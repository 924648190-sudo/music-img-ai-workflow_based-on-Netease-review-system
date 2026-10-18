import json,re

def load(raw):
    t=re.sub(r'<think>.*?</think>','',raw or '',flags=re.S).strip();t=re.sub(r'^```(?:json)?\s*','',t);t=re.sub(r'\s*```$','',t)
    try:d=json.loads(t)
    except Exception:
        p=t.find('{');d=json.JSONDecoder().raw_decode(t[p:])[0] if p>=0 else None
    if not isinstance(d,dict):raise ValueError('风格分析格式异常，请重试。')
    return d

def main(raw:str,intent:str)->dict:
    d=load(raw);i=load(intent);details=i.get('visual_details') or [];mode='detail_refine' if details and i.get('mode')=='detail_refine' else 'style_only'
    d['mode']=mode;d['user_details']=details if mode=='detail_refine' else [];d['user_contract']=i
    d['pre_review_flags']=[]
    ledger=d.get('factor_ledger') or []
    if not d.get('genre'):d['pre_review_flags'].append('genre_missing_do_not_infer_from_title')
    sel=d.get('selection') or {};valid_ids={x.get('id') for x in d.get('source_findings') or [] if isinstance(x,dict) and x.get('source_type') not in ['title','comment'] and x.get('support') in ['direct','contextual']}
    has_user=any(c.get('dimension')=='medium' and c.get('strength')=='required' for c in i.get('constraints') or [])
    if not has_user and sel.get('medium') and not valid_ids.intersection(sel.get('support_ids') or []):d['pre_review_flags'].append('medium_has_no_independent_support_compare_or_leave_open')
    return {'mode':mode,'style_data':json.dumps(d,ensure_ascii=False),'factor_ledger':json.dumps(ledger,ensure_ascii=False)}
