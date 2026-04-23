"""Consolidate pricing into earnings

- Drop legacy pricing_configs table if it exists.
- Ensure earnings_configs has pricing columns used by order creation.

Revision ID: f1f4a8a0d9c2
Revises: e0d8e2bc6a21
Create Date: 2026-04-22
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "f1f4a8a0d9c2"
down_revision = "e0d8e2bc6a21"
branch_labels = None
depends_on = None


def upgrade():
    # Remove the duplicate table (safe if it was never created).
    op.execute("DROP TABLE IF EXISTS pricing_configs CASCADE")

    # Add pricing columns to earnings_configs if they don't exist.
    op.execute(
        "ALTER TABLE earnings_configs ADD COLUMN IF NOT EXISTS base_fare DOUBLE PRECISION NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE earnings_configs ADD COLUMN IF NOT EXISTS per_km_rate DOUBLE PRECISION NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE earnings_configs ADD COLUMN IF NOT EXISTS minimum_fare DOUBLE PRECISION NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE earnings_configs ADD COLUMN IF NOT EXISTS platform_commission DOUBLE PRECISION NOT NULL DEFAULT 0"
    )


def downgrade():
    # Best-effort rollback: remove the columns we added.
    op.execute("ALTER TABLE earnings_configs DROP COLUMN IF EXISTS platform_commission")
    op.execute("ALTER TABLE earnings_configs DROP COLUMN IF EXISTS minimum_fare")
    op.execute("ALTER TABLE earnings_configs DROP COLUMN IF EXISTS per_km_rate")
    op.execute("ALTER TABLE earnings_configs DROP COLUMN IF EXISTS base_fare")
