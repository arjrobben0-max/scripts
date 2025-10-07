# File: smartscripts/ai/marking_adapter.py

from smartscripts.models import StudentSubmission
from smartscripts.ai.marking_pipeline import mark_batch_submissions, mark_single_submission
import logging

logger = logging.getLogger(__name__)


def start_ai_marking(test_id: int, student_id: str = None):
    """
    Marks a single submission (if student_id) or all submissions for a test.
    Lazy imports are used to avoid circular dependencies.
    """
    # Lazy import to avoid circular imports
    try:
        from smartscripts.app.teacher.ai_marking_routes import save_marked_image
    except ImportError as e:
        logger.error(f"Failed to import save_marked_image: {e}")
        save_marked_image = None

    if student_id:
        submission = StudentSubmission.query.filter_by(test_id=test_id, student_id=student_id).first()
        if not submission:
            logger.warning(f"Submission not found: test_id={test_id}, student_id={student_id}")
            return {"error": "Submission not found"}

        result = mark_single_submission(submission)
        if save_marked_image:
            save_marked_image(submission, result)
        return {"message": f"✅ AI marking completed for submission {submission.id}"}

    # Process all submissions for the test
    submissions = StudentSubmission.query.filter_by(test_id=test_id).all()
    if not submissions:
        logger.warning(f"No submissions found for test_id={test_id}")
        return {"error": "No submissions found for this test"}

    results = mark_batch_submissions(submissions, test_id)
    for submission, result in zip(submissions, results):
        if save_marked_image:
            save_marked_image(submission, result)

    logger.info(f"AI marking completed for {len(submissions)} submissions for test {test_id}")
    return {"message": f"✅ AI marking completed for {len(submissions)} submissions"}
