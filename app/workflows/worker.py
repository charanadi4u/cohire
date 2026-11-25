"""Durable polling worker. Network calls run outside domain transactions."""
import asyncio, time, hashlib, json
from sqlalchemy import select, or_
from app.config import settings
from app.repositories.db import transaction, Workflow, Candidate, Job, Match, Proposal, Audit, uid
from app.agents.specialists import execute
from app.domain.scoring import score

async def invoke(kind,payload,operation_id):
    if settings().agent_transport=='a2a':
        from app.a2a.client import call
        return await call(kind,payload,operation_id)
    return await execute(kind,payload)

def projection(row): return {'document':row.document,'profile':row.profile,**({'rubric':row.rubric} if isinstance(row,Job) else {})}

async def process_one(tenant):
    cfg=settings(); stamp=time.time(); fence=uid()
    async with transaction(tenant) as s:
        q=select(Workflow).where(Workflow.tenant==tenant,or_(Workflow.state=='queued',(Workflow.state=='running')&(Workflow.lease_until<stamp))).order_by(Workflow.created).with_for_update(skip_locked=True)
        w=(await s.scalars(q)).first()
        if not w: return False
        if w.attempts>=cfg.max_attempts:
            w.state='failed'; w.error='RETRY_BUDGET_EXHAUSTED'; return True
        w.state='running'; w.attempts+=1; w.fence=fence; w.lease_until=stamp+cfg.max_run_seconds+30
        wid,kind,subject,payload=w.id,w.kind,w.subject,w.payload
    try:
        async with asyncio.timeout(cfg.max_run_seconds):
            if kind in ('resume','job'):
                model=Candidate if kind=='resume' else Job
                async with transaction(tenant) as s:
                    row=await s.get(model,subject)
                    if not row or row.tenant!=tenant or row.status!='queued': raise ValueError('SUBJECT_NOT_LIVE')
                    doc=row.document
                parsed=await invoke(kind,{'document':doc},wid)
                async with transaction(tenant) as s:
                    row=(await s.scalars(select(model).where(model.id==subject,model.tenant==tenant).with_for_update())).one()
                    w=(await s.scalars(select(Workflow).where(Workflow.id==wid,Workflow.tenant==tenant).with_for_update())).one()
                    if w.fence!=fence or w.state!='running': return True
                    if row.status!='queued': raise ValueError('SUBJECT_NOT_LIVE')
                    row.profile=parsed; row.status='ready' if kind=='resume' else 'draft'
                    w.result={'resource_id':subject}; w.state='completed'
            elif kind=='match':
                async with transaction(tenant) as s:
                    job=await s.get(Job,subject)
                    if not job or job.tenant!=tenant or job.status!='approved' or job.revision!=payload['job_revision']: raise ValueError('STALE_JOB')
                    jp=projection(job)
                failures=[]
                for cid in payload['candidate_ids']:
                    async with transaction(tenant) as s:
                        existing=(await s.scalars(select(Match).where(Match.tenant==tenant,Match.run_id==wid,Match.candidate_id==cid))).first()
                        if existing: continue
                        c=await s.get(Candidate,cid)
                        if not c or c.tenant!=tenant or c.status!='ready': failures.append(cid); continue
                        cp=projection(c)
                    try:
                        assessed=await invoke('match',{'job':jp,'candidate':cp},wid+':'+cid)
                        result=score(jp,cp,assessed)
                        result['provenance']={'mode':cfg.agent_mode,'model':cfg.gemini_match_model if cfg.agent_mode=='gemini' else 'deterministic-demo', 'prompt_version':'v1','schema_version':'v1','input_hash':hashlib.sha256(json.dumps([jp,cp],sort_keys=True).encode()).hexdigest()}
                    except ValueError:
                        failures.append(cid); continue
                    async with transaction(tenant) as s:
                        c=(await s.scalars(select(Candidate).where(Candidate.id==cid,Candidate.tenant==tenant).with_for_update())).one()
                        w=(await s.scalars(select(Workflow).where(Workflow.id==wid,Workflow.tenant==tenant).with_for_update())).one()
                        if w.fence!=fence or w.state!='running': return True
                        if c.status!='ready': failures.append(cid); continue
                        mid=uid()
                        s.add(Match(id=mid,tenant=tenant,run_id=wid,candidate_id=cid,job_id=subject,result=result))
                        if result['proposal_eligible']:
                            s.add(Proposal(tenant=tenant,match_id=mid,candidate_id=cid,details={'reason':'Threshold met; recruiter review required','external_action':False}))
                async with transaction(tenant) as s:
                    w=(await s.scalars(select(Workflow).where(Workflow.id==wid,Workflow.tenant==tenant).with_for_update())).one()
                    if w.fence==fence and w.state=='running':
                        w.state='partial' if failures else 'completed'; w.result={'failed_candidate_ids':failures,'evaluated':len(payload['candidate_ids'])-len(failures)}
            else: raise ValueError('UNKNOWN_WORKFLOW')
    except Exception as exc:
        async with transaction(tenant) as s:
            w=(await s.scalars(select(Workflow).where(Workflow.id==wid,Workflow.tenant==tenant).with_for_update())).one()
            if w.fence==fence and w.state=='running':
                w.error='VALIDATION_FAILED' if isinstance(exc,ValueError) else 'DEPENDENCY_FAILURE'
                w.state='failed' if isinstance(exc,ValueError) or w.attempts>=cfg.max_attempts else 'queued'
    return True

async def drain(tenant):
    while await process_one(tenant): 
        pass

async def main():
    while True:
        worked=await process_one(settings().tenant_id)
        if not worked: 
            await asyncio.sleep(1)
if __name__=='__main__': 
    asyncio.run(main())
