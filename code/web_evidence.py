import json,re,html
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit,quote,urljoin
from html.parser import HTMLParser

PRIMARY=('artofthetitle.com','netflix.com','imaginaryforces.com','katebush.com','bbc.co.uk','bbc.com','theasc.com','arri.com','panavision.com','a24films.com','criterion.com','ghibli.jp','disney.com','pixar.com','sony.com','sonypictures.com','warnerbros.com','universalpictures.com','focusfeatures.com','paramount.com','mubi.com','oscars.org','bfi.org.uk','afi.com','vam.ac.uk','metmuseum.org','moma.org','sfmoma.org','designmuseum.org','cooperhewitt.org','si.edu','brooklynmuseum.org','maxon.net','adobe.com')
def allowed(url):
    try:
        p=urlsplit(url);host=(p.hostname or '').lower()
        return p.scheme=='https' and not p.username and not p.password and p.port in (None,443) and any(host==d or host.endswith('.'+d) for d in PRIMARY)
    except Exception:return False
class SourceLinks(HTMLParser):
    def __init__(self):super().__init__();self.link=None;self.rows=[]
    def handle_starttag(self,t,a):
        if t=='a':self.link={'url':dict(a).get('href',''),'parts':[]}
    def handle_data(self,s):
        if self.link:self.link['parts'].append(s)
    def handle_endtag(self,t):
        if t=='a' and self.link:
            url=urljoin('https://www.artofthetitle.com/',self.link['url'])
            title=' '.join(self.link['parts']).strip()
            if title and allowed(url) and '/title/' in url:
                self.rows.append({'title':title[:200],'url':url,'snippet':'站内检索候选；必须另读正文，不能从命中本身推断风格。','scope':'unreviewed_reference_link'})
            self.link=None
def rss(body):
    # 同时兼容旧实体/RSS样本；生产视觉资料来自站内索引的真实链接。
    try:
        data=json.loads(body or '{}')
        pages=(data.get('query') or {}).get('pages') or {}
        out=[]
        for page in pages.values():
            if 'missing' in page:continue
            for link in page.get('extlinks') or []:
                url=link.get('url') or link.get('*') or ''
                if url.startswith('http://'):url='https://'+url[7:]
                if allowed(url):out.append({'title':page.get('title','')+' · 引用来源','url':url,'snippet':'该条目列出的外部引用，需读取正文确认具体支持内容。','scope':'unreviewed_reference_link'})
        return out
    except Exception:pass
    if '<html' in (body or '').lower() or '<!doctype' in (body or '').lower():
        p=SourceLinks()
        try:p.feed((body or '')[:500000]);return p.rows
        except Exception:return []
    try:root=ET.fromstring(body or '')
    except Exception:return []
    out=[]
    for item in root.findall('.//item')[:8]:
        url=item.findtext('link','');title=html.unescape(item.findtext('title',''));snippet=re.sub('<[^>]+>',' ',html.unescape(item.findtext('description','')))
        if allowed(url):out.append({'title':title[:200],'url':url,'snippet':snippet[:650],'scope':'search_snippet_only'})
    return out
def choose(relation:str,design:str,identity:str)->dict:
    d=json.loads(identity);terms=[d.get('title','')]+[a.get('canonical_title') or a.get('input_name','') for a in d.get('media_candidates') or []]
    rows=[];seen=set();entity_docs=[]
    for raw in [relation,design]:
        try:
            data=json.loads(raw);pages=(data.get('query') or {}).get('pages') or {}
            if data.get('AbstractText') and data.get('Heading'):
                entity_docs.append({'title':data['Heading'],'url':data.get('AbstractURL',''),'scope':'secondary_instant_answer_work_context_not_recording_audio','text':data['AbstractText'][:5500],'warning':'可能为原作或同名作品；先比对平台具体版本。不是完整、实时的全网检索，也未审阅音视频。'})
        except Exception:pages={}
        for p in pages.values():
            title=p.get('title','');text=p.get('extract','')
            if 'missing' in p or not text:continue
            pieces=[text[:2000]]
            for t in terms:
                idx=text.lower().find(t.lower()) if t else -1
                if idx>=0:pieces.append(text[max(0,idx-250):idx+1500])
            entity_docs.append({'title':title,'url':p.get('fullurl') or 'https://en.wikipedia.org/wiki/'+quote(title.replace(' ','_')),'scope':'secondary_entity_text_not_video_review','text':'\n'.join(dict.fromkeys(pieces))[:6500]})
    for x in rss(relation)+rss(design):
        if x['url'] in seen:continue
        seen.add(x['url']);normalized=re.sub(r'[^a-z0-9\u3400-\u9fff]','',(x['title']+' '+x['url']+' '+x['snippet']).lower())
        score=sum(2 for t in terms if t and re.sub(r'[^a-z0-9\u3400-\u9fff]','',t.lower()) in normalized)
        if not score:continue
        # 引用列表并不意味着全都相关；优先URL直接含作品或歌曲名称的制作方资料。
        score+=sum(4 for t in terms if t and re.sub(r'[^a-z0-9]','',t.lower()) in re.sub(r'[^a-z0-9]','',x['url'].lower()))
        if 'netflix.com/tudum/' in x['url'] or 'imaginaryforces.com/project/' in x['url']:score+=2
        if 'artofthetitle.com/title/' in x['url']:score+=4
        if score:rows.append((score,x))
    rows.sort(key=lambda x:-x[0]);items=[x[1] for x in rows[:6]]
    return {'entity_context':json.dumps(entity_docs,ensure_ascii=False),'search_candidates':json.dumps(items,ensure_ascii=False),'has_sources':'yes' if items else 'no','page1_url':items[0]['url'] if items else '',
        'page2_url':items[1]['url'] if len(items)>1 else (items[0]['url'] if items else '')}
class Text(HTMLParser):
    def __init__(self):super().__init__();self.skip=0;self.parts=[]
    def handle_starttag(self,t,a):
        if t in ('script','style','nav','footer'):self.skip+=1
    def handle_endtag(self,t):
        if t in ('script','style','nav','footer') and self.skip:self.skip-=1
    def handle_data(self,s):
        if not self.skip and s.strip():self.parts.append(s.strip())
def pack(candidates:str,page1:str,page2:str)->dict:
    items=json.loads(candidates);docs=[]
    for i,body in enumerate([page1,page2]):
        if i>=len(items):break
        p=Text()
        try:p.feed((body or '')[:500000]);text=' '.join(p.parts)
        except Exception:text=''
        # HTML抓取不等于看过影片；拒绝将空页或反爬页升级为全文证据。
        blocked=bool(re.search(r'access denied|captcha|verify you are human|just a moment',text[:1500],re.I))
        useful=len(text)>200 and not blocked
        # 抓取失败时，“引用链接”不能升级成带实质信息的搜索摘要。
        fallback=items[i].get('scope','unreviewed_reference_link')
        docs.append({'url':items[i]['url'],'title':items[i]['title'],'scope':'web_text_only' if useful else fallback,'text':text[:14000] if useful else items[i]['snippet']})
    return {'result':json.dumps({'status':'retrieved_text' if any(x['scope']=='web_text_only' for x in docs) else 'snippets_only','documents':docs,'other_candidates':items[2:],'not_video_review':True},ensure_ascii=False)}
