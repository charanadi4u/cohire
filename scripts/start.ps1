$ErrorActionPreference = 'Stop'
if (!(Test-Path '.venv\Scripts\python.exe')) { py -3.12 -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
& .\.venv\Scripts\python.exe -m pip install --no-deps -e .
if (!(Test-Path '.env')) { & .\.venv\Scripts\python.exe scripts\configure.py }
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m scripts.init_db
Write-Host 'Setup complete. Start API and worker using the README commands in separate terminals.'
