import cv2
import numpy as np
import os

# Example utility function for overlaying tick/cross
def add_overlay(image, overlay_type="tick"):
    """
    Add tick or cross overlay to an image.
    
    Args:
        image: OpenCV image (numpy array)
        overlay_type: "tick" or "cross"
    
    Returns:
        Annotated OpenCV image
    """
    if image is None:
        raise ValueError("Input image is None")

    # Define overlay color and thickness
    if overlay_type == "tick":
        color = (0, 255, 0)  # Green
        thickness = 5
        start_point = (50, 50)
        mid_point = (100, 100)
        end_point = (200, 50)
        # Draw tick
        cv2.line(image, start_point, mid_point, color, thickness)
        cv2.line(image, mid_point, end_point, color, thickness)
    elif overlay_type == "cross":
        color = (0, 0, 255)  # Red
        thickness = 5
        # Draw cross
        h, w = image.shape[:2]
        cv2.line(image, (0, 0), (w, h), color, thickness)
        cv2.line(image, (w, 0), (0, h), color, thickness)
    else:
        raise ValueError(f"Unknown overlay_type={overlay_type}")

    return image


# If you have functions that need marking_pipeline
# always import locally inside the function to avoid circular import
def overlay_with_feedback(submission_id, overlay_type="tick"):
    """
    Annotate a submission image and save feedback.
    """
    # Local import to avoid circular import
    from smartscripts.models import StudentSubmission
    from smartscripts.ai.marking_pipeline import update_marked_submission

    submission = StudentSubmission.query.get(submission_id)
    if not submission:
        raise ValueError(f"Submission ID {submission_id} not found")

    image = cv2.imread(submission.file_path)
    annotated = add_overlay(image, overlay_type)
    save_dir = os.path.join("uploads", "marked", str(submission.test_id), str(submission.student_id))
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, f"marked_{os.path.basename(submission.file_path)}")
    cv2.imwrite(save_path, annotated)

    update_marked_submission(
        submission_id=submission.id,
        score=submission.score,
        feedback=submission.feedback,
        marked_file_path=save_path,
    )

    return save_path
