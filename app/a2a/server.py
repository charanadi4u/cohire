"""A2A 1.0 JSON-RPC service using a2a-sdk 1.3.0.
One tenant per service instance; bearer secret is a local integration credential.
"""
import hashlib, json, time, hmac
from uuid import uuid5, NAMESPACE_URL
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from google.protobuf.json_format import MessageToDict, ParseDict
from a2a import types as t
from a2a.server.agent_execution import AgentExecutor, RequestContext, RequestContextBuilder
from a2a.server.context import ServerCallContext
from a2a.server.tasks import TaskStore
from a2a.server.routes import create_jsonrpc_routes, create_agent_card_routes
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes.common import ServerCallContextBuilder
from sqlalchemy import select
from app.repositories.db import Operation, transaction, uid
from app.config import settings
from app.agents.specialists import execute

cfg=settings()
def task_id(op): return str(uuid5(NAMESPACE_URL,cfg.tenant_id+':'+op))
def pack(value):return MessageToDict(value,preserving_proto_field_name=True)
def unpack(data,cls):return ParseDict(data,cls())

class ContextBuilder(ServerCallContextBuilder):
    def build(self,request):return ServerCallContext(tenant=cfg.tenant_id,state={"headers":dict(request.headers)})

class StableContext(RequestContextBuilder):
    async def build(self,context,params=None,task_id=None,context_id=None,task=None):
        if params:
            if len(params.message.parts)!=1 or not params.message.parts[0].HasField('data'):raise ValueError('STRUCTURED_DATA_REQUIRED')
            data=pack(params.message.parts[0])['data']
            if set(data)!={'operation_id','kind','payload'} or len(data['operation_id'])>100:raise ValueError('INVALID_OPERATION')
            if data['kind'] not in ('resume','job','match','intent'):
                raise ValueError('INVALID_KIND')
            expected=globals()['task_id'](data['operation_id'])
            if task_id and task_id!=expected:raise ValueError('TASK_ID_MISMATCH')
            task_id=expected;context_id=expected
            digest=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
            async with transaction(cfg.tenant_id) as s:
                row=await s.get(Operation,task_id)
                if row:
                    if row.tenant!=cfg.tenant_id or row.state=='erased':raise ValueError('OPERATION_ERASED')
                    if row.digest!=digest:raise ValueError('OPERATION_CONFLICT')
                else:s.add(Operation(id=task_id,tenant=cfg.tenant_id,digest=digest,payload=data))
        return RequestContext(call_context=context,request=params,task_id=task_id,context_id=context_id,task=task)

class Store(TaskStore):
    async def save(self,task,context):
        async with transaction(cfg.tenant_id) as s:
            row=(await s.scalars(select(Operation).where(Operation.id==task.id,Operation.tenant==cfg.tenant_id).with_for_update())).first()
            if row and row.state!='erased':row.task=pack(task)
    async def get(self,task_id,context):
        async with transaction(cfg.tenant_id) as s:
            row=await s.get(Operation,task_id)
            if row and row.tenant==cfg.tenant_id and row.state!='erased' and row.task:return unpack(row.task,t.Task)
    async def list(self,params,context):
        # Listing is intentionally disabled; callers must know their operation ID.
        return t.ListTasksResponse(tasks=[],total_size=0)
    async def delete(self,task_id,context):
        async with transaction(cfg.tenant_id) as s:
            row=await s.get(Operation,task_id)
            if row and row.tenant==cfg.tenant_id:row.state='erased';row.payload={};row.result={};row.task={}

class Executor(AgentExecutor):
    async def execute(self,context,event_queue):
        id=context.task_id;fence=uid()
        async with transaction(cfg.tenant_id) as s:
            row=(await s.scalars(select(Operation).where(Operation.id==id,Operation.tenant==cfg.tenant_id).with_for_update())).one()
            if row.state=='erased':raise ValueError('ERASED')
            cached=row.result if row.state=='completed' else None
            if cached is None:
                if row.state=='running' and row.lease_until>time.time():raise ValueError('OPERATION_BUSY_RECONCILE')
                row.state='running';row.fence=fence;row.lease_until=time.time()+cfg.max_run_seconds+10
            data=row.payload
        if cached is None:
            result=await execute(data['kind'],data['payload'])
            async with transaction(cfg.tenant_id) as s:
                row=(await s.scalars(select(Operation).where(Operation.id==id,Operation.tenant==cfg.tenant_id).with_for_update())).one()
                if row.state=='erased' or row.fence!=fence:raise ValueError('STALE_OPERATION')
                row.result=result;row.state='completed'
        else:result=cached
        part=unpack({'data':result,'media_type':'application/json'},t.Part)
        task=t.Task(id=id,context_id=id,status=t.TaskStatus(state=t.TaskState.TASK_STATE_COMPLETED),artifacts=[t.Artifact(artifact_id=id,parts=[part])])
        # Persist before responding, so a lost response is recoverable via operation lookup.
        await Store().save(task,context.call_context)
        await event_queue.enqueue_event(task)
    async def cancel(self,context,event_queue):
        await Store().delete(context.task_id,context.call_context)
        await event_queue.enqueue_event(t.Task(id=context.task_id,context_id=context.context_id,status=t.TaskStatus(state=t.TaskState.TASK_STATE_CANCELED)))

