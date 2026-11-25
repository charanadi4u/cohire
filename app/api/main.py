import hashlib, json, math
from datetime import datetime
from zoneinfo import ZoneInfo
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, delete, func
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.api.auth import Context, require
from app.repositories.db import *
from app.domain.contracts import SourceApproval, RubricApproval, RunRequest, Review, Slot, Feedback
from app.privacy.pipeline import extract, preview, document, cipher

app=FastAPI(title='Co-Agent-Recruitment Hire',version='0.1.0',description='Recruiter decision support. Local/integration release. No autonomous employment decisions or outreach.')
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:3000','http://127.0.0.1:3000'],allow_methods=['GET','POST','DELETE'],allow_headers=['Authorization','Content-Type','Idempotency-Key'])

@app.exception_handler(ValueError)
async def validation_error(request,exc): return JSONResponse(status_code=422,content={'detail':'VALIDATION_FAILED','message':'Review the document, rubric or input. No model output was committed.'})
@app.exception_handler(IntegrityError)
async def conflict(request,exc): return JSONResponse(status_code=409,content={'detail':'CONCURRENT_REQUEST_RETRY_SAME_KEY'})

async def owned(s,model,id,ctx,lock=False):
    q=select(model).where(model.id==id,model.tenant==ctx.tenant)
    if lock:q=q.with_for_update()
    r=(await s.scalars(q)).first()
    if not r or (isinstance(r,Candidate) and r.status=='deleted'): raise HTTPException(404,'NOT_FOUND')
    return r

def audit(s,ctx,action,subject): s.add(Audit(tenant=ctx.tenant,actor=ctx.actor,action=action,subject=subject))
async def idem(s,ctx,route,key,body):
    if not key or len(key)>128: raise HTTPException(422,'IDEMPOTENCY_KEY_REQUIRED')
    digest=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
    r=(await s.scalars(select(Idempotency).where(Idempotency.tenant==ctx.tenant,Idempotency.actor==ctx.actor,Idempotency.route==route,Idempotency.key==key))).first()
    if r and r.digest!=digest: raise HTTPException(409,'IDEMPOTENCY_PAYLOAD_CONFLICT')
    return r,digest

def remember(s,ctx,route,key,digest,response):
    s.add(Idempotency(tenant=ctx.tenant,actor=ctx.actor,route=route,key=key,digest=digest,response=response))

def enqueue(s,ctx,kind,subject,payload=None):
    id=uid(); s.add(Workflow(id=id,tenant=ctx.tenant,kind=kind,subject=subject,payload=payload or {}))
    s.add(Outbox(tenant=ctx.tenant,workflow_id=id)); audit(s,ctx,'workflow_queued',id)
    return {'workflow_id':id,'resource_id':subject,'state':'queued'}

@app.get('/health')
async def health(): return {'status':'ok','mode':settings().agent_mode,'outreach':'draft'}

@app.post('/v1/uploads/{kind}',status_code=201)
async def upload(kind:str,file:UploadFile=File(...),ctx:Context=Depends(require('privacy')),idempotency_key:str=Header(...)):
    if kind not in ('resume','job'): raise HTTPException(422,'INVALID_KIND')
    data=await file.read(2_000_001); raw=extract(data,file.filename or '')
    route='upload/'+kind
    async with transaction(ctx.tenant) as s:
        old,digest=await idem(s,ctx,route,idempotency_key,{'sha256':hashlib.sha256(data).hexdigest()})
        if old: return old.response
        id=uid(); model=Candidate if kind=='resume' else Job
        # Raw text encrypted in the separate identity DB. Raw file bytes are not retained.
        async with VaultSession.begin() as vs:
            vs.add(Identity(id=id,tenant=ctx.tenant,encrypted=cipher().encrypt(raw.encode()).decode()))
        s.add(model(id=id,tenant=ctx.tenant))
        result={'id':id,'status':'privacy_review','sanitized_preview':preview(raw),'notice':'Manually remove names and indirect identifiers before approving. Scanned PDFs require transcription.'}
        # Do not cache source content in the general idempotency store.
        remember(s,ctx,route,idempotency_key,digest,{'id':id,'status':'privacy_review','preview_endpoint':f'/v1/sources/{kind}/{id}/preview'})
        audit(s,ctx,'upload',id)
        return result

