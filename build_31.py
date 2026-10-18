import json,copy,re,subprocess,hashlib
from pathlib import Path
R=Path(__file__).parent
out=json.loads((R/'baseline-online-3.0.json').read_text());graph=out['workflow']['graph'];nodes=graph['nodes'];edges=graph['edges'];N={n['id']:n for n in nodes}
def read(p):return (R/p).read_text()
def writecode(i,path):N[i]['data']['code']=read('code/'+path)
def var(name,n,key):return {'variable':name,'value_selector':[n,key],'value_type':'string'}
def addvar(i,name,n,key):N[i]['data']['variables'].append(var(name,n,key))
def addout(i,*keys):
 for k in keys:N[i]['data']['outputs'][k]={'type':'string','children':None}
def newnode(i,template,title,x,y):
 n=copy.deepcopy(N[template]);n['id']=i;n['data']['title']=title;n['data']['selected']=False;n['selected']=False;n['position']={'x':x,'y':y};n['positionAbsolute']={'x':x,'y':y};nodes.append(n);N[i]=n;return n['data']
def edge(a,b,handle='source'):
 edges.append({'id':a+'-'+handle+'-'+b,'source':a,'target':b,'sourceHandle':handle,'targetHandle':'target','type':'custom','data':{'sourceType':N[a]['data']['type'],'targetType':N[b]['data']['type'],'isInIteration':False,'isInLoop':False}})
def prompt(i,p,user=None):
 N[i]['data']['prompt_template'][0]['text']=read('prompts/'+p)
 if user is not None:N[i]['data']['prompt_template'][1]['text']=user
