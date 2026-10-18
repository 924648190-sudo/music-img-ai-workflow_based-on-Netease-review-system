import json,re,html
from urllib.parse import quote
def norm(x):return re.sub(r'[\W_]+','',str(x).lower())
def main(body:str,ref:str,intent:str,error:str)->dict:
    r=json.loads(ref);d=json.loads(intent);sid=r.get('id','');message=error
    if not message and r.get('kind')=='short':
        b=html.unescape(body or '')
        match=re.search(r'(?:https?://(?:y\.|m\.)?music\.163\.com/[^\s"<>]*?song[^\s"<>]*?[?&]id=|["\']songId["\']\s*:\s*["\']?)(\d{4,20})',b)
        if match:sid=match.group(1)
        else:message='短链接未解析出歌曲标识，请换用网易云完整歌曲链接；原画面描述无需重写。'
    elif not message and not sid:
        try:candidates=(json.loads(body).get('result') or {}).get('songs') or []
        except Exception:candidates=[]
        title=norm(d.get('song_title'));artist=norm(d.get('song_artist'))
        exact=[s for s in candidates if norm(s.get('name'))==title and (not artist or any(artist==norm(a.get('name')) for a in (s.get('artists') or s.get('ar') or [])))]
        if len(exact)==1:sid=str(exact[0]['id'])
        elif len(exact)>1:message='搜索到多个同名版本，请补充歌手或歌曲链接，以免把翻唱、现场版或其他MV混用。'
        else:message='未确认到唯一歌曲，请补充歌曲名与歌手，或提供网易云歌曲链接。'
    if message:sid='0'
    return {'song_id':sid or '0','valid':'no' if message else 'yes','message':message,'source_url':'https://music.163.com/song?id='+str(sid),'detail_url':'https://music.163.com/api/song/detail/?id='+str(sid or '0')+'&ids=%5B'+str(sid or '0')+'%5D'}
