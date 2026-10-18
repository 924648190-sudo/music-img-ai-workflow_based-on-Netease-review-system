import json, re

CAP = 20
MAX_REFILLS = 3
KINDS = {'atmosphere', 'memory_imagery', 'musical_analysis', 'style_interpretation', 'creator_intent', 'relationship_lead'}

def obj(raw):
    try:
        d=json.loads(raw or '{}');return d if isinstance(d,dict) else {}
    except Exception:return {}

def model_obj(raw):
    t=re.sub(r'<think>.*?</think>', '', raw or '', flags=re.S).strip()
    t=re.sub(r'^```(?:json)?\s*|\s*```$', '', t)
    try:return obj(t) if t.startswith('{') else json.JSONDecoder().raw_decode(t[t.index('{'):])[0]
    except Exception:return {}

def normalize(raws, account):
    rows=[];seen_ids=set();seen_text=set();total=0;responses=0
    for raw in raws:
        d=obj(raw)
        if any(k in d for k in ('comments','hotComments','topComments')):responses+=1
        try:total=max(total,int(d.get('total') or 0))
        except Exception:pass
        for rank,key in [(1,'topComments'),(2,'hotComments'),(3,'comments')]:
            for p in d.get(key) or []:
                cid=str(p.get('commentId') or '');text=str(p.get('content') or '').strip()
                norm=re.sub(r'\W+','',text).casefold()
                if not cid or not norm:continue
                creator=bool(account and str((p.get('user') or {}).get('userId'))==str(account))
                rows.append({'id':cid,'text':text[:900], 'priority':'creator_verified' if creator else key,
                    'likes':int(p.get('likedCount') or 0),'rank':0 if creator else rank})
    rows.sort(key=lambda p:(p['rank'],-p['likes']))
    out=[]
    for p in rows:
        norm=re.sub(r'\W+','',p['text']).casefold()
        if p['id'] in seen_ids or norm in seen_text:continue
        seen_ids.add(p['id']);seen_text.add(norm);out.append(p)
    return out,total,responses

def initial(details,comments,artist):
    s=(obj(details).get('songs') or [{}])[0];account=(obj(artist).get('artist') or {}).get('accountId')
    rows,total,responses=normalize([comments],account)
    state={'title':s.get('name',''),'artists':[a.get('name','') for a in s.get('artists') or []],
        'account':account,'all_candidates':rows,'reviewed_ids':[], 'accepted':[], 'decisions':[],
        'song_id':str(s.get('id','')),'total':total,'response_count':responses,'refill_round':0,'refill_used':False,'errors':[]}
    pool=rows[:CAP];state['current_pool']=pool
    base='https://music.163.com/api/v1/resource/comments/R_SO_4_'+str(s.get('id',''))
    result={'pool':json.dumps({'song':state['title'],'artists':state['artists'],'remaining':CAP,'comments':pool},ensure_ascii=False),
            'state':json.dumps(state,ensure_ascii=False)}
    for i,offset in enumerate([20,40,60,80]):result['url'+str(i)]=base+'?limit=20&offset='+str(offset)
    return result

def apply_review(state,raw):
    d=model_obj(raw);decisions=d.get('decisions') or [];pool={x['id']:x for x in state.get('current_pool') or []}
    labels={};unknown=0
    for x in decisions:
        if not isinstance(x,dict):continue
        cid=str(x.get('id') or '')
        if cid not in pool:unknown+=1;continue
        if cid not in labels:labels[cid]=x
    if unknown:state['errors'].append('模型返回不存在的评论ID，已丢弃：'+str(unknown))
    missing=0;retained_norm={re.sub(r'\W+','',p['text']).casefold() for p in state['accepted']}
    for cid,p in pool.items():
        x=labels.get(cid) or {};kind=x.get('kind');useful=x.get('useful') is True and kind in KINDS
        if not x:missing+=1
        # 创作者身份由平台账号核验；模型不能把普通用户升级为作者。
        if kind=='creator_intent' and p['priority']!='creator_verified':kind='style_interpretation'
        norm=re.sub(r'\W+','',p['text']).casefold()
        if useful and norm not in retained_norm and len(state['accepted'])<CAP:
            row={**p,'kind':kind,'reason':str(x.get('reason') or '')[:180],
                 'visual_cues':str(x.get('visual_cues') or '')[:280],
                 'evidence_scope':'listener_impression_not_audio_fact' if kind!='creator_intent' else 'verified_account_statement_not_universal_fact'}
            state['accepted'].append(row);retained_norm.add(norm)
        state['decisions'].append({'id':cid,'useful':useful,'kind':kind or 'unassessed','reason':str(x.get('reason') or '筛选器未完成判断')[:180]})
    state['reviewed_ids']=list(dict.fromkeys(state['reviewed_ids']+list(pool)))
    if missing:state['errors'].append('未返回有效分类的评论数：'+str(missing)+'；未当作有效样本')
    state['current_pool']=[]
    return state