@app.get('/v1/sources/{kind}/{id}/preview')
async def source_preview(kind:str,id:str,ctx:Context=Depends(require('privacy'))):
    if kind not in ('resume','job'):raise HTTPException(422,'INVALID_KIND')
    async with transaction(ctx.tenant) as s: await owned(s,Candidate if kind=='resume' else Job,id,ctx); audit(s,ctx,'privacy_preview',id)
    async with VaultSession() as vs:
        row=(await vs.scalars(select(Identity).where(Identity.id==id,Identity.tenant==ctx.tenant))).first()
        if not row: raise HTTPException(404,'SOURCE_NOT_FOUND')
        return {'sanitized_preview':preview(cipher().decrypt(row.encrypted.encode()).decode())}

@app.post('/v1/sources/{kind}/{id}/approve',status_code=202)
async def approve_source(kind:str,id:str,body:SourceApproval,ctx:Context=Depends(require('privacy')),idempotency_key:str=Header(...)):
    if kind not in ('resume','job'): raise HTTPException(422,'INVALID_KIND')
    route=f'approve-source/{kind}/{id}'
    async with transaction(ctx.tenant) as s:
        old,digest=await idem(s,ctx,route,idempotency_key,body.model_dump())
        if old:return old.response
        row=await owned(s,Candidate if kind=='resume' else Job,id,ctx,True)
        if row.status!='privacy_review':raise HTTPException(409,'SOURCE_ALREADY_FROZEN')
        row.document=document(body.sanitized_text); row.status='queued'
        result=enqueue(s,ctx,kind,id); remember(s,ctx,route,idempotency_key,digest,result)
        audit(s,ctx,'privacy_approved',id); return result

@app.get('/v1/jobs')
async def jobs(ctx:Context=Depends(require('recruit')),offset:int=0,limit:int=50):
    if not 0<=offset or not 1<=limit<=100:raise HTTPException(422,'INVALID_PAGE')
    async with transaction(ctx.tenant) as s:
        rows=(await s.scalars(select(Job).where(Job.tenant==ctx.tenant).order_by(Job.created).offset(offset).limit(limit))).all()
        return [{'id':r.id,'status':r.status,'profile':r.profile,'rubric':r.rubric,'revision':r.revision,'document':r.document} for r in rows]

@app.get('/v1/candidates')
async def candidates(ctx:Context=Depends(require('recruit')),offset:int=0,limit:int=50):
    if offset<0 or not 1<=limit<=100:raise HTTPException(422,'INVALID_PAGE')
    async with transaction(ctx.tenant) as s:
        rows=(await s.scalars(select(Candidate).where(Candidate.tenant==ctx.tenant,Candidate.status!='deleted').order_by(Candidate.created).offset(offset).limit(limit))).all()
        return [{'id':r.id,'status':r.status,'profile':r.profile,'document':r.document,'revision':r.revision} for r in rows]

@app.post('/v1/jobs/{id}/approve')
async def approve_job(id:str,body:RubricApproval,ctx:Context=Depends(require('recruit')),idempotency_key:str=Header(...)):
    route=f'rubric/{id}'
    async with transaction(ctx.tenant) as s:
        old,digest=await idem(s,ctx,route,idempotency_key,body.model_dump())
        if old:return old.response
        row=await owned(s,Job,id,ctx,True)
        if row.status!='draft':raise HTTPException(409,'RUBRIC_IMMUTABLE_CREATE_NEW_JOB')
        if any(r['necessity']=='unclear' for r in row.profile['requirements']):raise HTTPException(409,'CLARIFY_JOB_AND_REUPLOAD')
        if set(body.weights)!={r['id'] for r in row.profile['requirements']}:raise HTTPException(422,'WEIGHT_SET_MISMATCH')
        if any(not math.isfinite(w) or w<=0 for w in body.weights.values()):raise HTTPException(422,'INVALID_WEIGHTS')
        total=sum(body.weights.values()); row.rubric={k:v/total for k,v in body.weights.items()};row.status='approved'
        result={'id':id,'status':row.status,'rubric':row.rubric,'revision':row.revision}
        remember(s,ctx,route,idempotency_key,digest,result); audit(s,ctx,'rubric_approved',id);return result

