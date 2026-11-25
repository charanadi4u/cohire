"""Exercise real HTTP API. Requires API + worker processes already running."""
import time, json, uuid, os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import httpx
from dotenv import load_dotenv
load_dotenv()
base=os.getenv('COHIRE_API_URL','http://127.0.0.1:8000')
client=httpx.Client(trust_env=False,base_url=base,headers={'Authorization':'Bearer '+os.environ['DEV_TOKEN']},timeout=30)
def post(path,**kwargs):
    r=client.post(path,headers={'Idempotency-Key':str(uuid.uuid4())},**kwargs);r.raise_for_status();return r.json()
def get(path):
    r=client.get(path);r.raise_for_status();return r.json()
def wait(id):
    for _ in range(180):
        row=get('/v1/workflows/'+id)
        if row['state'] in ('completed','partial'):return row
        if row['state'] in ('failed','canceled'):raise RuntimeError(row)
        time.sleep(1)
    raise TimeoutError(id)
def source(kind,name):
    data=Path('examples/'+name).read_bytes()
    upload=post('/v1/uploads/'+kind,files={'file':(name,data,'text/plain')})
    # These bundled SYNTHETIC fixtures have been manually reviewed; real documents need human review.
    text='\n'.join(x for x in data.decode().splitlines() if not x.startswith(('Name:','Email:')))
    queued=post(f"/v1/sources/{kind}/{upload['id']}/approve",json={'sanitized_text':text,'identity_removed':True})
    wait(queued['workflow_id']);return upload['id']
job=source('job','job.txt')
candidates=[source('resume',name) for name in ('resume_a.txt','resume_b.txt','resume_c.txt')]
profile=next(j for j in get('/v1/jobs') if j['id']==job)
weights={'python':.3,'fastapi':.3,'postgresql':.3,'gcp':.1}
post(f'/v1/jobs/{job}/approve',json={'weights':{r['id']:weights[r['term']] for r in profile['profile']['requirements']}})
run=post('/v1/runs',json={'job_id':job,'candidate_ids':candidates});wait(run['workflow_id'])
ranked=get('/v1/runs/'+run['workflow_id']+'/matches')
post('/v1/matches/'+ranked[0]['id']+'/review',json={'action':'advance','reason':'Evidence reviewed; proceed to a technical discussion.'})
post('/v1/matches/'+ranked[0]['id']+'/feedback',json={'label':'evidence_correct','note':'Synthetic example checked against supplied text.'})
proposals=get('/v1/proposals')
proposal=next(p for p in proposals if p['match_id']==ranked[0]['id'])
start=(datetime.now(timezone.utc)+timedelta(days=7)).replace(minute=0,second=0,microsecond=0)
post('/v1/proposals/'+proposal['id']+'/draft',json={'start':start.isoformat(),'end':(start+timedelta(minutes=45)).isoformat(),'timezone':'UTC'})
print(json.dumps({'run':run,'ranked':ranked,'proposals':get('/v1/proposals'),'analytics':get('/v1/analytics')},indent=2))
