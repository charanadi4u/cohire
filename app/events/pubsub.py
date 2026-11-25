"""Transactional outbox relay and authenticated durable Pub/Sub ingress.
The domain polling worker remains the executor; push handlers never run models.
"""
import asyncio, base64, json
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import select
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from google.cloud import pubsub_v1
from app.config import settings
from app.repositories.db import transaction, Outbox, Inbox, Workflow
router=APIRouter()

async def publish_once():
    cfg=settings()
    if not cfg.pubsub_topic:raise ValueError('PUBSUB_TOPIC_REQUIRED')
    async with transaction(cfg.tenant_id) as s:
        events=(await s.scalars(select(Outbox).where(Outbox.tenant==cfg.tenant_id,Outbox.published==False).limit(100))).all()
        batch=[(e.id,e.workflow_id) for e in events]
    client=pubsub_v1.PublisherClient()
    for event_id,wid in batch:
        data=json.dumps({'version':1,'event_id':event_id,'workflow_id':wid}).encode()
        await asyncio.to_thread(lambda:client.publish(cfg.pubsub_topic,data).result(timeout=30))
        async with transaction(cfg.tenant_id) as s:
            row=await s.get(Outbox,event_id)
            if row and row.tenant==cfg.tenant_id:row.published=True
    return len(batch)

@router.post('/internal/pubsub',status_code=204)
async def ingress(request:Request):
    cfg=settings()
    if not cfg.pubsub_audience or not cfg.pubsub_service_account:raise HTTPException(503,'PUBSUB_NOT_CONFIGURED')
    try:
        token=request.headers.get('authorization','').removeprefix('Bearer ')
        claims=await asyncio.to_thread(id_token.verify_oauth2_token,token,GoogleRequest(),cfg.pubsub_audience)
        if claims.get('email')!=cfg.pubsub_service_account or not claims.get('email_verified'):raise ValueError()
    except Exception:raise HTTPException(401,'INVALID_PUSH_IDENTITY') from None
    raw=await request.body()
    if len(raw)>10000:raise HTTPException(413,'TOO_LARGE')
    try:
        envelope=json.loads(raw);data=json.loads(base64.b64decode(envelope['message']['data'],validate=True))
        if set(data)!={'version','event_id','workflow_id'} or data['version']!=1:raise ValueError()
    except Exception:raise HTTPException(422,'INVALID_EVENT') from None
    async with transaction(cfg.tenant_id) as s:
        w=await s.get(Workflow,data['workflow_id'])
        if not w or w.tenant!=cfg.tenant_id:raise HTTPException(404,'UNKNOWN_WORKFLOW')
        old=(await s.scalars(select(Inbox).where(Inbox.tenant==cfg.tenant_id,Inbox.event_id==data['event_id']))).first()
        if not old:s.add(Inbox(tenant=cfg.tenant_id,event_id=data['event_id']))
    # Ack only after commit. Duplicate concurrent inserts return 409; redelivery then acks.

if __name__=='__main__':
    print(asyncio.run(publish_once()))
