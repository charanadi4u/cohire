import uuid, json, time
from pathlib import Path
import pytest
from sqlalchemy import select
from app.config import settings
from app.repositories.db import transaction, Workflow, Candidate, Match, Idempotency
from app.workflows.worker import drain,process_one
from app.api.auth import Context,context
from app.api.main import app

async def post(client,path,body=None,key=None,**kw):
    return await client.post(path,json=body,headers={'Idempotency-Key':key or str(uuid.uuid4())},**kw)
async def source(client,kind,text):
    r=await post(client,'/v1/uploads/'+kind,files={'file':('source.txt',text.encode(),'text/plain')});assert r.status_code==201,r.text
    id=r.json()['id']
    sanitized='\n'.join(x for x in text.splitlines() if not x.startswith(('Name:','Email:')))
    r=await post(client,f'/v1/sources/{kind}/{id}/approve',{'sanitized_text':sanitized,'identity_removed':True});assert r.status_code==202,r.text
    await drain(settings().tenant_id)
    return id
async def setup(client):
    job=await source(client,'job',Path('examples/job.txt').read_text())
    candidates=[await source(client,'resume',Path('examples/'+n).read_text()) for n in ['resume_a.txt','resume_b.txt','resume_c.txt']]
    j=(await client.get('/v1/jobs')).json()[0]
    w={'python':.3,'fastapi':.3,'postgresql':.3,'gcp':.1}
    r=await post(client,f'/v1/jobs/{job}/approve',{'weights':{r['id']:w[r['term']] for r in j['profile']['requirements']}});assert r.status_code==200,r.text
    return job,candidates

@pytest.mark.asyncio
async def test_end_to_end(client):
    job,candidates=await setup(client)
    r=await post(client,'/v1/runs',{'job_id':job,'candidate_ids':candidates},key='run1');assert r.status_code==202,r.text
    run=r.json()['workflow_id'];await drain(settings().tenant_id)
    state=(await client.get('/v1/workflows/'+run)).json();assert state['state']=='completed',state
    ranked=(await client.get('/v1/runs/'+run+'/matches')).json()
    assert [round(x['score']) for x in ranked]==[100,60,0]
    assert [round(x['coverage'],1) for x in ranked]==[1,.6,0]
    assert all(x['review_required'] for x in ranked)
    assert ranked[-1]['score_upper_bound']==100
    proposals=(await client.get('/v1/proposals')).json();assert len(proposals)==1
    slot={'start':'2099-01-10T10:00:00+05:30','end':'2099-01-10T10:45:00+05:30','timezone':'Asia/Kolkata'}
    assert (await post(client,'/v1/proposals/'+proposals[0]['id']+'/draft',slot)).status_code==409
    assert (await post(client,'/v1/matches/'+ranked[0]['id']+'/review',{'action':'advance','reason':'Reviewed professional evidence.'})).status_code==200
    drafted=await post(client,'/v1/proposals/'+proposals[0]['id']+'/draft',slot)
    assert drafted.status_code==200 and drafted.json()['details']['external_action'] is False
    assert (await client.get('/v1/analytics')).json()['suppressed'] is True
    feedback=await post(client,'/v1/matches/'+ranked[0]['id']+'/feedback',{'label':'evidence_correct','note':'Fixture reviewed.'})
    assert feedback.json()['promotion']=='offline_review_only'
    again=await post(client,'/v1/runs',{'job_id':job,'candidate_ids':candidates},key='run1');assert again.json()['workflow_id']==run
    conflict=await post(client,'/v1/runs',{'job_id':job,'candidate_ids':[candidates[0]]},key='run1');assert conflict.status_code==409

@pytest.mark.asyncio
async def test_tenant_isolation_all_resources(client):
    job,candidates=await setup(client)
    r=await post(client,'/v1/runs',{'job_id':job,'candidate_ids':candidates});run=r.json()['workflow_id'];await drain(settings().tenant_id)
    ranked=(await client.get('/v1/runs/'+run+'/matches')).json()
    async def other():return Context('22222222-2222-4222-8222-222222222222','other',frozenset({'recruit','privacy','feedback','analytics'}))
    app.dependency_overrides[context]=other
    try:
        assert (await client.get('/v1/jobs')).json()==[]
        assert (await client.get('/v1/candidates')).json()==[]
        assert (await client.get('/v1/workflows/'+run)).status_code==404
        assert (await client.get('/v1/runs/'+run+'/matches')).status_code==404
        assert (await client.delete('/v1/candidates/'+candidates[0])).status_code==404
        assert (await post(client,'/v1/matches/'+ranked[0]['id']+'/review',{'action':'advance','reason':'Not authorized here.'})).status_code==404
        assert (await post(client,'/v1/runs',{'job_id':job,'candidate_ids':candidates})).status_code==404
    finally:app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_deletion_and_replay(client):
    job,cs=await setup(client)
    r=await post(client,'/v1/runs',{'job_id':job,'candidate_ids':cs});run=r.json()['workflow_id'];await drain(settings().tenant_id)
    assert (await client.delete('/v1/candidates/'+cs[0])).status_code==200
    assert (await client.delete('/v1/candidates/'+cs[0])).status_code==200
    assert len((await client.get('/v1/runs/'+run+'/matches')).json())==2
    assert (await client.get('/v1/proposals')).json()==[]
    assert (await post(client,'/v1/runs',{'job_id':job,'candidate_ids':[cs[0]]})).status_code==404

