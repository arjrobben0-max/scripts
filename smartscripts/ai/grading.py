import os
import json
from typing import Dict, List, Any
from flask import current_app

from smartscripts.models import StudentSubmission
from smartscripts.extensions import db

# -----------------------------
# Basic Grading Logic
# -----------------------------
def grade_question(question: Dict[str, Any]) -> Dict[str, Any]:
    q_number = question["question_number"]
    student_answer = question.get("student_answer", "")
    correct_answer = question.get("correct_answer", "")
    max_score = question.get("max_score", 5)

    if student_answer.strip().lower() == correct_answer.strip().lower():
        score = max_score
        is_correct = True
    elif student_answer and correct_answer.lower() in student_answer.lower():
        score = round(max_score * 0.5, 2)
        is_correct = False
    else:
        score = 0.0
        is_correct = False

    return {
        "question_number": q_number,
        "score": score,
        "is_correct": is_correct,
        "student_answer": student_answer,
        "expected_answer": correct_answer,
        "max_score": max_score,
    }

# -----------------------------
# Feedback Generation
# -----------------------------
def generate_feedback(question_scores: List[Dict[str, Any]]) -> str:
    flagged = [
        q for q in question_scores 
        if not q["is_correct"] or q["score"] < q.get("max_score", 5)
    ]
    if not flagged:
        return "Excellent work. All answers are correct!"

    feedback_lines = ["Overall good effort. Here's what to review:"]
    for q in flagged:
        feedback_lines.append(
            f" - Question {q['question_number']}: expected something closer to '{q['expected_answer']}'"
        )
    return "\n".join(feedback_lines)

# -----------------------------
# Submission Grading
# -----------------------------
def mark_submission(file_path: str, guide: Dict[str, Any]) -> Dict[str, Any]:
    current_app.logger.info(f"[INFO] Grading file: {file_path}")

    with open(file_path, "r") as f:
        submission = json.load(f)

    student_answers = submission.get("answers", [])
    questions = guide.get("questions", [])

    question_results: List[Dict[str, Any]] = []
    total_score = 0.0
    max_total = 0.0

    for q in questions:
        q_number = q.get("question_number")
        correct_answer = q.get("correct_answer")
        max_score = q.get("max_score", 5)

        student_answer = next(
            (a.get("answer", "") for a in student_answers if a.get("question_number") == q_number),
            ""
        )

        result = grade_question({
            "question_number": q_number,
            "student_answer": student_answer,
            "correct_answer": correct_answer,
            "max_score": max_score
        })

        total_score += result["score"]
        max_total += max_score
        question_results.append(result)

    overall_grade = round((total_score / max_total) * 100, 2) if max_total else 0.0

    result_data = {
        "grade": overall_grade,
        "feedback": generate_feedback(question_results),
        "question_scores": question_results,
        "ai_confidence": round(0.9 + 0.1 * (overall_grade / 100), 3),
    }

    # Extract test_id and student_id from path
    try:
        parts = file_path.split(os.sep)
        test_id = parts[-3]
        student_id = parts[-2]
    except IndexError:
        current_app.logger.error("[ERROR] Invalid file_path structure.")
        return result_data

    feedback_dir = os.path.join("uploads", "feedback", test_id)
    os.makedirs(feedback_dir, exist_ok=True)

    feedback_path = os.path.join(feedback_dir, f"{student_id}_feedback.json")
    with open(feedback_path, "w") as f:
        json.dump(result_data, f, indent=2)

    current_app.logger.info(f"[INFO] Saved feedback to: {feedback_path}")
    return result_data
