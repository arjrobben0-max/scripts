import cv2
import os
import numpy as np
import pytest

from smartscripts.services.overlay_service import overlay_marks


@pytest.fixture
def sample_image(tmp_path):
    """Create a blank white image as a mock answer sheet."""
    img_path = tmp_path / "blank_answer.jpg"
    image = np.ones((400, 400, 3), dtype=np.uint8) * 255  # white image
    cv2.imwrite(str(img_path), image)
    return str(img_path)


def test_overlay_marks_creates_output(sample_image, tmp_path):
    marks = [
        {"x": 50, "y": 60, "type": "tick"},
        {"x": 200, "y": 220, "type": "cross"},
        {"x": 300, "y": 350, "type": "score", "value": "4/5"},
    ]
    
    output_path = tmp_path / "annotated.jpg"

    overlay_marks(sample_image, marks, str(output_path))

    # ✅ Check that the file was created
    assert os.path.exists(output_path)

    # ✅ Check that the image has changed (not identical to the original)
    original = cv2.imread(sample_image)
    annotated = cv2.imread(str(output_path))

    assert not np.array_equal(original, annotated), "Overlay failed: image did not change"


def test_overlay_invalid_mark_type_ignored(sample_image, tmp_path):
    marks = [
        {"x": 100, "y": 100, "type": "banana"},  # invalid type
    ]
    output_path = tmp_path / "invalid_type.jpg"

    overlay_marks(sample_image, marks, str(output_path))

    # File should still be created (just without applying invalid overlay)
    assert os.path.exists(output_path)

