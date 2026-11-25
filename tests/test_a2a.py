import json
import pytest
from httpx import AsyncClient, ASGITransport
from google.protobuf.json_format import MessageToDict,ParseDict
from a2a.types import SendMessageRequest
from app.a2a.server import app,task_id
from app.config import settings
from app.privacy.pipeline import document

@pytest.mark.asyncio
async def test_a2a_exchange_replay_and_erase():
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://a2a',headers={'A2A-Version':'1.0','Authorization':'Bearer '+settings().a2a_token}) as c:
        card=await c.get('/.well-known/agent-card.json');assert card.status_code==200,card.text
        assert card.json()['supportedInterfaces'][0]['protocolVersion']=='1.0'
        payload={'operation_id':'test-operation','kind':'resume','payload':{'document':document('Built Python and FastAPI backend services.')}}
        request=ParseDict({'message':{'message_id':'message1','role':'ROLE_USER','parts':[{'data':payload,'media_type':'application/json'}]},'configuration':{'return_immediately':False}},SendMessageRequest())
        rpc={'jsonrpc':'2.0','id':'1','method':'SendMessage','params':MessageToDict(request)}
        first=await c.post('/rpc',json=rpc)
        assert first.status_code==200 and 'error' not in first.json(),first.text
        state=(await c.get('/internal/agent-operations/test-operation')).json()
        assert state['state']=='completed',state
        assert len(state['result']['skills'])==2
        again=await c.post('/rpc',json=rpc);assert 'error' not in again.json(),again.text
        same=(await c.get('/internal/agent-operations/test-operation')).json()
        assert same['remote_task_id']==state['remote_task_id']
        erased=await c.delete('/internal/agent-operations/test-operation/data');assert erased.json()['state']=='completed'
        late=await c.post('/rpc',json=rpc);assert 'error' in late.json()
        status=(await c.get('/internal/agent-operations/test-operation')).json();assert status['result'] is None
        unauthorized=await c.get('/internal/agent-operations/test-operation',headers={'Authorization':'Bearer bad'});assert unauthorized.status_code==401
