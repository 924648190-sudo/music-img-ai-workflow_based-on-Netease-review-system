import re,json,html
from urllib.parse import urlsplit,unquote

def song_ref(value):
    value=html.unescape((value or '').strip()).rstrip('.,，。；;）)]】>')
    if re.fullmatch(r'\d{4,20}',value):return {'kind':'id','id':value,'url':'https://music.163.com/song?id='+value}
    if not re.match(r'^https?://',value):return None
    try:
        p=urlsplit(value);host=(p.hostname or '').lower()
        if p.username or p.password or p.port not in (None,80,443):return None
    except ValueError:return None
    if host=='163cn.tv' and p.path not in ('','/'):return {'kind':'short','id':'','url':'https://163cn.tv'+p.path}
    if host not in ('music.163.com','y.music.163.com','m.music.163.com'):return None
    path=unquote(p.path+'?'+p.query+'#'+p.fragment)
    if not re.search(r'(?:/|#)(?:song(?:\b|/)|outchain/player)',path):return None
    ids=re.findall(r'(?:[?&#]|\b)id=(\d{4,20})(?:\D|$)',path)
    if not ids or ('outchain/player' in path and re.search(r'type=(?!2\b)\d+',path)):return None
    sid=ids[0];return {'kind':'id','id':sid,'url':'https://music.163.com/song?id='+sid}

def main(userinput_query:str,song_url:str)->dict:
    q=html.unescape((userinput_query or '').strip()).replace('https\\://','https://').replace('http\\://','http://')
    field=html.unescape((song_url or '').strip()).replace('https\\://','https://')
    urls=re.findall(r'https?://[^\s<>"\u3000，。；！？、（）《》\[\]\)]+',q)
    refs=[];music_urls=[]
    for u in urls:
        r=song_ref(u)
        if r:refs.append(r);music_urls.append(u)
    f=song_ref(field) if field else None
    error=''
    if field and not f:error='song_url暂支持网易云歌曲链接、163cn.tv短链或歌曲ID；其他参考请保留在描述中。'
    if f:refs.insert(0,f)
    # 标准链接与短链共存时留待解析核验，不因同曲两种写法直接判冲突。
    ids={r['id'] for r in refs if r['kind']=='id'};shorts={r['url'] for r in refs if r['kind']=='short'}
    if len(ids)>1 or len(shorts)>1 or (ids and shorts):error='检测到多个歌曲引用，请只保留本次参考的一首链接。'
    r=refs[0] if refs else {'kind':'none','id':'','url':''}
    clean=q
    for u in music_urls:clean=clean.replace(u,' ')
    metadata=[]
    pattern=r'分享\s*([^\n《》]{1,120}?)\s*的(?:单曲|歌曲)\s*《([^》\n]+)》'
    def share(m):
        metadata.append({'artist':m.group(1).strip(),'title':m.group(2).strip(),'origin':'platform_share_identity_only'})
        return ' '
    clean=re.sub(pattern,share,clean)
    clean=re.sub(r'[（(]\s*(?:来自\s*)?@?网易云音乐\s*[）)]',' ',clean)
    clean=re.sub(r'\s+',' ',clean).strip(' ，,;；')
    return {'request':json.dumps({'song_share_metadata':metadata,'user_requirements_text':clean,'identity_only_warning':'分享歌名与艺术家用于歌曲定位，不是画面要求，也不自动作为情绪或媒介依据。'},ensure_ascii=False),'raw_query':q,'ref':json.dumps(r,ensure_ascii=False),'input_error':error}
