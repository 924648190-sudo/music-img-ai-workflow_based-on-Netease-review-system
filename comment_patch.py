"""3.1 comment-only patch. Called by the existing build_31.py entry point."""
import copy
from pathlib import Path

def apply(out):
    root=Path(__file__).parent;g=out['workflow']['graph'];nodes=g['nodes'];edges=g['edges'];N={n['id']:n for n in nodes}
    core=(root/'code/comments_filter.py').read_text();filter_prompt=(root/'prompts/comment_filter.md').read_text().rstrip()
    def var(name,n,key):return {'variable':name,'value_selector':[n,key],'value_type':'string'}
    def node(i,template,title,x,y):
        n=copy.deepcopy(N[template]);n.update(id=i,position={'x':x,'y':y},positionAbsolute={'x':x,'y':y},selected=False)
        n['data'].update(title=title,selected=False);nodes.append(n);N[i]=n;return n['data']
    def edge(a,b,handle='source'):
        edges.append({'id':a+'-'+handle+'-'+b,'source':a,'target':b,'sourceHandle':handle,'targetHandle':'target','type':'custom',
            'data':{'sourceType':N[a]['data']['type'],'targetType':N[b]['data']['type'],'isInIteration':False,'isInLoop':False}})
    def code(i,title,func,args,outputs,x,y):
        d=node(i,'110',title,x,y);names=','.join(a[0] for a in args)
        d['code']=core+'\ndef main('+','.join(a[0]+':str' for a in args)+')->dict:\n    result='+func+'('+names+')\n    return {k:result[k] for k in '+repr(outputs)+'}\n'
        d['variables']=[var(*a) for a in args];d['outputs']={k:{'type':'string','children':None} for k in outputs};return d
    def llm(i,title,pool,x,y):
        d=node(i,'115',title,x,y);d['prompt_template']=[{'id':i+'-sys','role':'system','text':filter_prompt},
            {'id':i+'-user','role':'user','text':'评论候选：{{#'+pool+'.pool#}}'}]
        d['error_strategy']='default-value';d['default_value']=[{'key':'text','type':'string','value':'{"decisions":[]}'}]
        d['desc']='语义筛选，不在此生成综合总结；异常时不把未经分析的评论算作有效。'
    # 首轮只审20条，只有未满20条有效样本才读取余下4页。最终输出仍只有Prompt。
    N['130']['data']['code']=N['130']['data']['code'].replace('?limit=15&offset=0','?limit=20&offset=0')
    N['150']['data']['title']='评论首批候选 · 每页20条'
    code('240','评论候选去重与优先级 · 首批20条','initial',[('details','126','body'),('comments','150','body'),('artist','160','body')],['pool','state','url0','url1','url2','url3'],3100,-1700)
    llm('241','评论内容筛选 · 首批','240',3450,-1700)
    code('242','核验有效样本与补采缺口','first_review',[('state','240','state'),('raw','241','text')],['state','needs_more'],3800,-1700)
    d=node('243','174','有效评论不足20条？',4150,-1700);d['cases'][0]['conditions'][0].update(variable_selector=['242','needs_more'],id='243-c')
    code('244','已足量或无更多评论','finish',[('state','242','state')],['result'],4500,-1500)
    for i,offset in enumerate([20,40,60,80]):
        key=str(245+i);d=node(key,'150','按需补采评论 · offset '+str(offset),4500,-1900-i*170);d['url']='{{#240.url'+str(i)+'#}}'
        edge('243',key,'true')
    code('249','补采候选去重 · 最多再审80条','refill',[('state','242','state')]+[('page'+str(i),str(245+i),'body') for i in range(4)],['pool','state'],4850,-1800)
    for i in range(4):edge(str(245+i),'249')
    llm('250','评论内容筛选 · 补足有效样本','249',5200,-1800)
    finish_outputs=['result','state','needs_more','url0','url1','url2','url3']
    code('251','有效评论收束 · 首轮补采','finish',[('state','249','state'),('raw','250','text')],finish_outputs,5550,-1800)
    done=[['244','result']];prev='251'
    # 最多3轮按需补采；每轮结束先判断，已满20不继续。末轮如实返回缺口。
    for round_no,start in [(2,260),(3,280)]:
        condition=str(start);carry=str(start+1);prep=str(start+6);selector=str(start+7);end=str(start+8)
        d=node(condition,'174','有效评论仍不足？ · 第'+str(round_no)+'轮',5900+(round_no-2)*1500,-1800)
        d['cases'][0]['conditions'][0].update(variable_selector=[prev,'needs_more'],id=condition+'-c');edge(prev,condition)
        code(carry,'有效评论已满或补采结束 · '+str(round_no),'finish',[('state',prev,'state')],['result'],6200+(round_no-2)*1500,-1500);edge(condition,carry,'false');done.append([carry,'result'])
        for i in range(4):
            key=str(start+2+i);d=node(key,'150','补采第'+str(round_no)+'轮 · 页'+str(i+1),6200+(round_no-2)*1500,-1950-i*150)
            d['url']='{{#'+prev+'.url'+str(i)+'#}}';edge(condition,key,'true')
        code(prep,'后续补采去重 · 第'+str(round_no)+'轮','refill',[('state',prev,'state')]+[('page'+str(i),str(start+2+i),'body') for i in range(4)],['pool','state'],6550+(round_no-2)*1500,-1800)
        for i in range(4):edge(str(start+2+i),prep)
        llm(selector,'评论语义筛选 · 第'+str(round_no)+'轮',prep,6900+(round_no-2)*1500,-1800);edge(prep,selector)
        code(end,'有效评论收束 · 第'+str(round_no)+'轮','finish',[('state',prep,'state'),('raw',selector,'text')],finish_outputs,7250+(round_no-2)*1500,-1800);edge(selector,end);prev=end
    done.append([prev,'result'])
    d=node('255','178','有效评论汇合',9200,-1500);d['variables']=done
    for n,_ in done:edge(n,'255')
    for a,b in [('150','240'),('160','240'),('240','241'),('241','242'),('242','243'),('249','250'),('250','251'),('255','190')]:edge(a,b)
    edge('243','244','false')
    # 保留已有来源检索/MV功能；仅替换送入Step-1的评论为经过筛选的真实原文。
    d=N['190']['data'];d['variables'].append(var('comment_review','255','output'))
    d['code']=d['code'].replace('cap=10 if total<=500 else 15','cap=20')
    d['code']=d['code'].replace('artist_bio:str)->dict:', 'artist_bio:str,comment_review:str)->dict:')
    insertion="""    filtered=obj(comment_review)
    evidence['selected_comments']=filtered.get('selected_comments') or []
    evidence['comment_sampling']=filtered.get('comment_sampling') or {'target':20,'selected':0,'status':'filter_unavailable'}
    evidence['comment_filter_audit']='完整逐条筛选记录保留在有效评论汇合节点；此处只提供有效原文，避免拒绝内容污染风格总结。'
"""
    d['code']=d['code'].replace("    for post in evidence.get('selected_comments',[]):",insertion+"    for post in evidence.get('selected_comments',[]):")
    d['code']=d['code'].replace("refs['sampling']=json.dumps({'selected':c['sample_count'],'cap':c['sample_cap'],'author_candidates':json.loads(c['author_candidates'])},ensure_ascii=False)","refs['sampling']=json.dumps(evidence['comment_sampling'],ensure_ascii=False)")
    d['title']='有效评论、艺人背景与可信网页筛选';d['desc']='有效评论最多20条；不足才补采，最多3轮、每轮4页；达到20立即停止，最多审260条，不足如实记录。'
    addition='\n评论已由独立筛选器按有效性去重与补采，最多20条有效原文。仅总结selected_comments，不能把comment_filter_decisions中的拒绝项重新使用；不因未满20而编造。综合comment_summary须包含selected_count、主要氛围/情绪、音乐性听感线索、风格文化待核线索及分歧；每项附support_comment_ids。memory_imagery仅转译为氛围，不把听众的私人场景变成主体；听感、文化关联仍须遵守原证据边界。'
    N['200']['data']['prompt_template'][0]['text']+=addition
    N['215']['data']['prompt_template'][0]['text']+='\n复核comment_summary只使用入选评论ID；被筛掉的评论不能重新支撑风格，不能将20条样本说成听众共识。'
    out['app']['description']='3.1：分维度用户约束、文化与封面审阅、最多20条有效评论语义筛选及按需补采、独立风格审查。RAG未接入。'
