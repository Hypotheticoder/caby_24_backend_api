"""Add pickup_radius_km to earnings_configs

Revision ID: b9a4c2d1e7f0
Revises: f3a0c9b1e2d4
Create Date: 2026-05-05

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "b9a4c2d1e7f0"
down_revision = "f3a0c9b1e2d4"
branch_labels = None
depends_on = None


def upgrade():
    # New driver pickup search radius (km).
    # Non-null with default ensures distance filters are stable.
    op.execute(
        "ALTER TABLE earnings_configs "
        "ADD COLUMN IF NOT EXISTS pickup_radius_km DOUBLE PRECISION NOT NULL DEFAULT 10.0"
    )


def downgrade():
    op.execute("ALTER TABLE earnings_configs DROP COLUMN IF EXISTS pickup_radius_km")
