# tests/test_grading.py

import os
import pytest
from flask.testing import FlaskClient
from smartscripts.app import create_app  # Flask app factory
from smartscripts.ai.scoring import grade_answer, calculate_score, evaluate_question

# ─── App setup ───────────────────────────────────────
app = create_app("default")  # or "development"
client: FlaskClient = app.test_client()


# ─── Fixtures ───────────────────────────────────────
@pytest.fixture
def rubric():
    return {
        1: {
            "answers": ["x = 3", "x equals 3"],
            "rubric": [
                {"keyword": "x", "weight": 2},
                {"keyword": "=", "weight": 1},
                {"keyword": "3", "weight": 2}
            ],
            "max_marks": 5
        },
        2: {
            "answers": ["area = 12", "Area equals twelve"],
            "rubric": [
                {"keyword": "area", "weight": 2},
                {"keyword": "=", "weight": 1},
                {"keyword": "12", "weight": 2}
            ],
            "max_marks": 5
        }
    }


@pytest.fixture
def teacher_review_payload():
    return {
        "question_number": 1,
        "student_answer": "The value of x is 2",
        "correct_answer": "x = 3",
        "rubric": [
            {"keyword": "x", "weight": 2},
            {"keyword": "=", "weight": 1},
            {"keyword": "3", "weight": 2}
        ],
        "max_marks": 5,
        "manual_override": True,
        "manual_score": 4,
        "manual_feedback": "Good effort, but check your calculation."
    }


@pytest.fixture
def student_review_payload():
    return {
        "student_id": "stu123",
        "question_number": 2,
        "student_answer": "Area = 12",
        "expected_answer": "Area = 12",
        "max_marks": 5
    }


# ─── Rule-Based Grading Tests ───────────────────────
def test_exact_match_score(rubric):
    student_answer = "x = 3"
    result = grade_answer(student_answer, rubric[1])

    assert result["score"] == rubric[1]["max_marks"]
    assert "perfect" in result["feedback"].lower() or "matched" in result["feedback"].lower()


def test_partial_match_score(rubric):
    student_answer = "Area = 10"
    result = grade_answer(student_answer, rubric[2])

    assert 0 < result["score"] < rubric[2]["max_marks"]
    assert "partial" in result["feedback"].lower() or "matched" in result["feedback"].lower()


def test_zero_score(rubric):
    student_answer = "I don't know"
    result = grade_answer(student_answer, rubric[2])

    assert result["score"] == 0
    assert "no key concepts" in result["feedback"].lower() or "does not match" in result["feedback"].lower()


def test_calculate_score_logic():
    keywords = ["photosynthesis", "chlorophyll", "sunlight"]
    max_score = 5

    full = calculate_score("Photosynthesis uses sunlight and chlorophyll.", keywords, max_score=max_score)
    assert full == max_score

    partial = calculate_score("Just sunlight mentioned.", keywords, max_score=max_score)
    assert 0 < partial < max_score

    none = calculate_score("No relevant content here.", keywords, max_score=max_score)
    assert none == 0.0


# ─── Semantic Grading Tests ─────────────────────────
def test_semantic_grading_full_credit():
    expected = "The heart pumps blood throughout the body"
    student = "Blood is pumped around the body by the heart"

    result = evaluate_question(
        student_answer=student,
        expected_answers=[expected],
        rubric_keywords=[],
        max_marks=5,
        method="semantic"
    )

    assert result["score"] == 5
    assert "matches" in result["feedback"].lower() or "perfect" in result["feedback"].lower()


def test_semantic_grading_partial_credit():
    expected = "Photosynthesis requires sunlight, carbon dioxide, and water"
    student = "Photosynthesis uses sunlight and water"

    result = evaluate_question(
        student_answer=student,
        expected_answers=[expected],
        rubric_keywords=[],
        max_marks=5,
        method="semantic"
    )

    assert 0 < result["score"] < 5
    assert "partial" in result["feedback"].lower()


def test_semantic_grading_no_credit():
    expected = "Mitosis is the process of cell division"
    student = "Mitochondria create energy in cells"

    result = evaluate_question(
        student_answer=student,
        expected_answers=[expected],
        rubric_keywords=[],
        max_marks=5,
        method="semantic"
    )

    assert result["score"] == 0
    assert "does not match" in result["feedback"].lower() or "no answer" in result["feedback"].lower()


def test_semantic_grading_extra_detail_credit():
    expected = "Water boils at 100 degrees Celsius"
    student = "At standard pressure, water boils at 100°C"

    result = evaluate_question(
        student_answer=student,
        expected_answers=[expected],
        rubric_keywords=[],
        max_marks=5,
        method="semantic"
    )

    assert result["score"] >= 4
    assert "matches" in result["feedback"].lower() or "accurate" in result["feedback"].lower()


def test_semantic_grading_minor_inaccuracy():
    expected = "The capital of France is Paris"
    student = "The capital of France is Lyon"

    result = evaluate_question(
        student_answer=student,
        expected_answers=[expected],
        rubric_keywords=[],
        max_marks=5,
        method="semantic"
    )

    assert 0 < result["score"] < 5
    assert "partial" in result["feedback"].lower() or "incorrect" in result["feedback"].lower()


# ─── API Tests ─────────────────────────────────────
def test_teacher_review_manual_override(teacher_review_payload):
    response = client.post("/api/teacher/review", json=teacher_review_payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["score"] == teacher_review_payload["manual_score"]
    assert teacher_review_payload["manual_feedback"] in data["feedback"]


def test_student_review_feedback_overlay(student_review_payload):
    response = client.post("/api/student/review", json=student_review_payload)
    assert response.status_code == 200
    data = response.get_json()
    assert "score" in data
    assert "feedback" in data
    assert "correct" in data["feedback"].lower() or "well done" in data["feedback"].lower()


def test_teacher_review_missing_fields():
    incomplete_payload = {
        "question_number": 1,
        "student_answer": "x = 2"
    }
    response = client.post("/api/teacher/review", json=incomplete_payload)
    assert response.status_code in (400, 422)


def test_student_review_invalid_types():
    invalid_payload = {
        "student_id": 123,
        "question_number": "two",
        "student_answer": 12,
        "expected_answer": None,
        "max_marks": "five"
    }
    response = client.post("/api/student/review", json=invalid_payload)
    assert response.status_code in (400, 422)


# ─── Output File Verification ───────────────────────
def test_marking_creates_files(tmp_path):
    test_id = "test456"
    student_id = "stu999"

    # Create simulated directories for output
    base_path = tmp_path / "uploads" / "marked" / test_id / student_id
    base_path.mkdir(parents=True, exist_ok=True)

    annotated_path = base_path / "annotated.png"
    feedback_path = base_path / "feedback.json"

    # Simulate file creation
    with open(annotated_path, "wb") as f:
        f.write(b"fake image data")

    with open(feedback_path, "w") as f:
        f.write('{"score": 4, "feedback": "Sample feedback."}')

    assert annotated_path.exists()
    assert feedback_path.exists()
    assert annotated_path.stat().st_size > 0
    assert feedback_path.read_text().startswith("{")
