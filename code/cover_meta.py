import json
from urllib.parse import urlsplit

def main(details:str)->dict:
    try:s=json.loads(details)['songs'][0]
    except Exception:s={}
    a=s.get('album') or s.get('al') or {};url=str(a.get('picUrl') or '')
    p=urlsplit(url)
    host=(p.hostname or '').lower()
    valid=p.scheme in ('http','https') and not p.username and not p.password and any(host==d or host.endswith('.'+d) for d in ['music.126.net','music.163.com'])
    if valid:url='https://'+p.netloc+p.path+('?' + p.query if p.query else '')
    else:url=''
    return {'cover_url':url,'has_cover':'yes' if url else 'no','meta':json.dumps({'scope':'album_cover_only','song_title':s.get('name'),'album_title':a.get('name'),'source_url':url,'note':'单张专辑封面；不代表听感或MV，不复制主体。'},ensure_ascii=False)}
