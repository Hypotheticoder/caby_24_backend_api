"""create orders table

Revision ID: 2d7b5c8f4a1e
Revises: 13974fae0bca
Create Date: 2026-03-24 19:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '2d7b5c8f4a1e'
down_revision = '13974fae0bca'
branch_labels = None
depends_on = None


def upgrade():
    # Create table only if it doesn't already exist (idempotent)
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'orders' not in inspector.get_table_names():
        op.create_table(
            'orders',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('type', sa.String(), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('driver_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('pickup_location', sa.String(), nullable=True),
            sa.Column('drop_location', sa.String(), nullable=True),
            sa.Column('status', sa.String(), nullable=False, server_default='pending'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )


def downgrade():
    op.drop_table('orders')
