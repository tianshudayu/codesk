import asyncio
import httpx
import uvicorn
from multiprocessing import Process
import time
from cloud_gateway.main import app as gateway_app
import os

PORT = 8901

def run_server():
    uvicorn.run(gateway_app, host='127.0.0.1', port=PORT, log_level='info')

async def test_agent():
    async with httpx.AsyncClient() as client:
        resp = await client.post(f'http://127.0.0.1:{PORT}/api/agent/register', json={'machineName':'test-desktop','platform':'Win'})
        identity = resp.json()
        device_id = identity['deviceId']
        agent_token = identity['agentToken']
        print(f'Registered device: {device_id}')

    os.environ['CODEX_CLOUD_URL'] = f'http://127.0.0.1:{PORT}'

    from bridge.main import build_runtime
    runtime = build_runtime(enable_relay=False, enable_cloud_agent=True)
    
    agent = runtime.cloud_agent
    from bridge.cloud_identity import CloudAgentIdentity
    agent._identity = CloudAgentIdentity(
        device_id=device_id,
        agent_token=agent_token,
        cloud_url=f'http://127.0.0.1:{PORT}'
    )
    agent._identity_store.load = lambda: agent._identity
    
    await runtime.service.start_background_tasks()
    
    task = asyncio.create_task(agent.start())
    await asyncio.sleep(2)
    
    print('Agent Connected Snapshot:', agent._snapshot.connected)
        
    await agent.close()
    await runtime.service.stop_background_tasks()
    await runtime.adapter.close()
    task.cancel()

if __name__ == '__main__':
    p = Process(target=run_server)
    p.start()
    time.sleep(2)
    try:
        asyncio.run(test_agent())
    finally:
        p.terminate()
