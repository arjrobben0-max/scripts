import logging
import cv2
from smartscripts.ai.marking_pipeline import mark_submission

# Configure simple logging to console
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Example inputs
image_path = "examples/student_answer.jpg"
expected_answer = (
    "Photosynthesis is the process by which plants make food using sunlight."
)

try:
    result = mark_submission(image_path, expected_answer)

    # ✅ Always enforce 3 return values
    if isinstance(result, (tuple, list)) and len(result) == 3:
        student_text, score, annotated = result
    else:
        logger.warning(f"mark_submission returned unexpected result: {result}")
        student_text, score, annotated = "", 0.0, None

except Exception as e:
    logger.warning(f"mark_submission raised exception: {e}")
    student_text, score, annotated = "", 0.0, None

# --- Output results ---
print(f"Student wrote: {student_text}")
print(f"Similarity score: {score:.2f}")

if annotated is not None:
    try:
        cv2.imwrite("output/annotated_result.png", annotated)
        print("Annotated result saved to output/annotated_result.png")
    except Exception as e:
        logger.warning(f"Could not save annotated image: {e}")
else:
    logger.warning("No annotated image to save.")
