# smartscripts/models/__init__.py

from .user import User
from .student import Student
from .test import Test
from .test_script import TestScript

# Import the correct submission model and alias it as Submission
from .student_submission import StudentSubmission

from .test_submission import TestSubmission
from .marking_guide import MarkingGuide
from .ocr_submission import OCRSubmission
from .ocr_override import OcrOverrideLog
from .audit_log import AuditLog
from .result import Result
from .bulk_upload import BulkUpload
from .attendance import AttendanceRecord
from .page_review import PageReview
from .submission_manifest import SubmissionManifest
from .extracted_student_script import ExtractedStudentScript
from .marksheet import Marksheet
from .graded_script import GradedScript
from .teacher_review import TeacherReview
from .task_control import TaskControl  # <-- NEW import

__all__ = [
    "User",
    "Student",
    "Test",
    "TestScript",
    "StudentSubmission",
    "TestSubmission",
    "MarkingGuide",
    "OCRSubmission",
    "OcrOverrideLog",
    "AuditLog",
    "Result",
    "BulkUpload",
    "AttendanceRecord",
    "PageReview",
    "SubmissionManifest",
    "ExtractedStudentScript",
    "Marksheet",
    "GradedScript",
    "TeacherReview",
    "TaskControl",  # <-- NEW in __all__
]
