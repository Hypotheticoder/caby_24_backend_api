"""Add max_weight_kg to earnings_configs

Revision ID: d4b7a2f91c3e
Revises: ce19adc7fc5c
Create Date: 2026-04-30

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "d4b7a2f91c3e"
down_revision = "ce19adc7fc5c"
branch_labels = None
depends_on = None


def upgrade():
    # Nullable: only relevant for parcel_* service types.
    op.execute(
        "ALTER TABLE earnings_configs ADD COLUMN IF NOT EXISTS max_weight_kg DOUBLE PRECISION"
    )


def downgrade():
    op.execute("ALTER TABLE earnings_configs DROP COLUMN IF EXISTS max_weight_kg")
