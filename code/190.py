import json,re
from datetime import datetime,timezone,timedelta

def obj(s):
    try:
        x=json.loads(s or '{}');return x if isinstance(x,dict) else {}
    except Exception:return {}

def clean(details: str, lyrics: str, comments: str, artist: str, mv_search: str, source_url: str, source_notes: str) -> dict:
    s=(obj(details).get('songs') or [{}])[0]; arts=s.get('artists') or []
    c=obj(comments); verified=(obj(artist).get('artist') or {}).get('accountId')
    try: total=int(c.get('total',0))
    except Exception: total=0
    cap=20
    candidates=[];seen=set()
    for rank,key in [(1,'topComments'),(2,'hotComments'),(3,'comments')]:
        for post in c.get(key) or []:
            cid=str(post.get('commentId',''))
            if not cid or cid in seen:continue
            seen.add(cid);u=post.get('user') or {}
            creator=bool(verified and str(u.get('userId'))==str(verified))
            candidates.append((0 if creator else rank,-int(post.get('likedCount') or 0),post,creator,key))
    candidates.sort(key=lambda p:(p[0],p[1]))
    selected=[];author=[]
    for _,_,p,creator,kind in candidates[:cap]:
        item={'id':str(p.get('commentId')),'priority':'creator_verified' if creator else kind,'likes':p.get('likedCount',0),'text':str(p.get('content',''))[:900]}
        selected.append(item)
        # 寒暄、感谢、演唱会承诺不自动作为创作意图。语义复核在独立分支完成。
        if creator and re.search('创作|编曲|曲风|风格|灵感|表达|情绪|氛围|年代|复古|致敬|这首|这歌|歌曲|写这|写歌|想让|想要',item['text']):author.append(item)
    mv_id=int(s.get('mvid') or 0);title=s.get('name','');artist_ids={str(a.get('id')) for a in arts}
    matches=[]
    mv_result=obj(mv_search).get('result')
    if not isinstance(mv_result,dict):mv_result={}
    for m in mv_result.get('mvs') or []:
        mids={str(a.get('id')) for a in m.get('artists',[])}|{str(m.get('artistId',''))}
        if m.get('name','').strip()==title.strip() and artist_ids.intersection(mids):matches.append(m)
    if not mv_id and matches:mv_id=int(matches[0].get('id') or 0)
    raw=(obj(lyrics).get('lrc') or {}).get('lyric','')
    instruments=[];lyric_lines=[]
    for line in raw.splitlines():
        t=re.sub(r'\[[^\]]*\]','',line).strip()
        if not t:continue
        if re.search(r'吉他|Guitar|贝斯|Bass|钢琴|Piano|弦乐|Strings|鼓\s*[:：]|Drum|合成器|Synth|采样|Sampler',t,re.I):
            # 移除演奏者署名，只保留器乐名称和可验证类型。
            instruments.append(re.split('[:：]',t)[0][:70]);continue
        if re.search('[:：]|作词|作曲|编曲|制作人|录音|混音|母带|工作室',t):continue
        if t not in lyric_lines:lyric_lines.append(t)
    release=''
    try:release=datetime.fromtimestamp(s.get('publishTime',0)/1000,timezone(timedelta(hours=8))).strftime('%Y')
    except Exception:pass
    evidence={'identity':{'title':title,'artists':[a.get('name') for a in arts],'language_hint':'未核实','release_year_context_only':release,'source':source_url},'instrument_labels':list(dict.fromkeys(instruments)),'lyrics_for_mood_and_natural_imagery_only':lyric_lines[:100],'selected_comments':selected,'comment_sampling':{'total':total,'cap':cap,'selected':len(selected),'order':'verified creator > pinned > hot > fallback','not_full_census':True},'supplementary_reference_notes':(source_notes or '')[:12000],'audio_reviewed':False,'mv_lookup':{'id':mv_id,'catalog_search_candidates':len(matches)},'restrictions':['无总评、人物故事、关系分析、制作名单、曲序、时长、公司、专辑日期、乐理或重听建议。','歌词只提炼情绪／氛围与明确的非人物自然地理意象；评论不引入个人故事、物件或消费场景。']}
    return {'evidence':json.dumps(evidence,ensure_ascii=False),'author_candidates':json.dumps(author,ensure_ascii=False),'has_author_intent':'yes' if author else 'no','has_mv':'yes' if mv_id else 'no','mv_id':str(mv_id),'sample_count':len(selected),'sample_cap':cap}

import json,re,html
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit,quote,urljoin
from html.parser import HTMLParser

