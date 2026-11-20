#!/usr/bin/env python3
"""Replay saved typed plans through the full pipeline, with no model (Era 2, Step 9, Phase F).

The drafter is a stub that returns each variant row's saved typed plan, rebuilt
the way ``typed.to_plan`` builds it: ``from_step`` and the join key are
inferred, since variant rows do not record them. Everything after the drafter
runs as in a measured arm, against the stores in ``.env``. The ids it returns
are compared **tree to tree**: run it on this tree and on a pre-change worktree
over the same store state, never against committed answers (memory: typed plan
replay). Multi-producer plans (F-FAN) stay ambiguous.

    uv run python scripts/algebra_pipeline_replay.py <variants dir> <arm> <out.json> [--workers N] [--only CASE:TIER,...]

Promoted from the 2026-11-20 session scratchpad (diag/pipe_replay.py), unchanged in logic.
"""
import json,sys,os,re,dataclasses
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,'.')
import scripts.variant_harness as VH
for k,v in VH.BASE_ENV.items(): os.environ[k]=v
os.environ.update(VH.REWRITE_ENV['off'])
from utils.config import load_env
from utils.planner.schema import Plan, SubQuestion, Limits, JoinDeclaration
from utils.synthesis.config import SynthesisConfig
vdir,arm,out=sys.argv[1],sys.argv[2],sys.argv[3]
workers=int(sys.argv[sys.argv.index('--workers')+1]) if '--workers' in sys.argv else 6
only=set(sys.argv[sys.argv.index('--only')+1].split(',')) if '--only' in sys.argv else None
rows=[r for r in json.load(open(os.path.join(vdir,arm+'.json'))) if 'records_exact' in r]
if only: rows=[r for r in rows if f"{r['case_id']}:{r['tier']}" in only]
ref={x['case_id']:x for x in json.load(open(os.path.join(vdir,'reference.json')))}
KEY='attack-technique-id'
def build(r):
    plan=Plan(request=r['question'])
    sqs=[SubQuestion(id=f"q{i}",source=p['source'],text="",entities=p['entities'],limits=Limits(3,1000,5000),
                     rationale="typed plan (replay)",step=dict(p['step'])) for i,p in enumerate(r['planner']['plan'],1)]
    for i,sq in enumerate(sqs):
        a=sq.step.get('anchor_ids') or []
        if sq.step.get('kind')!='scan' and not a:
            cands=[p for p in reversed(sqs[:i]) if p.source!=sq.source]
            prod=next((p for p in cands if any(h.get('relation')=='MAPS_TO' for h in p.step.get('hops',[]))),None) or (cands[0] if cands else None)
            if prod:
                sq.step['from_step']=prod.id
                plan.joins.append(JoinDeclaration(key=KEY,sources=[prod.source,sq.source],on=''))
                sqs[i]=dataclasses.replace(sq,join_key=KEY)
                j=sqs.index(prod); sqs[j]=dataclasses.replace(sqs[j],join_key=sqs[j].join_key or KEY)
        foreign=(sq.source=='capec' and any(re.match(r'^T\d{4}',x) for x in a)) or (sq.source=='attack' and any(x.upper().startswith('CAPEC') for x in a))
        if foreign: sqs[i]=dataclasses.replace(sqs[i],join_key=KEY)
    if '--drop' in sys.argv:
        used={sq.step.get('from_step') for sq in sqs}
        keep=[]
        for sq in sqs:
            st=sq.step
            if st.get('kind')=='describe' and st.get('from_step') and sq.id not in used and any(
                o is not sq and o.source==sq.source and o.step.get('from_step')==st.get('from_step') and o.step.get('hops')
                and o.step.get('anchor_label')==st.get('anchor_label') for o in sqs):
                continue
            keep.append(sq)
        sqs=keep
    plan.sub_questions=sqs
    plan.assumptions=["typed plan (replay)"]
    return plan
class Stub:
    def __init__(self,plan): self.plan=plan; self.last_used='TypedDrafter'; self.logs=[]
    def draft(self,request,cards,live_view,feedback=None,intent=None):
        p=dataclasses.replace(self.plan,sub_questions=list(self.plan.sub_questions),joins=list(self.plan.joins))
        p.typed={'mode':'replay'}
        return p
def agent_for(plan):
    from utils.planner.agent import PlanningAgent
    from utils.planner.config import PlannerConfig
    from utils.specialists.config import SpecialistConfig
    config=dataclasses.replace(PlannerConfig.from_env(), llm_enabled=True)
    spec=dataclasses.replace(SpecialistConfig.from_env(), llm_enabled=False, llm_query_builder=False)
    return PlanningAgent(config, drafter=Stub(plan)), spec
cfg=dataclasses.replace(SynthesisConfig.from_env(), llm_enabled=False)
def one(r):
    if not r['planner']['plan'] or not all(p.get('step') for p in r['planner']['plan']):
        return None
    plan=build(r)
    VH_local={}
    agent,spec=agent_for(plan)
    orig=VH._planner_agent
    got=None
    try:
        from utils.orchestration.main import PipelineRun, iter_pipeline
        run=PipelineRun(question=r['question'],mode='query'); evidence=None
        for ev,payload in iter_pipeline(r['question'],mode='query',run=run,synthesis_config=cfg,use_llm=True,agent=agent,specialist_config=spec):
            if ev=='evidence': evidence=payload.get('evidence')
            elif ev=='answer': evidence=payload.get('evidence') or evidence
        ids=set(); recs=0; qs=[]
        for res in getattr(evidence,'results',[]) or []:
            ids|=VH._entity_ids(res); recs+=len(res.records or [])
            if res.query: qs.append(VH._norm_query(res.query))
    except Exception as e:
        return {'key':[r['case_id'],r['tier'],r['question']],'error':repr(e)[:300]}
    s=VH.score({'entity_ids':sorted(ids),'record_count':recs,'abstentions':r['abstentions']},ref[r['case_id']])
    return {'key':[r['case_id'],r['tier'],r['question']],'entity_ids':sorted(ids),'record_count':recs,'queries':sorted(qs),
            'old_exact':r['records_exact'],'old_wrong':r['wrong_entity'],'old_abst':r['abstained'],'old_ids':r['entity_ids'],'old_queries':r['queries'],**s}
with ThreadPoolExecutor(workers) as ex:
    res=[x for x in ex.map(one,rows) if x]
json.dump(res,open(out,'w'))
c=Counter()
for x in res:
    if 'error' in x: c['error']+=1; continue
    c['same_ids']+= x['entity_ids']==x['old_ids']
    c['now_exact']+=x['records_exact']; c['was_exact']+=x['old_exact']
    c['gained']+= x['records_exact'] and not x['old_exact']; c['lost']+= x['old_exact'] and not x['records_exact']
    c['cw_now']+= x['wrong_entity'] and not x['abstained']; c['cw_was']+= x['old_wrong'] and not x['old_abst']
print(arm,len(res),dict(c))
