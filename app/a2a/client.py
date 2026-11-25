import httpx, json, hashlib
from uuid import uuid4
from google.protobuf.json_format import MessageToDict, ParseDict
from a2a.types import SendMessageRequest, AgentCard
from app.config import settings

async def call(kind,payload,operation_id):
    s=settings()
    async with httpx.AsyncClient(trust_env=False,base_url=s.a2a_url,headers={'A2A-Version':'1.0','Authorization':'Bearer '+s.a2a_token},timeout=s.max_run_seconds) as c:
        canonical=ParseDict({'message':{'parts':[{'data':{'operation_id':operation_id,'kind':kind,'payload':payload}}]}},SendMessageRequest())
        digest=hashlib.sha256(json.dumps(MessageToDict(canonical.message.parts[0],preserving_proto_field_name=True)['data'],sort_keys=True).encode()).hexdigest()
        # Reconcile before every submission, including recovery after timeout/restart.
        found=await c.get('/internal/agent-operations/'+operation_id)
        if found.status_code==200:
            state=found.json()
            if state['state']!='erased' and state['input_hash']!=digest:raise ValueError('OPERATION_PAYLOAD_CONFLICT')
            if state['state']=='completed':return state['result']
            if state['state']=='erased':raise ValueError('OPERATION_ERASED')
        elif found.status_code!=404:found.raise_for_status()
        card_response=await c.get('/.well-known/agent-card.json');card_response.raise_for_status()
        card=ParseDict(card_response.json(),AgentCard())
        if not any(i.protocol_binding=='JSONRPC' and i.protocol_version=='1.0' for i in card.supported_interfaces):raise ValueError('PROTOCOL_MISMATCH')
        # Configured origin only; never follow a card-provided arbitrary URL.
        request=ParseDict({'message':{'message_id':str(uuid4()),'role':'ROLE_USER','parts':[{'data':{'operation_id':operation_id,'kind':kind,'payload':payload},'media_type':'application/json'}]},'configuration':{'return_immediately':False}},SendMessageRequest())
        response=await c.post('/rpc',json={'jsonrpc':'2.0','id':str(uuid4()),'method':'SendMessage','params':MessageToDict(request)})
        response.raise_for_status()
        if 'error' in response.json():raise RuntimeError('REMOTE_AGENT_ERROR')
        result=await c.get('/internal/agent-operations/'+operation_id);result.raise_for_status()
        data=result.json()
        if data['state']!='completed':
            raise RuntimeError('REMOTE_PENDING_RECONCILE')
        return data['result']

async def erase_operations(ids):
    s=settings()
    async with httpx.AsyncClient(trust_env=False,base_url=s.a2a_url,headers={'A2A-Version':'1.0','Authorization':'Bearer '+s.a2a_token},timeout=30) as c:
        for id in ids:
            r=await c.delete('/internal/agent-operations/'+id+'/data');r.raise_for_status()