writecode('110','input_parse.py');writecode('116','prepare_lookup.py');writecode('130','requests.py');writecode('210','style_guard.py');writecode('225','format_final.py')
N['110']['data']['title']='3.1 分享元数据与用户要求拆分'
prompt('115','intent.md','拆分后的输入：{{#110.request#}}\n歌曲引用：{{#110.ref#}}')
N['115']['data']['title']='3.1 用户分维度约束契约'
addout('130','artist_bio_url','culture_url','artist_context_url')
# 仅为可核验的艺人资料地址索引，不存储风格事实、不接入RAG；其他艺人走通用检索。
registry={'gorillaz':[{'title':'Gorillaz · Jamie Hewlett official biography','url':'https://jamiehewlett.com/pages/about','scope':'artist_visual_creator_background_not_recording_style'}], 'our last hope lost hope':[{'title':'Our Last Hope Lost Hope · artist official profile','url':'https://ourlasthopelosthope.com/','scope':'artist_background_not_audio_review'},{'title':'Our Last Hope Lost Hope · official album page','url':'https://ourlasthopelosthope.bandcamp.com/album/our-last-hope-lost-hope','scope':'artist_album_metadata'}]}
(R/'source-directory.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2))
for i,url,title,y in [('182','{{#130.culture_url#}}','艺术家视觉文化 · 公开检索',-650),('183','{{#130.artist_context_url#}}','艺人百科与外部来源索引',-850),('184','{{#130.artist_bio_url#}}','平台艺术家简介',-1050)]:
 d=newnode(i,'180',title,2880,y);d['url']=url;edge('130',i);edge(i,'190')
# 专辑封面独立分支
m=newnode('131','110','专辑封面来源与版本',2880,1300);m['code']=read('code/cover_meta.py');m['variables']=[var('details','126','body')];m['outputs']={k:{'type':'string','children':None} for k in ['cover_url','has_cover','meta']}
c=newnode('132','174','有专辑封面可审阅？',3200,1300);c['cases'][0]['conditions'][0]['variable_selector']=['131','has_cover'];c['cases'][0]['conditions'][0]['id']='132-c'
h=newnode('133','175','读取专辑封面图片',3520,1200);h['url']='{{#131.cover_url#}}'
l=newnode('134','176','专辑封面独立视觉审阅',3840,1200);l['prompt_template']=[{'id':'134-sys','role':'system','text':read('prompts/cover.md')},{'id':'134-usr','role':'user','text':'封面元数据：{{#131.meta#}}'}];l['vision']['configs']['variable_selector']=['133','files'];l['error_strategy']='default-value';l['default_value']=[{'key':'text','type':'string','value':'{"scope":"image_unavailable","visual_facts":{},"uncertainties":["封面读取或视觉模型不可用，未完成图像审阅"]}'}]
f=newnode('135','177','专辑封面缺失降级',3520,1450);f['code']='def main(meta:str)->dict:\n    import json\n    return {"result":json.dumps({"scope":"image_unavailable","metadata":meta,"visual_facts":{},"uncertainties":["平台未返回可用专辑封面"]},ensure_ascii=False)}';f['variables']=[var('meta','131','meta')]
a=newnode('136','178','专辑封面参考汇合',4160,1300);a['variables']=[['134','text'],['135','result']]
for a,b in [('130','131'),('131','132'),('133','134'),('134','136'),('135','136'),('136','200')]:edge(a,b)
edge('132','133','true');edge('132','135','false')
# 扩展来源选择，兼容旧 clean 函数
base=N['190']['data']['code'];clean=base.split('\nimport json,re,html\n')[0]
web=read('code/web_evidence.py')
web=web.replace("'maxon.net','adobe.com')","'maxon.net','adobe.com','jamiehewlett.com','taschen.com','gorillaz.com','ourlasthopelosthope.com','bandcamp.com')")
web=web.replace('def choose(relation:str,design:str,identity:str)->dict:','def choose(relation:str,design:str,identity:str,culture:str="",artist_context:str="")->dict:')
web=web.replace("terms=[d.get('title','')]+", "terms=[d.get('title','')]+d.get('artists',[])+")
web=web.replace('for raw in [relation,design]:','for raw in [relation,design,artist_context]:')
web=web.replace("if score:rows.append((score,x))","if x.get('scope','').startswith('artist_'):score+=8\n        if score:rows.append((score,x))")
web=web.replace('for x in rss(relation)+rss(design):','for x in rss(relation)+rss(design)+rss(culture)+rss(artist_context)+d.get("research_seed_links",[]):')
web=web.replace("rows.sort(key=lambda x:-x[0]);items=[x[1] for x in rows[:6]]","rows.sort(key=lambda x:-x[0]);items=[x[1] for x in rows[:6]]")
# 不把页面导航或泛化反爬网页标为实际正文
web=web.replace("useful=len(text)>200 and not blocked","useful=len(text)>200 and not blocked and any(t.lower() in text.lower() for t in re.split(r' · | — ',items[i].get('title','')) if len(t)>3)")
wrapper='''\ndef main(details:str,lyrics:str,comments:str,artist:str,mv_search:str,source_url:str,request:str,relation:str,design:str,identity:str,intent:str,culture:str,artist_context:str,artist_bio:str)->dict:
    c=clean(details,lyrics,comments,artist,mv_search,source_url,'')
    ident=json.loads(identity)
    registry=REGISTRY
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
    evidence['artist_background']={'scope':'artist_level_not_recording_genre','source_url':'https://music.163.com/api/artist/introduction?id='+aid,'brief':str(bio.get('briefDesc') or artist_obj.get('briefDesc') or '')[:5000],'introductions':'\\n'.join(intro)[:6000]}
    for post in evidence.get('selected_comments',[]):
        t=post.get('text','')
        if post.get('priority')=='creator_verified' and post in json.loads(c['author_candidates']):kind='creator_intent_candidate'
        elif re.search(r'原声|片尾曲|主题曲|采样自|出自|作于|soundtrack|sampled',t,re.I):kind='relationship_lead_verify_first'
        elif re.search(r'听感|听这|这歌|这首|旋律|混乱|邪典|节奏|幼稚|失控|悲伤|顽皮',t):kind='listening_or_association_requires_semantic_review'
        else:kind='personal_association_or_irrelevant'
        post['kind_hint']=kind;post['rule']='外部作品/艺人名仅为待核联想，不自动成为视觉参考；听感仅辅助情绪。'
    evidence['search_queries_scope']='3.1 平台艺人简介、公开RSS视觉文化候选、百科外链与机构网页；摘要不等于全文，失败明确降级；无实际音频审听；RAG未接入。'
    refs['evidence']=json.dumps(evidence,ensure_ascii=False)
    refs['sampling']=json.dumps({'selected':c['sample_count'],'cap':c['sample_cap'],'author_candidates':json.loads(c['author_candidates'])},ensure_ascii=False)
    return refs
'''.replace('REGISTRY',repr(registry))
N['190']['data']['code']=clean+'\n'+web+wrapper
for name,n in [('culture','182'),('artist_context','183'),('artist_bio','184')]:addvar('190',name,n,'body')
N['190']['data']['title']='评论分类、艺人背景与可信网页筛选'
N['190']['data']['desc']='评论≤500最多10条，>500最多15条；作者/置顶/热门优先；评论实体需核验；网页最多读取2个。'
prompt('200','step1.md','用户契约：{{#116.intent#}}\n音乐与文化资料：{{#190.evidence#}}\n网页正文：{{#196.output#}}\n专辑封面审阅：{{#136.output#}}\nMV单帧：{{#178.output#}}')
N['200']['data']['title']='3.1 情绪与媒介分离规划'
N['210']['data']['title']='用户契约固定与证据预检'
# 独立方案审查：读取图像汇合和资料，防止计划遗漏证据
l=newnode('215','200','3.1 风格方案审查与修订',6080,300);l['prompt_template']=[{'id':'215-sys','role':'system','text':read('prompts/review.md')},{'id':'215-user','role':'user','text':'原始用户契约：{{#116.intent#}}\n待审查计划：{{#210.style_data#}}\n原始资料：{{#190.evidence#}}\n网页正文：{{#196.output#}}\n专辑封面：{{#136.output#}}\nMV单帧：{{#178.output#}}'}]
edges[:]=[e for e in edges if not (e['source']=='210' and e['target']=='220')];edge('210','215');edge('215','220')
prompt('220','step2.md','用户契约：{{#116.intent#}}\n确认的模式：{{#210.mode#}}\n审查修订后的风格计划：{{#215.text#}}')
N['220']['data']['title']='3.1 最终Prompt与栏目边界自检'
N['225']['data']['title']='栏目收束、约束核验与最终格式'
addvar('225','intent','116','intent')
# 布局为新审查节点留出空间
for i,x in [('220',6400),('225',6720),('230',7040)]:N[i]['position']['x']=x;N[i]['positionAbsolute']['x']=x
out['app']['name']='音乐 × 影视 → 视觉风格 3.1';out['app']['description']='3.1：分享元数据清洗、分维度用户契约、艺人视觉文化检索、专辑封面独立审阅、评论分类、媒介候选比较与独立审查。RAG未接入；极简方案暂缓。'
from comment_patch import apply
apply(out)
for n in nodes:
 d=n['data'];d['selected']=False;n['selected']=False
 if d['type']=='llm':
  d['reasoning_format']='separated'
  for part in d.get('prompt_template',[]):part['text']=part.get('text','').rstrip('\n')
 if d['type']=='code':compile(d['code'],n['id'],'exec');(R/'code'/(n['id']+'.py')).write_text(d['code'])
(R/'workflow-3.1.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
(R/'music-visual-style-3.1.yml').write_bytes(subprocess.check_output(['ruby','-rjson','-ryaml','-e','puts YAML.dump(JSON.parse(STDIN.read))'],input=json.dumps(out,ensure_ascii=False).encode()))
print(json.dumps({'nodes':len(nodes),'edges':len(edges),'models':{i:N[i]['data']['model']['name'] for i in ['115','176','134','200','215','220']},'rag_nodes':sum(n['data']['type']=='knowledge-retrieval' for n in nodes)},ensure_ascii=False))
