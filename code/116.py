import json,re
from urllib.parse import quote

def obj(raw):
    text=re.sub(r'<think>.*?</think>','',raw or '',flags=re.S).strip()
    text=re.sub(r'^```(?:json)?\s*','',text);text=re.sub(r'\s*```$','',text)
    try:d=json.loads(text)
    except Exception:
        pos=text.find('{')
        try:d=json.JSONDecoder().raw_decode(text[pos:])[0] if pos>=0 else None
        except Exception:d=None
    if not isinstance(d,dict):raise ValueError('意图解析格式异常；请重试。')
    return d

def main(raw:str,ref:str,input_error:str)->dict:
    d=obj(raw);r=json.loads(ref);title=str(d.get('song_title') or '').strip();artist=str(d.get('song_artist') or '').strip();error=input_error or ''
    if d.get('input_conflicts'):error=error or '画面要求存在冲突：'+json.dumps(d['input_conflicts'],ensure_ascii=False)+'。请明确希望采用哪一项。'
    d['constraints']=[x for x in d.get('constraints') or [] if isinstance(x,dict) and x.get('quote')]
    for i,c in enumerate(d['constraints']):c['id']='U'+str(i+1)
    if r['kind']=='id':url='https://music.163.com/api/song/detail/?id='+r['id']+'&ids=%5B'+r['id']+'%5D'
    elif r['kind']=='short':url=r['url']
    elif title:url='https://music.163.com/api/search/get?s='+quote(title+' '+artist)+'&type=1&limit=8&offset=0'
    else:url='https://music.163.com/api/search/get?s=__missing_song__&type=1&limit=1';error=error or '请提供歌曲名称或分享链接；song_url可以选填。'
    d['song_title']=title;d['song_artist']=artist
    return {'intent':json.dumps(d,ensure_ascii=False),'lookup_url':url,'error':error}
