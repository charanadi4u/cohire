"""Initial domain schema and forced tenant RLS."""
from alembic import op
from app.repositories.db import Base
revision='001'
down_revision=None

def upgrade():
    bind=op.get_bind();Base.metadata.create_all(bind)
    if bind.dialect.name=='postgresql':
        for name in Base.metadata.tables:
            op.execute(f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE "{name}" FORCE ROW LEVEL SECURITY')
            op.execute(f'''CREATE POLICY tenant_scope ON "{name}" USING (tenant = nullif(current_setting('app.tenant_id', true), '')) WITH CHECK (tenant = nullif(current_setting('app.tenant_id', true), ''))''')

def downgrade():
    Base.metadata.drop_all(op.get_bind())
