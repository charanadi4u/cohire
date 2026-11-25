"""Create local secrets once. Never overwrite an existing .env."""
from pathlib import Path
import secrets
from cryptography.fernet import Fernet
p=Path('.env')
if p.exists():raise SystemExit('.env exists; edit it directly.')
p.write_text('ENVIRONMENT=local\nDEV_AUTH=true\nDEV_TOKEN='+secrets.token_urlsafe(32)+'\nIDENTITY_KEY='+Fernet.generate_key().decode()+'\nDATABASE_URL=sqlite+aiosqlite:///./cohire.db\nIDENTITY_DATABASE_URL=sqlite+aiosqlite:///./identity.db\nAGENT_MODE=demo\nAGENT_TRANSPORT=local\nA2A_TOKEN='+secrets.token_urlsafe(32)+'\nOUTREACH_MODE=draft\n',encoding='utf-8')
print('Created .env with independent local secrets. Keep it private.')
