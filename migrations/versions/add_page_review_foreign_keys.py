"""Add foreign keys for PageReview -> ExtractedStudentScript

Revision ID: 20250926_add_page_review_fks
Revises: a1b2c3d4e5f6
Create Date: 2025-09-26 22:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250926_add_page_review_fks"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    # Ensure extracted_scripts table exists
    op.create_foreign_key(
        "fk_page_reviews_extracted_script",
        "page_reviews",
        "extracted_scripts",
        ["extracted_script_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Optional: add foreign key to users if not exists
    op.create_foreign_key(
        "fk_page_reviews_reviewer",
        "page_reviews",
        "users",
        ["reviewer_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Optional: add foreign key to tests if not exists
    op.create_foreign_key(
        "fk_page_reviews_test",
        "page_reviews",
        "tests",
        ["test_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    op.drop_constraint("fk_page_reviews_extracted_script", "page_reviews", type_="foreignkey")
    op.drop_constraint("fk_page_reviews_reviewer", "page_reviews", type_="foreignkey")
    op.drop_constraint("fk_page_reviews_test", "page_reviews", type_="foreignkey")
