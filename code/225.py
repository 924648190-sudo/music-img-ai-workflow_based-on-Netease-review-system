import json,re

def load(raw):
    t=re.sub(r'<think>.*?</think>','',raw or '',flags=re.S).strip();t=re.sub(r'^```(?:json)?\s*','',t);t=re.sub(r'\s*```$','',t)
    try:d=json.loads(t)
    except Exception:
        p=t.find('{');d=json.JSONDecoder().raw_decode(t[p:])[0] if p>=0 else None
    if not isinstance(d,dict):raise ValueError('最终Prompt格式异常，请重试。')
    return d

def main(raw:str,mode:str,intent:str)->dict:
    d=load(raw);i=load(intent);rows=d.get('sections') or [];allowed=['风格与文化语境','表现方式与媒介','色彩与光影','情绪与氛围','质感与处理方式']
    if mode=='detail_refine':allowed.append('用户画面细化')
    rev=d.get('review') or {};constraints=i.get('constraints') or []
    required={str(c['id']) for c in constraints if c.get('id')};checked={str(x) for x in rev.get('checked_constraint_ids') or []}
    if rev.get('status')!='pass' or not required.issubset(checked):raise ValueError('用户要求审查未完成，请重试。')
    by={};seen=set()
    for r in rows:
        if not isinstance(r,dict) or r.get('title') not in allowed:continue
        title=r['title'];t=str(r.get('text') or '').strip()
        if title in by:raise ValueError('最终栏目重复，请重试。')
        if not t:continue
        # 去除完全重复句；用户约束原文另在最后列出，不在此凭关键词改写语义。
        sentences=re.split(r'(?<=[。！？])',t);parts=[]
        for s in sentences:
            key=re.sub(r'\s+','',s)
            if key and key not in seen:parts.append(s);seen.add(key)
        by[title]=''.join(parts)
    if mode=='detail_refine' and not by.get('用户画面细化'):raise ValueError('缺少用户画面细化，请重试。')
    body='\n\n'.join('【'+title+'】'+by[title] for title in allowed if by.get(title))
    if not body:raise ValueError('最终风格字段为空，请重试。')
    rules='【约束与生成规范】\n参考范围：音乐及相关作品辅助视觉风格；主体内容与用户指定参考保持优先。'
    if mode=='style_only':rules+='本输出作为风格参考，主体内容由用户另行指定。'
    locks=[]
    for c in constraints:
        q=str(c.get('quote') or '').strip();target=str(c.get('target') or '按用户原意');strength={'required':'明确要求','preferred':'偏好','forbidden':'禁止项'}.get(c.get('strength'),'要求')
        if q:locks.append(strength+'（'+target+'）：'+q)
    if locks:rules+='\n用户约束：'+'；'.join(locks)+'。'
    rules+='\n生成质量：形体、材质、透视与光照自洽，细节表达符合所选媒介。\n内容规范：默认SFW，非色情、无露骨性内容、无性化未成年人、无血腥暴力；文字与标识按用户明确要求处理。'
    return {'prompt':body+'\n\n'+rules}