@pytest.mark.asyncio
async def test_deleted_while_matching(client,monkeypatch):
    job,cs=await setup(client)
    from app.workflows import worker
    original=worker.invoke
    async def delete_during(kind,payload,op):
        out=await original(kind,payload,op)
        await client.delete('/v1/candidates/'+cs[0]);return out
    monkeypatch.setattr(worker,'invoke',delete_during)
    r=await post(client,'/v1/runs',{'job_id':job,'candidate_ids':[cs[0]]});run=r.json()['workflow_id'];await drain(settings().tenant_id)
    assert (await client.get('/v1/runs/'+run+'/matches')).json()==[]
    assert (await client.get('/v1/workflows/'+run)).json()['state']=='canceled'

@pytest.mark.asyncio
async def test_expired_lease_recovers(client):
    job,cs=await setup(client)
    r=await post(client,'/v1/runs',{'job_id':job,'candidate_ids':cs});run=r.json()['workflow_id']
    async with transaction(settings().tenant_id) as s:
        w=await s.get(Workflow,run);w.state='running';w.attempts=1;w.lease_until=time.time()-1;w.fence='old-owner'
    await drain(settings().tenant_id)
    w=(await client.get('/v1/workflows/'+run)).json();assert w['state']=='completed' and w['attempts']==2

@pytest.mark.asyncio
async def test_privacy_gate_and_auth(client):
    assert (await client.get('/v1/jobs',headers={'Authorization':'Bearer invalid'})).status_code==401
    r=await post(client,'/v1/uploads/resume',files={'file':('resume.txt',b'Name: Example Person\nEmail: example@example.test\nBuilt Python API services.')})
    id=r.json()['id'];await drain(settings().tenant_id)
    rows=(await client.get('/v1/candidates')).json();assert rows[0]['status']=='privacy_review' and not rows[0]['document']
    r=await post(client,f'/v1/sources/resume/{id}/approve',{'sanitized_text':'Email: example@example.test\nBuilt Python services.','identity_removed':True})
    assert r.status_code==422

@pytest.mark.asyncio
async def test_model_malformed_is_not_committed(client,monkeypatch):
    from app.workflows import worker
    async def invalid(*args):raise ValueError('Malformed model output')
    monkeypatch.setattr(worker,'invoke',invalid)
    r=await post(client,'/v1/uploads/resume',files={'file':('r.txt',b'Built Python and FastAPI backend services.')});id=r.json()['id']
    r=await post(client,f'/v1/sources/resume/{id}/approve',{'sanitized_text':'Built Python and FastAPI backend services.','identity_removed':True})
    await drain(settings().tenant_id)
    assert (await client.get('/v1/workflows/'+r.json()['workflow_id'])).json()['state']=='failed'
    assert not (await client.get('/v1/candidates')).json()[0]['profile']

@pytest.mark.asyncio
async def test_rubric_immutable_and_cancel(client):
    job,cs=await setup(client)
    assert (await post(client,f'/v1/jobs/{job}/approve',{'weights':{'R1':1}})).status_code==409
    r=await post(client,'/v1/runs',{'job_id':job,'candidate_ids':cs});run=r.json()['workflow_id']
    await post(client,f'/v1/workflows/{run}/cancel');await drain(settings().tenant_id)
    assert (await client.get('/v1/workflows/'+run)).json()['state']=='canceled'

@pytest.mark.asyncio
async def test_upload_retry_after_deletion_does_not_resurrect(client):
    data=b'Name: Synthetic Person\nBuilt Python and FastAPI backend services.'
    first=await post(client,'/v1/uploads/resume',key='upload-stable',files={'file':('r.txt',data)})
    id=first.json()['id'];assert (await client.delete('/v1/candidates/'+id)).status_code==200
    again=await post(client,'/v1/uploads/resume',key='upload-stable',files={'file':('r.txt',data)})
    assert again.json()['id']==id
    assert (await client.get('/v1/candidates')).json()==[]

@pytest.mark.asyncio
async def test_raw_source_encrypted_and_not_in_domain(client):
    from app.repositories.db import VaultSession,Identity
    raw=b'Name: Synthetic Person\nEmail: private@example.test\nBuilt Python backend services.'
    r=await post(client,'/v1/uploads/resume',files={'file':('r.txt',raw)})
    async with VaultSession() as s:
        vault=await s.get(Identity,r.json()['id']);assert 'private@example.test' not in vault.encrypted
    async with transaction(settings().tenant_id) as s:
        c=await s.get(Candidate,r.json()['id']);assert c.document=={} and c.profile=={}
    assert 'private@example.test' not in (await client.get('/v1/candidates')).text
