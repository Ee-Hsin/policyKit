"""Remove severity from policies table

Revision ID: 04ec75eb74b4
Revises: a2e582d4a91f
Create Date: 2025-05-18 21:58:09.086365

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '04ec75eb74b4'
down_revision: Union[str, None] = 'a2e582d4a91f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('policies', 'severity')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('policies', sa.Column('severity', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=False))
