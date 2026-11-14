"""Initial fleet schema"""
from alembic import op
import sqlalchemy as sa
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("vehicles",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("vehicle_number",sa.String(40),nullable=False),sa.Column("make",sa.String(100)),sa.Column("model",sa.String(100)),sa.Column("created_at",sa.DateTime(),nullable=False)); op.create_index("ix_vehicles_vehicle_number","vehicles",["vehicle_number"],unique=True)
    op.create_table("import_batches",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("filename",sa.String(255),nullable=False),sa.Column("reporting_month",sa.String(7)),sa.Column("status",sa.String(30),nullable=False),sa.Column("total_rows",sa.Integer(),nullable=False),sa.Column("valid_rows",sa.Integer(),nullable=False),sa.Column("invalid_rows",sa.Integer(),nullable=False),sa.Column("created_at",sa.DateTime(),nullable=False),sa.Column("notes",sa.Text()))
    op.create_index("ix_import_batches_reporting_month","import_batches",["reporting_month"])
    op.create_table("daily_statuses",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("vehicle_id",sa.Integer(),sa.ForeignKey("vehicles.id",ondelete="CASCADE"),nullable=False),sa.Column("status_date",sa.Date(),nullable=False),sa.Column("imported_status",sa.String(100)),sa.Column("corrected_status",sa.String(100)),sa.Column("correction_reason",sa.Text()),sa.Column("corrected_by",sa.String(100)),sa.Column("corrected_at",sa.DateTime()),sa.Column("import_batch_id",sa.Integer(),sa.ForeignKey("import_batches.id")),sa.UniqueConstraint("vehicle_id","status_date",name="uq_vehicle_status_date"))
    op.create_index("ix_daily_statuses_vehicle_id","daily_statuses",["vehicle_id"]); op.create_index("ix_daily_statuses_status_date","daily_statuses",["status_date"]); op.create_index("ix_status_date","daily_statuses",["status_date"])
    op.create_table("audit_logs",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("entity_type",sa.String(50),nullable=False),sa.Column("entity_id",sa.String(80),nullable=False),sa.Column("action",sa.String(50),nullable=False),sa.Column("actor",sa.String(100),nullable=False),sa.Column("reason",sa.Text()),sa.Column("before_value",sa.Text()),sa.Column("after_value",sa.Text()),sa.Column("created_at",sa.DateTime(),nullable=False))
def downgrade():
    op.drop_table("audit_logs"); op.drop_index("ix_status_date",table_name="daily_statuses"); op.drop_index("ix_daily_statuses_status_date",table_name="daily_statuses"); op.drop_index("ix_daily_statuses_vehicle_id",table_name="daily_statuses"); op.drop_table("daily_statuses"); op.drop_index("ix_import_batches_reporting_month",table_name="import_batches"); op.drop_table("import_batches"); op.drop_index("ix_vehicles_vehicle_number",table_name="vehicles"); op.drop_table("vehicles")
