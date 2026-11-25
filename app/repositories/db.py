from contextlib import asynccontextmanager
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy import String, Text, JSON, Integer, Float, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import settings

def uid(): return str(uuid4())
def now(): return datetime.now(timezone.utc).isoformat()
class Base(DeclarativeBase): pass
class TenantRow:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant: Mapped[str] = mapped_column(String(36), index=True)
    created: Mapped[str] = mapped_column(String(40), default=now)

class Candidate(TenantRow, Base):
    __tablename__='candidates'
    status: Mapped[str] = mapped_column(String(32), default='privacy_review')
    revision: Mapped[int] = mapped_column(Integer, default=1)
    document: Mapped[dict] = mapped_column(JSON, default=dict)
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    consent: Mapped[bool] = mapped_column(default=False)

class Job(TenantRow, Base):
    __tablename__='jobs'
    status: Mapped[str] = mapped_column(String(32), default='privacy_review')
    revision: Mapped[int] = mapped_column(Integer, default=1)
    document: Mapped[dict] = mapped_column(JSON, default=dict)
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    rubric: Mapped[dict] = mapped_column(JSON, default=dict)

class Workflow(TenantRow, Base):
    __tablename__='workflows'
    kind: Mapped[str] = mapped_column(String(40))
    subject: Mapped[str] = mapped_column(String(36))
    state: Mapped[str] = mapped_column(String(30), default='queued')
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    attempts: Mapped[int] = mapped_column(default=0)
    lease_until: Mapped[float] = mapped_column(Float, default=0)
    fence: Mapped[str] = mapped_column(String(36), default='')
    error: Mapped[str] = mapped_column(String(80), default='')

class Match(TenantRow, Base):
    __tablename__='matches'
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    candidate_id: Mapped[str] = mapped_column(String(36), index=True)
    job_id: Mapped[str] = mapped_column(String(36))
    result: Mapped[dict] = mapped_column(JSON)
    __table_args__=(UniqueConstraint('tenant','run_id','candidate_id'),)

class Decision(TenantRow, Base):
    __tablename__='decisions'
    match_id: Mapped[str] = mapped_column(String(36))
    actor: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(Text)

class Proposal(TenantRow, Base):
    __tablename__='proposals'
    match_id: Mapped[str] = mapped_column(String(36))
    candidate_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(40), default='draft')
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__=(UniqueConstraint('tenant','match_id'),)

class Outbox(TenantRow, Base):
    __tablename__='outbox'
    workflow_id: Mapped[str] = mapped_column(String(36), unique=True)
    published: Mapped[bool] = mapped_column(default=False)
class Inbox(TenantRow, Base):
    __tablename__='inbox'
    event_id: Mapped[str] = mapped_column(String(100))
    __table_args__=(UniqueConstraint('tenant','event_id'),)
class Audit(TenantRow, Base):
    __tablename__='audit'
    actor: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(60))
    subject: Mapped[str] = mapped_column(String(36))
class FeedbackRow(TenantRow, Base):
    __tablename__='feedback'
    match_id: Mapped[str] = mapped_column(String(36))
    actor: Mapped[str] = mapped_column(String(200))
    data: Mapped[dict] = mapped_column(JSON)
class Idempotency(TenantRow, Base):
    __tablename__='idempotency'
    actor: Mapped[str] = mapped_column(String(200))
    route: Mapped[str] = mapped_column(String(150))
    key: Mapped[str] = mapped_column(String(128))
    digest: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON)
    __table_args__=(UniqueConstraint('tenant','actor','route','key'),)
class Operation(TenantRow, Base):
    __tablename__='agent_operations'
    digest: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(30), default='queued')
    payload: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    task: Mapped[dict] = mapped_column(JSON, default=dict)
    lease_until: Mapped[float] = mapped_column(Float, default=0)
    fence: Mapped[str] = mapped_column(String(36), default='')

class VaultBase(DeclarativeBase): pass
class Identity(VaultBase):
    __tablename__='identity_vault'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant: Mapped[str] = mapped_column(String(36), index=True)
    encrypted: Mapped[str] = mapped_column(Text)

engine=create_async_engine(settings().database_url)
Session=async_sessionmaker(engine, expire_on_commit=False)
vault_engine=create_async_engine(settings().identity_database_url)
VaultSession=async_sessionmaker(vault_engine, expire_on_commit=False)

@asynccontextmanager
async def transaction(tenant):
    async with Session.begin() as s:
        if engine.dialect.name=='postgresql':
            await s.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {'t':tenant})
        yield s

async def init_dev():
    async with engine.begin() as c: await c.run_sync(Base.metadata.create_all)
    async with vault_engine.begin() as c: await c.run_sync(VaultBase.metadata.create_all)
