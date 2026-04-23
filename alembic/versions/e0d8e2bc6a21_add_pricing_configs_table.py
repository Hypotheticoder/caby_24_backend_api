"""Add pricing configs table

Revision ID: e0d8e2bc6a21
Revises: c34d2f1a8b9e
Create Date: 2026-04-22
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e0d8e2bc6a21"
down_revision = "c34d2f1a8b9e"
branch_labels = None
depends_on = None


def upgrade():
    # PricingConfig was removed in favor of EarningsConfig.
    pass


def downgrade():
    pass