def first_review(state,raw):
    d=apply_review(obj(state),raw)
    # 无数据、总数已覆盖或已满20条时不再补采。
    more=len(d['accepted'])<CAP and (len(d['all_candidates'])>len(d['reviewed_ids']) or d['total']>20)
    return {'state':json.dumps(d,ensure_ascii=False),'needs_more':'yes' if more else 'no'}

def refill(state,page0,page1,page2,page3):
    d=obj(state);rows,total,responses=normalize([page0,page1,page2,page3],d.get('account'))
    # 重复热评、重复正文、首轮已审核ID均不重新计数。
    merged=[];seen_ids=set();seen_text=set()
    for p in sorted(d['all_candidates']+rows,key=lambda p:(p['rank'],-p['likes'])):
        norm=re.sub(r'\W+','',p['text']).casefold()
        if p['id'] in seen_ids or norm in seen_text:continue
        seen_ids.add(p['id']);seen_text.add(norm);merged.append(p)
    d['all_candidates']=merged;d['total']=max(total,d['total']);d['response_count']+=responses;d['last_response_count']=responses;d['refill_round']=d.get('refill_round',0)+1;d['refill_used']=True
    reviewed=set(d['reviewed_ids']);pool=[p for p in merged if p['id'] not in reviewed][:80]
    d['current_pool']=pool
    return {'state':json.dumps(d,ensure_ascii=False),'pool':json.dumps({'song':d['title'],'artists':d['artists'],
        'remaining':CAP-len(d['accepted']),'already_selected':[{'id':p['id'],'visual_cues':p['visual_cues']} for p in d['accepted']], 'comments':pool},ensure_ascii=False)}

def finish(state,raw=None):
    d=obj(state)
    if raw is not None:d=apply_review(d,raw)
    selected=d.get('accepted',[])[:CAP];count=len(selected)
    payload={'selected_comments':selected,'comment_sampling':{'target':CAP,'selected':count,
        'shortfall':CAP-count,'status':'target_reached' if count==CAP else 'insufficient_useful_comments',
        'total':d.get('total',0),'unique_candidates':len(d.get('all_candidates',[])),
        'semantically_reviewed':len(d.get('reviewed_ids',[])),'semantic_review_budget':CAP+MAX_REFILLS*80,
        'refill_rounds':d.get('refill_round',0),
        'refill_used':d.get('refill_used',False),'response_count':d.get('response_count',0),
        'order':'usefulness first; verified creator > pinned > hot > ordinary; semantic deduplication',
        'not_full_census':True,'errors':d.get('errors',[])},'filter_decisions':d.get('decisions',[])}
    base='https://music.163.com/api/v1/resource/comments/R_SO_4_'+d.get('song_id','')
    rounds=d.get('refill_round',0);last_offset=20+rounds*80
    more=count<CAP and rounds<MAX_REFILLS and d.get('last_response_count',0)>0 and (d.get('total',0)>last_offset or len(d.get('all_candidates',[]))>len(d.get('reviewed_ids',[])))
    result={'result':json.dumps(payload,ensure_ascii=False),'state':json.dumps(d,ensure_ascii=False),'needs_more':'yes' if more else 'no'}
    for i in range(4):result['url'+str(i)]=base+'?limit=20&offset='+str(last_offset+i*20)
    return result

def main(details:str,comments:str,artist:str)->dict:
    result=initial(details,comments,artist)
    return {k:result[k] for k in ['pool', 'state', 'url0', 'url1', 'url2', 'url3']}