card=unpack({'name':'CoHire specialists','description':'Sanitized resume/job extraction and evidence assessment; no side-effect tools.',
 'version':'0.1.0','supported_interfaces':[{'url':cfg.a2a_url+'/rpc','protocol_binding':'JSONRPC','protocol_version':'1.0'}],
 'capabilities':{'streaming':False,'push_notifications':False},'default_input_modes':['application/json'],'default_output_modes':['application/json'],
 'security_schemes':{'bearer':{'http_auth_security_scheme':{'scheme':'bearer'}}},
 'security_requirements':[{'schemes':{'bearer':{'list':[]}}}],
 'skills':[{'id':k,'name':k,'description':'Validated '+k+' specialist','tags':['recruitment']} for k in ('resume','job','match','intent')]},t.AgentCard)
app=FastAPI(title='CoHire A2A service')
@app.middleware('http')
async def auth(request:Request,call_next):
    token=request.headers.get('authorization','').removeprefix('Bearer ')
    if not cfg.a2a_token or not hmac.compare_digest(token,cfg.a2a_token):return JSONResponse(status_code=401,content={'detail':'UNAUTHORIZED'})
    if int(request.headers.get('content-length','0'))>1_000_000:return JSONResponse(status_code=413,content={'detail':'TOO_LARGE'})
    return await call_next(request)

@app.get('/internal/agent-operations/{op}')
async def lookup(op:str):
    async with transaction(cfg.tenant_id) as s:
        row=await s.get(Operation,task_id(op))
        if not row or row.tenant!=cfg.tenant_id:raise HTTPException(404,'NOT_FOUND')
        return {'operation_id':op,'input_hash':row.digest,'remote_task_id':row.id,'state':row.state,'result':row.result if row.state=='completed' else None}
@app.delete('/internal/agent-operations/{op}/data')
async def erase(op:str):
    id=task_id(op)
    async with transaction(cfg.tenant_id) as s:
        row=(await s.scalars(select(Operation).where(Operation.id==id,Operation.tenant==cfg.tenant_id).with_for_update())).first()
        if row:row.state='erased';row.payload={};row.result={};row.task={};row.fence=uid()
        else:s.add(Operation(id=id,tenant=cfg.tenant_id,state='erased',digest='',payload={}))
    return {'erasure_id':id,'state':'completed'}
@app.get('/internal/erasures/{id}')
async def erasure(id:str):
    async with transaction(cfg.tenant_id) as s:
        row=await s.get(Operation,id)
        if not row or row.tenant!=cfg.tenant_id or row.state!='erased':raise HTTPException(404,'NOT_FOUND')
        return {'erasure_id':id,'state':'completed','stores':['operation','task','artifact'],'sessions':'ephemeral per inference'}
class DeduplicatingHandler(DefaultRequestHandler):
    async def on_message_send(self,params,context):
        if len(params.message.parts)==1 and params.message.parts[0].HasField('data'):
            data=pack(params.message.parts[0])['data']
            if 'operation_id' in data:
                digest=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
                async with transaction(cfg.tenant_id) as s:
                    row=await s.get(Operation,task_id(data['operation_id']))
                    if row and row.tenant==cfg.tenant_id and row.digest==digest and row.state=='completed' and row.task:
                        return unpack(row.task,t.Task)
        return await super().on_message_send(params,context)

handler=DeduplicatingHandler(agent_executor=Executor(),task_store=Store(),agent_card=card,request_context_builder=StableContext())
app.router.routes.extend(create_agent_card_routes(card))
app.router.routes.extend(create_jsonrpc_routes(handler,'/rpc',context_builder=ContextBuilder(),enable_v0_3_compat=False))
