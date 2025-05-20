"""Add job posting embeddings table

Revision ID: add_job_posting_embeddings
Revises: 04ec75eb74b4
Create Date: 2025-05-19 20:45:01.500000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = 'add_job_posting_embeddings'
down_revision = '04ec75eb74b4'
branch_labels = None
depends_on = None

def upgrade():
    # Enable the pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Create the job posting embeddings table
    op.create_table(
        'job_posting_embeddings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_description', sa.String(), nullable=False),
        sa.Column('embedding', Vector(1536), nullable=False),
        sa.Column('has_violations', sa.Boolean(), nullable=False),
        sa.Column('violations', postgresql.JSON(), nullable=True),
        sa.Column('similarity_score', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create an index on the embedding column for faster similarity search
    op.create_index(
        'job_posting_embeddings_embedding_idx',
        'job_posting_embeddings',
        ['embedding'],
        postgresql_using='ivfflat',
        postgresql_with={'lists': 100},
        postgresql_ops={'embedding': 'vector_cosine_ops'}
    )

def downgrade():
    # Drop the table and extension
    op.drop_table('job_posting_embeddings')
    op.execute('DROP EXTENSION IF EXISTS vector') 