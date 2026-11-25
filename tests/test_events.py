import base64,json
import pytest
from sqlalchemy import select,func
from app.config import settings
from app.repositories.db import transaction,Workflow,Inbox,uid
from app.events import pubsub

@pytest.mark.asyncio
async def test_pubsub_durable_duplicate_ingress(client,monkeypatch):
    monkeypatch.setattr(settings(),'pubsub_audience','https://example.test/internal/pubsub')
    monkeypatch.setattr(settings(),'pubsub_service_account','push@example.test')
    monkeypatch.setattr(pubsub.id_token,'verify_oauth2_token',lambda *args:{'email':'push@example.test','email_verified':True})
    wid=uid()
    async with transaction(settings().tenant_id) as s:s.add(Workflow(id=wid,tenant=settings().tenant_id,kind='match',subject=uid()))
    event={'version':1,'event_id':'event1','workflow_id':wid}
    body={'message':{'data':base64.b64encode(json.dumps(event).encode()).decode()}}
    for _ in range(2):assert (await client.post('/internal/pubsub',json=body)).status_code==204
    async with transaction(settings().tenant_id) as s:assert await s.scalar(select(func.count()).select_from(Inbox))==1
    monkeypatch.setattr(pubsub.id_token,'verify_oauth2_token',lambda *args:{'email':'wrong@example.test','email_verified':True})
    assert (await client.post('/internal/pubsub',json=body)).status_code==401
