"""Order is job: driver FK + last location fields

Revision ID: 8c3f2d9a1b27
Revises: 5aedbfa414aa
Create Date: 2026-04-20
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8c3f2d9a1b27"
down_revision = "5aedbfa414aa"
branch_labels = None
depends_on = None


def upgrade():
    # Remove hub_job_id (order itself is the job now)
    op.drop_column("customer_orders", "hub_job_id")

    # Add last known driver position for this order
    op.add_column("customer_orders", sa.Column("assigned_driver_lat", sa.Float(), nullable=True))
    op.add_column("customer_orders", sa.Column("assigned_driver_lng", sa.Float(), nullable=True))
    op.add_column("customer_orders", sa.Column("last_location_update", sa.DateTime(), nullable=True))

    # Add FK from customer_orders.assigned_driver_id -> drivers.id
    # If any rows have an orphaned assigned_driver_id, null them so the FK can be created.
    op.execute(
        """
        UPDATE customer_orders
        SET assigned_driver_id = NULL
        WHERE assigned_driver_id IS NOT NULL
          AND assigned_driver_id NOT IN (SELECT id FROM drivers)
        """
    )

    op.create_foreign_key(
        "fk_customer_orders_assigned_driver_id",
        "customer_orders",
        "drivers",
        ["assigned_driver_id"],
        ["id"],
        ondelete=None,
    )


def downgrade():
    op.drop_constraint("fk_customer_orders_assigned_driver_id", "customer_orders", type_="foreignkey")

    op.drop_column("customer_orders", "last_location_update")
    op.drop_column("customer_orders", "assigned_driver_lng")
    op.drop_column("customer_orders", "assigned_driver_lat")

    op.add_column("customer_orders", sa.Column("hub_job_id", sa.String(), nullable=True))
