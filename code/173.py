import json
def main(body: str) -> dict:
    try:d=json.loads(body).get('data') or {}
    except Exception:d={}
    url=d.get('cover','')
    if url.startswith('http://'):url='https://'+url[7:]
    meta={'title':d.get('name'),'artist':d.get('artistName'),'description':d.get('desc'),'brief':d.get('briefDesc'),'source':'https://music.163.com/mv?id='+str(d.get('id','')),'review_scope':'平台MV介绍及单张封面；并非完整视频、逐帧审阅或音频听辨'}
    return {'cover_url':url,'has_cover':'yes' if url.startswith('https://') else 'no','meta':json.dumps(meta,ensure_ascii=False)}
