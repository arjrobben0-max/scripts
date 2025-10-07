import os
import pytest
from pathlib import Path
from flask.testing import FlaskClient

# Import the factory
from smartscripts.app import create_app

# Create app instance for testing
app = create_app("default")  # or "development"
client: FlaskClient = app.test_client()


@pytest.fixture
def test_image():
    path = Path("uploads/answers/sample_q1.jpg")
    if not path.exists():
        pytest.skip(f"Test image not found: {path}")
    return path


def test_ocr_endpoint(test_image):
    with open(test_image, "rb") as f:
        response = client.post("/ocr", data={"file": f}, content_type="multipart/form-data")

    assert response.status_code == 200
    data = response.get_json()
    assert "text" in data
    assert isinstance(data["text"], str)
    assert len(data["text"].strip()) > 0


def test_grade_endpoint():
    payload = {
        "question_number": 1,
        "student_answer": "x = 3"
    }

    response = client.post("/grade", json=payload)

    assert response.status_code == 200
    data = response.get_json()
    assert "score" in data and isinstance(data["score"], (int, float))
    assert "feedback" in data and isinstance(data["feedback"], str)


def test_upload_endpoint(test_image):
    with open(test_image, "rb") as f:
        response = client.post("/upload", data={"file": f}, content_type="multipart/form-data")

    assert response.status_code == 200
    data = response.get_json()
    assert "filename" in data
    assert data["filename"].endswith(".jpg")


def test_homepage_or_docs():
    response = client.get("/")
    assert response.status_code in (200, 404)
    # Optionally, check for known text:
    # assert "SmartScripts" in response.get_data(as_text=True)


def test_teacher_review():
    payload = {
        "question_number": 1,
        "student_answer": "x = 2",
        "correct_answer": "x = 3",
        "rubric": [
            {"keyword": "x", "weight": 2},
            {"keyword": "=", "weight": 1},
            {"keyword": "3", "weight": 2}
        ],
        "max_marks": 5
    }

    response = client.post("/teacher/review", json=payload)

    assert response.status_code == 200
    data = response.get_json()
    assert "score" in data
    assert "feedback" in data
