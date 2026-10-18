import json,re
from urllib.parse import quote,urlencode

def main(details:str,intent:str)->dict:
    try:s=json.loads(details)['songs'][0]
    except Exception:raise ValueError('平台未返回歌曲资料，请检查链接。')
    d=json.loads(intent);artists=s.get('artists') or [];names=[a.get('name','') for a in artists];sid=str(s['id']);title=s.get('name','');refs=d.get('media_refs') or []
    media=' '.join(str(r.get('canonical_title') or r.get('input_name') or '') for r in refs if isinstance(r,dict))
    def instant(t):return 'https://api.duckduckgo.com/?'+urlencode({'q':t,'format':'json','no_html':1,'skip_disambig':1})
    artist_name=names[0] if names else '';aid=str((artists or [{}])[0].get('id',0))
    query='"'+artist_name+'" music album artwork illustrator visual artist official'
    return {'identity':json.dumps({'title':title,'artists':names,'media_candidates':refs},ensure_ascii=False),
      'lyrics_url':'https://music.163.com/api/song/lyric?id='+sid+'&lv=1&kv=1&tv=-1',
      'comments_url':'https://music.163.com/api/v1/resource/comments/R_SO_4_'+sid+'?limit=20&offset=0',
      'artist_url':'https://music.163.com/api/artist/'+aid,
      'artist_bio_url':'https://music.163.com/api/artist/introduction?id='+aid,
      'mv_search_url':'https://music.163.com/api/search/get?s='+quote(title+' '+' '.join(names))+'&type=1004&limit=5&offset=0',
      'relation_url':instant(media or title+' '+artist_name),
      'design_url':'https://www.artofthetitle.com/search.do?'+urlencode({'q':media or title,'submit':'Search'}),
      'culture_url':'https://www.bing.com/search?'+urlencode({'q':query,'format':'rss'}),
      'artist_context_url':'https://en.wikipedia.org/w/api.php?'+urlencode({'action':'query','titles':artist_name,'prop':'extracts|extlinks|info','explaintext':1,'exintro':1,'exchars':8000,'ellimit':30,'inprop':'url','format':'json','redirects':1}),
      'search_queries':json.dumps({'method':'公开平台艺人简介＋Bing RSS视觉文化候选＋Wikipedia艺人索引＋即时答案＋片头站内索引；均可失败降级','artist_visual_query':query,'media_reference':media,'scope':'摘要和百科只作线索；另读网页核验，均不等于审听或看视频'},ensure_ascii=False)}
