"""Add driver_payout to customer_orders

Revision ID: 7b0c3d9f4c12
Revises: 50a5be49e3a0
Create Date: 2026-04-23
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7b0c3d9f4c12"
down_revision = "50a5be49e3a0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("customer_orders", sa.Column("driver_payout", sa.Float(), nullable=True))


def downgrade():
    op.drop_column("customer_orders", "driver_payout")
