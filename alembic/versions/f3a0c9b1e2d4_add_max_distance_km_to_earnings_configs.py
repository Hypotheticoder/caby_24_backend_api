"""Add max_distance_km to earnings_configs

Revision ID: f3a0c9b1e2d4
Revises: d4b7a2f91c3e
Create Date: 2026-05-02

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "f3a0c9b1e2d4"
down_revision = "d4b7a2f91c3e"
branch_labels = None
depends_on = None


def upgrade():
    # Ensure max_weight_kg behaves safely with >= filters
    op.execute("ALTER TABLE earnings_configs ALTER COLUMN max_weight_kg SET DEFAULT 9999.0")
    op.execute("UPDATE earnings_configs SET max_weight_kg = 9999.0 WHERE max_weight_kg IS NULL")
    op.execute("ALTER TABLE earnings_configs ALTER COLUMN max_weight_kg SET NOT NULL")

    # Add max_distance_km with a safe default so NULLs don't get filtered out
    op.execute(
        "ALTER TABLE earnings_configs "
        "ADD COLUMN IF NOT EXISTS max_distance_km DOUBLE PRECISION NOT NULL DEFAULT 9999.0"
    )


def downgrade():
    op.execute("ALTER TABLE earnings_configs DROP COLUMN IF EXISTS max_distance_km")

    # Revert max_weight_kg constraints (best-effort)
    op.execute("ALTER TABLE earnings_configs ALTER COLUMN max_weight_kg DROP NOT NULL")
    op.execute("ALTER TABLE earnings_configs ALTER COLUMN max_weight_kg DROP DEFAULT")