@app.post('/v1/runs',status_code=202)
async def run(body:RunRequest,ctx:Context=Depends(require('recruit')),idempotency_key:str=Header(...)):
    async with transaction(ctx.tenant) as s:
        old,digest=await idem(s,ctx,'runs',idempotency_key,body.model_dump())
        if old:return old.response
        job=await owned(s,Job,body.job_id,ctx)
        if job.status!='approved':raise HTTPException(409,'JOB_NOT_APPROVED')
        if len(body.candidate_ids)>settings().max_candidates:raise HTTPException(422,'CANDIDATE_BUDGET')
        for cid in body.candidate_ids:
            c=await owned(s,Candidate,cid,ctx)
            if c.status!='ready':raise HTTPException(409,'CANDIDATE_NOT_READY')
        result=enqueue(s,ctx,'match',job.id,{**body.model_dump(),'job_revision':job.revision})
        remember(s,ctx,'runs',idempotency_key,digest,result);return result

@app.get('/v1/workflows/{id}')
async def workflow(id:str,ctx:Context=Depends(require('recruit'))):
    async with transaction(ctx.tenant) as s:
        w=await owned(s,Workflow,id,ctx)
        return {'id':w.id,'state':w.state,'attempts':w.attempts,'error':w.error,'result':w.result}

@app.post('/v1/workflows/{id}/cancel')
async def cancel(id:str,ctx:Context=Depends(require('recruit'))):
    async with transaction(ctx.tenant) as s:
        w=await owned(s,Workflow,id,ctx,True)
        if w.state in ('queued','running'):w.state='canceled';w.fence=uid()
        audit(s,ctx,'workflow_canceled',id);return {'state':w.state}

@app.get('/v1/runs/{id}/matches')
async def matches(id:str,ctx:Context=Depends(require('recruit'))):
    async with transaction(ctx.tenant) as s:
        await owned(s,Workflow,id,ctx)
        rows=(await s.scalars(select(Match).join(Candidate,Candidate.id==Match.candidate_id).where(Match.tenant==ctx.tenant,Match.run_id==id,Candidate.tenant==ctx.tenant,Candidate.status=='ready'))).all()
        rows=sorted(rows,key=lambda r:(-r.result['score'],-r.result['coverage'],r.candidate_id))
        for r in rows:audit(s,ctx,'recommendation_shown',r.id)
        return [{'id':r.id,'candidate_id':r.candidate_id,**r.result} for r in rows]

@app.post('/v1/matches/{id}/review')
async def review(id:str,body:Review,ctx:Context=Depends(require('recruit')),idempotency_key:str=Header(...)):
    route=f'review/{id}'
    async with transaction(ctx.tenant) as s:
        old,digest=await idem(s,ctx,route,idempotency_key,body.model_dump())
        if old:return old.response
        m=await owned(s,Match,id,ctx);await owned(s,Candidate,m.candidate_id,ctx,True)
        d=Decision(id=uid(),tenant=ctx.tenant,match_id=id,actor=ctx.actor,action=body.action,reason=body.reason);s.add(d)
        result={'decision_id':d.id,'action':body.action};remember(s,ctx,route,idempotency_key,digest,result);audit(s,ctx,'review_'+body.action,id);return result

@app.get('/v1/proposals')
async def proposals(ctx:Context=Depends(require('recruit'))):
    async with transaction(ctx.tenant) as s:
        rows=(await s.scalars(select(Proposal).where(Proposal.tenant==ctx.tenant))).all()
        return [{'id':r.id,'match_id':r.match_id,'candidate_id':r.candidate_id,'status':r.status,'details':r.details} for r in rows]

@app.post('/v1/proposals/{id}/draft')
async def draft(id:str,body:Slot,ctx:Context=Depends(require('recruit'))):
    try:
        start=datetime.fromisoformat(body.start);end=datetime.fromisoformat(body.end);ZoneInfo(body.timezone)
        if start.tzinfo is None or end.tzinfo is None or not 900<=(end-start).total_seconds()<=7200:raise ValueError()
        if start.timestamp()<=datetime.now().timestamp():raise ValueError()
    except Exception:raise HTTPException(422,'INVALID_FUTURE_AWARE_SLOT') from None
    async with transaction(ctx.tenant) as s:
        p=await owned(s,Proposal,id,ctx,True);await owned(s,Candidate,p.candidate_id,ctx,True)
        latest=(await s.scalars(select(Decision).where(Decision.tenant==ctx.tenant,Decision.match_id==p.match_id).order_by(Decision.created.desc()))).first()
        if not latest or latest.action!='advance':raise HTTPException(409,'RECRUITER_ADVANCE_REQUIRED')
        p.details={**body.model_dump(),'message':'We would like to discuss your professional experience. Please confirm whether this proposed time works for you.',
                   'candidate_confirmation':'pending','calendar_status':'not_booked','external_action':False,'approved_by':ctx.actor}
        p.status='awaiting_candidate_confirmation';audit(s,ctx,'interview_drafted',id)
        return {'id':id,'status':p.status,'details':p.details}

