# generate_full_erd.py
import os
from sqlalchemy_schemadisplay import create_schema_graph
from smartscripts.extensions import db

# Import all models so they are registered with metadata
from smartscripts.models import (
    attendance,
    audit_log,
    bulk_upload,
    extracted_student_script,
    graded_script,
    marksheet,
    marking_guide,
    ocr_override_log,
    ocr_submission,
    page_review,
    result,
    student,
    student_submission,
    submission_manifest,
    task_control,
    teacher_review,
    test,
    test_script,
    test_submission,
    user
)

# Output file
output_file = os.path.join(os.getcwd(), "smartscripts_full_erd.png")

# Generate the ERD
graph = create_schema_graph(
    metadata=db.metadata,
    show_datatypes=True,  # show column types
    show_indexes=True,    # show indexes
    rankdir='LR',         # Left -> Right layout
    concentrate=False     # Don't merge foreign key lines
)

# Save PNG
graph.write_png(output_file)
print(f"✅ Full ERD generated: {output_file}")