PRIMARY=('artofthetitle.com','netflix.com','imaginaryforces.com','katebush.com','bbc.co.uk','bbc.com','theasc.com','arri.com','panavision.com','a24films.com','criterion.com','ghibli.jp','disney.com','pixar.com','sony.com','sonypictures.com','warnerbros.com','universalpictures.com','focusfeatures.com','paramount.com','mubi.com','oscars.org','bfi.org.uk','afi.com','vam.ac.uk','metmuseum.org','moma.org','sfmoma.org','designmuseum.org','cooperhewitt.org','si.edu','brooklynmuseum.org','maxon.net','adobe.com','jamiehewlett.com','taschen.com','gorillaz.com','ourlasthopelosthope.com','bandcamp.com')
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
def choose(relation:str,design:str,identity:str,culture:str="",artist_context:str="")->dict:
    d=json.loads(identity);terms=[d.get('title','')]+d.get('artists',[])+[a.get('canonical_title') or a.get('input_name','') for a in d.get('media_candidates') or []]
    rows=[];seen=set();entity_docs=[]
    for raw in [relation,design,artist_context]:
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
    for x in rss(relation)+rss(design)+rss(culture)+rss(artist_context)+d.get("research_seed_links",[]):
        if x['url'] in seen:continue
        seen.add(x['url']);normalized=re.sub(r'[^a-z0-9\u3400-\u9fff]','',(x['title']+' '+x['url']+' '+x['snippet']).lower())
        score=sum(2 for t in terms if t and re.sub(r'[^a-z0-9\u3400-\u9fff]','',t.lower()) in normalized)
        if not score:continue
        # 引用列表并不意味着全都相关；优先URL直接含作品或歌曲名称的制作方资料。
        score+=sum(4 for t in terms if t and re.sub(r'[^a-z0-9]','',t.lower()) in re.sub(r'[^a-z0-9]','',x['url'].lower()))
        if 'netflix.com/tudum/' in x['url'] or 'imaginaryforces.com/project/' in x['url']:score+=2
        if 'artofthetitle.com/title/' in x['url']:score+=4
        if x.get('scope','').startswith('artist_'):score+=8
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
        useful=len(text)>200 and not blocked and any(t.lower() in text.lower() for t in re.split(r' · | — ',items[i].get('title','')) if len(t)>3)
        # 抓取失败时，“引用链接”不能升级成带实质信息的搜索摘要。
        fallback=items[i].get('scope','unreviewed_reference_link')
        docs.append({'url':items[i]['url'],'title':items[i]['title'],'scope':'web_text_only' if useful else fallback,'text':text[:14000] if useful else items[i]['snippet']})
    return {'result':json.dumps({'status':'retrieved_text' if any(x['scope']=='web_text_only' for x in docs) else 'snippets_only','documents':docs,'other_candidates':items[2:],'not_video_review':True},ensure_ascii=False)}

def main(details:str,lyrics:str,comments:str,artist:str,mv_search:str,source_url:str,request:str,relation:str,design:str,identity:str,intent:str,culture:str,artist_context:str,artist_bio:str,comment_review:str)->dict:
    c=clean(details,lyrics,comments,artist,mv_search,source_url,'')
    ident=json.loads(identity)
    registry={'gorillaz': [{'title': 'Gorillaz · Jamie Hewlett official biography', 'url': 'https://jamiehewlett.com/pages/about', 'scope': 'artist_visual_creator_background_not_recording_style'}], 'our last hope lost hope': [{'title': 'Our Last Hope Lost Hope · artist official profile', 'url': 'https://ourlasthopelosthope.com/', 'scope': 'artist_background_not_audio_review'}, {'title': 'Our Last Hope Lost Hope · official album page', 'url': 'https://ourlasthopelosthope.bandcamp.com/album/our-last-hope-lost-hope', 'scope': 'artist_album_metadata'}]}
    seeds=[]
    for a in ident.get('artists',[]):
        for x in registry.get(a.casefold().strip(),[]):
            seeds.append(dict(x,snippet='艺人资料地址索引；必须读取正文后才能使用内容。'))
    ident['research_seed_links']=seeds
    refs=choose(relation,design,json.dumps(ident,ensure_ascii=False),culture,artist_context)
    evidence=json.loads(c['evidence']);evidence['intent']=json.loads(intent);evidence['source_identity']=json.loads(identity);evidence['media_entity_documents']=json.loads(refs.pop('entity_context'))
    evidence.pop('supplementary_reference_notes',None)
    s=(obj(details).get('songs') or [{}])[0];aid=str(((s.get('artists') or [{}])[0]).get('id',0))
    bio=obj(artist_bio);artist_obj=obj(artist).get('artist') or {};intro=[]
    for x in bio.get('introduction') or []:
        if isinstance(x,dict):intro.append(str(x.get('ti') or '')+' '+str(x.get('txt') or ''))
    evidence['artist_background']={'scope':'artist_level_not_recording_genre','source_url':'https://music.163.com/api/artist/introduction?id='+aid,'brief':str(bio.get('briefDesc') or artist_obj.get('briefDesc') or '')[:5000],'introductions':'\n'.join(intro)[:6000]}
    filtered=obj(comment_review)
    evidence['selected_comments']=filtered.get('selected_comments') or []
    evidence['comment_sampling']=filtered.get('comment_sampling') or {'target':20,'selected':0,'status':'filter_unavailable'}
    evidence['comment_filter_audit']='完整逐条筛选记录保留在有效评论汇合节点；此处只提供有效原文，避免拒绝内容污染风格总结。'
    for post in evidence.get('selected_comments',[]):
        t=post.get('text','')
        if post.get('priority')=='creator_verified' and post in json.loads(c['author_candidates']):kind='creator_intent_candidate'
        elif re.search(r'原声|片尾曲|主题曲|采样自|出自|作于|soundtrack|sampled',t,re.I):kind='relationship_lead_verify_first'
        elif re.search(r'听感|听这|这歌|这首|旋律|混乱|邪典|节奏|幼稚|失控|悲伤|顽皮',t):kind='listening_or_association_requires_semantic_review'
        else:kind='personal_association_or_irrelevant'
        post['kind_hint']=kind;post['rule']='外部作品/艺人名仅为待核联想，不自动成为视觉参考；听感仅辅助情绪。'
    evidence['search_queries_scope']='3.1 平台艺人简介、公开RSS视觉文化候选、百科外链与机构网页；摘要不等于全文，失败明确降级；无实际音频审听；RAG未接入。'
    refs['evidence']=json.dumps(evidence,ensure_ascii=False)
    refs['sampling']=json.dumps(evidence['comment_sampling'],ensure_ascii=False)
    return refs
