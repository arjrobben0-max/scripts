"""Add new fields to extracted_scripts table

Revision ID: a1b2c3d4e5f6
Revises: 12e4299f3f81
Create Date: 2025-09-07 14:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "12e4299f3f81"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("extracted_scripts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("student_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("matched_id", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("confidence", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("front_page", sa.Boolean(), nullable=True, server_default=sa.false()))
        batch_op.add_column(sa.Column("highlighted_text", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("extracted_scripts", schema=None) as batch_op:
        batch_op.drop_column("highlighted_text")
        batch_op.drop_column("front_page")
        batch_op.drop_column("confidence")
        batch_op.drop_column("matched_id")
        batch_op.drop_column("student_name")
