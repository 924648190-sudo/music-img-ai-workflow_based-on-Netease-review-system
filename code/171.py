import json
def main(details: str, mv_search: str) -> dict:
    try:s=json.loads(details)['songs'][0]
    except Exception:s={}
    mid=int(s.get('mvid') or 0);ids={str(a.get('id')) for a in s.get('artists') or []}
    try:items=(json.loads(mv_search).get('result') or {}).get('mvs') or []
    except Exception:items=[]
    if not mid:
        for m in items:
            mids={str(a.get('id')) for a in m.get('artists') or []}|{str(m.get('artistId',''))}
            if m.get('name','').strip()==s.get('name','').strip() and ids.intersection(mids):mid=int(m.get('id') or 0);break
    return {'mv_id':str(mid)}
