import json,unittest,re
from pathlib import Path
R=Path(__file__).parent
G=json.loads((R/'workflow-3.1.json').read_text());N={n['id']:n['data'] for n in G['workflow']['graph']['nodes']}
def fn(i):
 ns={};exec(N[i]['code'],ns);return ns['main']
class Regression(unittest.TestCase):
 def test_share_identity_and_user_text(self):
  for name,artist,link in [('Left Hand Suzuki Method','Gorillaz','https://163cn.tv/exampleA'),('And from this chasm, with ceaseless turmoil seething','Our Last Hope Lost Hope','https://163cn.tv/exampleB')]:
   d=fn('110')(f'分享{artist}的单曲《{name}》{link} (@网易云音乐)\n写实摄影，蓝色衣服，不要颗粒','');q=json.loads(d['request']);self.assertEqual(q['song_share_metadata'][0]['artist'],artist);self.assertEqual(q['song_share_metadata'][0]['title'],name);self.assertEqual(q['user_requirements_text'],'写实摄影，蓝色衣服，不要颗粒');self.assertEqual(json.loads(d['ref'])['kind'],'short')
 def test_escaped_share_url(self):
  d=fn('110')('分享A的单曲《B》https\\://163cn.tv/exampleB (@网易云音乐)','');self.assertEqual(json.loads(d['ref'])['kind'],'short');self.assertEqual(json.loads(d['request'])['user_requirements_text'],'')
 def test_only_link(self):
  d=fn('110')('https://music.163.com/song?id=22505333&userid=0','');self.assertEqual(json.loads(d['ref'])['id'],'22505333');self.assertEqual(json.loads(d['request'])['user_requirements_text'],'')
 def test_reasoning_json_and_conflict(self):
  d=fn('116')('<think>not JSON</think>```json\n'+json.dumps({'song_title':'x','constraints':[],'input_conflicts':['摄影与禁止摄影']})+'\n```','{"kind":"id","id":"22505333"}','');self.assertIn('冲突',d['error'])
 def test_comment_cap_and_creator(self):
  posts=[{'commentId':i,'content':'听感混乱','likedCount':100-i,'user':{'userId':i}} for i in range(1,20)]
  selected=[{'id':'19','text':'具体的氛围解析','priority':'creator_verified','kind':'creator_intent'}]
  for total in [499,500,501]:
   review={'selected_comments':selected,'comment_sampling':{'target':20,'selected':1,'shortfall':19}}
   r=fn('190')('{"songs":[{"id":22505333,"name":"Left Hand Suzuki Method","artists":[{"id":1,"name":"Gorillaz"}]}]}','{}',json.dumps({'total':total,'hotComments':posts}),'{"artist":{"accountId":19}}','{}','https://music.163.com/song?id=22505333','{}','{}','','{"title":"Left Hand Suzuki Method","artists":["Gorillaz"]}','{}','','','{}',json.dumps(review));e=json.loads(r['evidence']);self.assertEqual(len(e['selected_comments']),1);self.assertEqual(e['selected_comments'][0]['id'],'19');self.assertEqual(r['has_sources'],'yes');self.assertNotIn('supplementary_reference_notes',e);self.assertEqual(e['comment_sampling']['target'],20)
 def test_comment_filter_refill_and_cap(self):
  def posts(start,end):return [{'commentId':i,'content':'具体氛围描述'+str(i),'likedCount':500-i,'user':{'userId':i}} for i in range(start,end)]
  a=fn('240')('{"songs":[{"id":1,"name":"song"}]}',json.dumps({'total':999,'comments':posts(1,21)}),'{}')
  first={'decisions':[{'id':str(i),'useful':i<=7,'kind':'atmosphere','reason':'判别'} for i in range(1,21)]}
  b=fn('242')(a['state'],json.dumps(first));self.assertEqual(b['needs_more'],'yes')
  pages=[json.dumps({'total':999,'comments':posts(i,i+20)}) for i in [21,41,61,81]]
  c=fn('249')(b['state'],*pages);pool=json.loads(c['pool']);self.assertEqual(len(pool['comments']),80);self.assertEqual(pool['remaining'],13)
  second={'decisions':[{'id':str(i),'useful':True,'kind':'memory_imagery','visual_cues':'氛围'} for i in range(21,101)]+[{'id':'fake','useful':True,'kind':'atmosphere'}]}
  d=json.loads(fn('251')(c['state'],json.dumps(second))['result']);self.assertEqual(len(d['selected_comments']),20);self.assertEqual(d['comment_sampling']['semantically_reviewed'],100);self.assertEqual(d['comment_sampling']['shortfall'],0);self.assertTrue(d['comment_sampling']['errors']);self.assertNotIn('fake',[x['id'] for x in d['selected_comments']])
 def test_comment_shortage_and_model_failure(self):
  posts=[{'commentId':1,'content':'暗而温暖的感觉','user':{'userId':10}},{'commentId':2,'content':'暗而温暖的感觉','user':{'userId':11}}]
  a=fn('240')('{"songs":[{"id":1}]}',json.dumps({'total':2,'comments':posts}),'{"artist":{"accountId":10}}');self.assertEqual(len(json.loads(a['pool'])['comments']),1)
  b=fn('242')(a['state'],'not json');self.assertEqual(b['needs_more'],'no');d=json.loads(fn('244')(b['state'])['result']);self.assertEqual(d['comment_sampling']['selected'],0);self.assertEqual(d['comment_sampling']['shortfall'],20);self.assertTrue(d['comment_sampling']['errors'])
 def test_no_refill_when_twenty_are_useful(self):
  posts=[{'commentId':i,'content':'氛围'+str(i)} for i in range(1,21)]
  a=fn('240')('{"songs":[{"id":1}]}',json.dumps({'total':10000,'hotComments':posts}),'{}')
  raw=json.dumps({'decisions':[{'id':str(i),'useful':True,'kind':'musical_analysis'} for i in range(1,21)]})
  b=fn('242')(a['state'],raw);self.assertEqual(b['needs_more'],'no');d=json.loads(fn('244')(b['state'])['result']);self.assertEqual(d['comment_sampling']['selected'],20);self.assertFalse(d['comment_sampling']['refill_used'])
 def test_later_refill_until_twenty_and_failure_stop(self):
  def posts(start,n):return [{'commentId':i,'content':'音乐印象'+str(i)} for i in range(start,start+n)]
  def labels(items,keep):return json.dumps({'decisions':[{'id':p['id'],'useful':i<keep,'kind':'atmosphere'} for i,p in enumerate(items)]})
  a=fn('240')('{"songs":[{"id":123}]}',json.dumps({'total':999,'comments':posts(1,20)}),'{}')
  b=fn('242')(a['state'],labels(json.loads(a['pool'])['comments'],5))
  c=fn('249')(b['state'],*[json.dumps({'total':999,'comments':posts(i,20)}) for i in [21,41,61,81]])
  d=fn('251')(c['state'],labels(json.loads(c['pool'])['comments'],11));self.assertEqual(d['needs_more'],'yes');self.assertTrue(d['url0'].endswith('offset=100'))
  e=fn('266')(d['state'],*[json.dumps({'total':999,'comments':posts(i,20)}) for i in [101,121,141,161]])
  f=fn('268')(e['state'],labels(json.loads(e['pool'])['comments'],4));self.assertEqual(f['needs_more'],'no');self.assertEqual(json.loads(f['result'])['comment_sampling']['selected'],20);self.assertEqual(json.loads(f['result'])['comment_sampling']['refill_rounds'],2)
  failed=fn('266')(d['state'],'{}','{}','{}','{}');end=fn('268')(failed['state'],labels(json.loads(failed['pool'])['comments'],0));self.assertEqual(end['needs_more'],'no')
 def test_cover_missing_and_valid(self):
  self.assertEqual(fn('131')('{"songs":[{"album":{}}]}')['has_cover'],'no');self.assertEqual(fn('131')('{"songs":[{"album":{"picUrl":"http://p1.music.126.net/x.jpg"}}]}')['has_cover'],'yes');self.assertEqual(fn('131')('{"songs":[{"album":{"picUrl":"https://127.0.0.1/x"}}]}')['has_cover'],'no')
 def test_constraint_guard_and_final(self):
  i={'constraints':[{'id':'U1','dimension':'medium','quote':'写实油画','target':'全画面','strength':'required'}],'visual_details':['男孩在围墙上'],'mode':'detail_refine'}
  r=fn('210')(json.dumps({'selection':{'medium':'摄影','support_ids':[]}}),json.dumps(i));self.assertEqual(json.loads(r['style_data'])['user_contract'],i)
  raw={'sections':[{'title':'表现方式与媒介','text':'写实油画。'},{'title':'用户画面细化','text':'男孩在围墙上。'}],'review':{'status':'pass','checked_constraint_ids':['U1']}}
  final=fn('225')(json.dumps(raw),'detail_refine',json.dumps(i))['prompt'];self.assertIn('写实油画',final);self.assertIn('用户画面细化',final)
  raw['review']['checked_constraint_ids']=[]
  with self.assertRaises(ValueError):fn('225')(json.dumps(raw),'detail_refine',json.dumps(i))
 def test_graph_and_models(self):
  E=G['workflow']['graph']['edges'];adj={i:[] for i in N};degree={i:0 for i in N}
  for e in E:self.assertIn(e['source'],N);self.assertIn(e['target'],N);adj[e['source']].append(e['target']);degree[e['target']]+=1
  q=[i for i,x in degree.items() if x==0];count=0
  while q:
   i=q.pop();count+=1
   for t in adj[i]:
    degree[t]-=1
    if degree[t]==0:q.append(t)
  self.assertEqual(count,len(N));self.assertEqual(len(N['100']['variables']),2);self.assertFalse(any(n['type']=='knowledge-retrieval' for n in N.values()))
  for i,n in N.items():
   for v in n.get('variables',[]) if n['type']=='code' else []:
    s=v['value_selector'];self.assertIn(s[0],N)
    if N[s[0]]['type']=='code':self.assertIn(s[1],N[s[0]]['outputs'])
  b=json.loads((R/'baseline-online-3.0.json').read_text());old={n['id']:n['data'] for n in b['workflow']['graph']['nodes']}
  for i in ['115','176','200','220']:self.assertEqual(N[i]['model'],old[i]['model'])
if __name__=='__main__':unittest.main(verbosity=2)