@app.post('/v1/matches/{id}/feedback')
async def feedback(id:str,body:Feedback,ctx:Context=Depends(require('feedback')),idempotency_key:str=Header(...)):
    route=f'feedback/{id}'
    async with transaction(ctx.tenant) as s:
        old,digest=await idem(s,ctx,route,idempotency_key,body.model_dump())
        if old:return old.response
        m=await owned(s,Match,id,ctx);await owned(s,Candidate,m.candidate_id,ctx)
        f=FeedbackRow(id=uid(),tenant=ctx.tenant,match_id=id,actor=ctx.actor,data={**body.model_dump(),'provenance':m.result['provenance']});s.add(f)
        result={'id':f.id,'promotion':'offline_review_only'};remember(s,ctx,route,idempotency_key,digest,result);return result

@app.get('/v1/analytics')
async def analytics(ctx:Context=Depends(require('analytics'))):
    async with transaction(ctx.tenant) as s:
        n=await s.scalar(select(func.count()).select_from(Candidate).where(Candidate.tenant==ctx.tenant,Candidate.status=='ready'))
        if n<5:return {'suppressed':True,'minimum_cohort':5,'metrics':None}
        runs=await s.scalar(select(func.count()).select_from(Workflow).where(Workflow.tenant==ctx.tenant,Workflow.kind=='match'))
        return {'suppressed':False,'metrics':{'active_candidates':n,'match_runs':runs},'scope':'current tenant; all retained history','interpretation':'Descriptive counts only; no causal hiring conclusions.'}

@app.get('/v1/audit')
async def audit_log(ctx:Context=Depends(require('recruit'))):
    async with transaction(ctx.tenant) as s:
        rows=(await s.scalars(select(Audit).where(Audit.tenant==ctx.tenant).order_by(Audit.created.desc()).limit(100))).all()
        return [{'action':r.action,'subject':r.subject,'actor':r.actor,'at':r.created} for r in rows]

@app.delete('/v1/candidates/{id}')
async def erase(id:str,ctx:Context=Depends(require('privacy'))):
    # Tombstone first; retries also finish vault cleanup after a partial failure.
    async with transaction(ctx.tenant) as s:
        c=(await s.scalars(select(Candidate).where(Candidate.id==id,Candidate.tenant==ctx.tenant).with_for_update())).first()
        if not c:raise HTTPException(404,'NOT_FOUND')
        c.status='deleted';c.document={};c.profile={};c.consent=False
        mids=list(await s.scalars(select(Match.id).where(Match.tenant==ctx.tenant,Match.candidate_id==id)))
        for model in (Decision,FeedbackRow):await s.execute(delete(model).where(model.tenant==ctx.tenant,model.match_id.in_(mids)))
        await s.execute(delete(Match).where(Match.tenant==ctx.tenant,Match.candidate_id==id))
        await s.execute(delete(Proposal).where(Proposal.tenant==ctx.tenant,Proposal.candidate_id==id))
        flows=(await s.scalars(select(Workflow).where(Workflow.tenant==ctx.tenant))).all()
        operation_ids=[]
        for w in flows:
            if w.subject==id or id in w.payload.get('candidate_ids',[]):
                operation_ids.append(w.id if w.kind=='resume' else w.id+':'+id)
                if w.state in ('queued','running'):w.state='canceled';w.fence=uid()
        # Keep minimal idempotency receipts so old upload keys cannot recreate deleted subjects.
        audit(s,ctx,'candidate_erased',id)
    if settings().agent_transport=='a2a':
        from app.a2a.client import erase_operations
        await erase_operations(operation_ids)
    async with VaultSession.begin() as vs:
        await vs.execute(delete(Identity).where(Identity.id==id,Identity.tenant==ctx.tenant))
    return {'id':id,'status':'deleted','remote_cleanup':'completed','backup_policy':'Replay tombstones before serving a restored backup.'}

from app.events.pubsub import router as pubsub_router
app.include_router(pubsub_router)
