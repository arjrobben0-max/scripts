# smartscripts/services/grading_service.py
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Union

from flask import current_app
from smartscripts.models import StudentSubmission as Submission, db
from smartscripts.services.student_preprocessing import preprocess_student_submissions
from smartscripts.utils.file_helpers import get_submission_dir
from smartscripts.services.analytics_service import generate_review_zip  # ZIP generation logic

logger = logging.getLogger(__name__)


class GradingService:
    """
    Core grading service for preprocessing, AI/manual grading, and review workflow.
    Uses centralized student preprocessing for OCR, PDF splitting, and attendance review.
    """

    # -------------------------------
    # Preprocessing & Student Detection
    # -------------------------------
    def preprocess_combined_pdf(
        self,
        test_id: int,
        combined_pdf_path: Union[str, Path],
        class_list: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Preprocess combined PDF:
        - Extracts student scripts using OCR & front-page detection
        - Splits PDFs per student
        - Generates attendance CSV & review ZIP
        """
        if class_list is None:
            class_list = []

        result = preprocess_student_submissions(
            combined_pdf_path=Path(combined_pdf_path),
            test_id=test_id,
            class_list=class_list
        )

        # Create DB entries for extracted scripts
        for script in result.get("extracted_student_scripts", []):
            student_id = getattr(script, "matched_id", None) or getattr(script, "ocr_student_id", None)
            submission_dir = Path(get_submission_dir(test_id, student_id))
            submission_dir.mkdir(parents=True, exist_ok=True)

            submission = Submission(
                test_id=int(test_id),
                student_id=str(student_id),
                file_path=str(Path(current_app.root_path) / getattr(script, "extracted_pdf_path")),
                status="uploaded",
                grade=None,
                feedback=None
            )
            db.session.add(submission)

        db.session.commit()
        logger.info(
            "Preprocessing complete for test %s: %d scripts",
            test_id,
            len(result.get("extracted_student_scripts", []))
        )
        return result

    # -------------------------------
    # AI / Manual Grading
    # -------------------------------
    def run_ai_marking(self, submission: Submission) -> Dict[str, Optional[str]]:
        """
        Perform AI grading on a single submission.
        Uses centralized directories and placeholder AI logic.
        """
        test_id = int(submission.test_id)  # Column -> int
        student_id = str(submission.student_id)  # Column -> str

        submission_path = Path(get_submission_dir(test_id, student_id)) / Path(submission.file_path).name
        marked_dir = Path(get_submission_dir(test_id, student_id)) / "marked"
        marked_dir.mkdir(parents=True, exist_ok=True)
        marked_file_path = marked_dir / Path(submission.file_path).name

        # Dummy AI grading logic (replace with real model)
        grade = "A"
        feedback = "Excellent work."
        with open(marked_file_path, "w") as f:
            f.write("Annotated feedback placeholder")

        submission.marked_file_path = str(marked_file_path)  # type: ignore
        return {"grade": grade, "feedback": feedback}

    def grade_script(self, submission_id: int) -> Dict[str, Optional[str]]:
        """Grade a single student submission."""
        submission = Submission.query.get(submission_id)
        if not submission:
            raise ValueError(f"Submission {submission_id} not found")

        result = self.run_ai_marking(submission)
        submission.grade = result.get("grade")
        submission.feedback = result.get("feedback")
        submission.status = "graded"
        db.session.add(submission)
        db.session.commit()
        logger.info("Graded submission %s: %s", submission_id, result["grade"])
        return result

    def batch_grade_scripts(self, submission_ids: List[int]) -> int:
        """Batch grade multiple submissions."""
        submissions = Submission.query.filter(Submission.id.in_(submission_ids)).all()
        count = 0
        for submission in submissions:
            try:
                result = self.run_ai_marking(submission)
                submission.grade = result.get("grade")
                submission.feedback = result.get("feedback")
                submission.status = "graded"
                db.session.add(submission)
                count += 1
            except Exception as e:
                logger.error("Grading failed for submission %s: %s", submission.id, e)
        db.session.commit()
        logger.info("Batch graded %d submissions", count)
        return count

    def trigger_manual_review(self, submission_id: int) -> None:
        """Mark a submission for manual teacher review."""
        submission = Submission.query.get(submission_id)
        if submission:
            submission.status = "manual_review"
            db.session.add(submission)
            db.session.commit()
            logger.info("Submission %s marked for manual review", submission_id)
        else:
            logger.warning("Submission %s not found for manual review", submission_id)

    # -------------------------------
    # Generate review package
    # -------------------------------
    def generate_review_package(self, test_id: int) -> str:
        """
        Generate a ZIP containing all student submissions for front-page review.
        """
        submissions = Submission.query.filter(Submission.test_id == test_id).all()
        extracted_scripts = []

        for submission in submissions:
            pdf_path = Path(submission.file_path)
            # Create a lightweight dummy object
            extracted_scripts.append(type("ExtractedStudentScript", (), {"extracted_pdf_path": str(pdf_path)})())

        upload_dir = Path(current_app.root_path) / "static" / "uploads" / str(test_id)
        presence_csv = upload_dir / f"attendance_test_{test_id}.csv"

        # Wrap single CSV in list to satisfy List[Path] type
        return str(generate_review_zip(extracted_scripts, extra_files=[presence_csv], output_dir=upload_dir))


# -------------------------------
# Module-level convenience functions
# -------------------------------
_service = GradingService()


def grade_script(submission_id: int) -> Dict[str, Optional[str]]:
    return _service.grade_script(submission_id)


def batch_grade_scripts(submission_ids: List[int]) -> int:
    return _service.batch_grade_scripts(submission_ids)


def preprocess_combined_pdf(
    test_id: int,
    combined_pdf_path: Union[str, Path],
    class_list: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    return _service.preprocess_combined_pdf(test_id, combined_pdf_path, class_list)
