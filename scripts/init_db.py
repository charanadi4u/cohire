import asyncio
from app.repositories.db import vault_engine, VaultBase
async def main():
    async with vault_engine.begin() as c:await c.run_sync(VaultBase.metadata.create_all)
    await vault_engine.dispose()
if __name__=='__main__':asyncio.run(main())
