"""Remove vector extension and job posting embeddings table

Revision ID: remove_vector_extension
Revises: add_job_posting_embeddings
Create Date: 2024-03-19 20:45:01.500000

"""
from alembic import op
import sqlalchemy as sa

revision = 'remove_vector_extension'
down_revision = 'add_job_posting_embeddings'
branch_labels = None
depends_on = None

def upgrade():
    op.drop_table('job_posting_embeddings')
    
    op.execute('DROP EXTENSION IF EXISTS vector')

def downgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.create_table(
        'job_posting_embeddings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_description', sa.String(), nullable=False),
        sa.Column('embedding', sa.ARRAY(sa.Float()), nullable=False),
        sa.Column('has_violations', sa.Boolean(), nullable=False),
        sa.Column('violations', sa.JSON(), nullable=True),
        sa.Column('similarity_score', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    ) 