from typing import List, Dict, Any, Optional, Tuple
from difflib import SequenceMatcher
import logging

from smartscripts.ai.text_matching import compute_similarity
from smartscripts.utils.text_cleaner import clean_text

logger = logging.getLogger(__name__)


def string_similarity(a: str, b: str) -> float:
    """Compute simple sequence similarity between two strings."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def match_keywords(
    student_answer: str, rubric_keywords: List[Dict[str, Any]]
) -> Tuple[float, List[str], List[str]]:
    """
    Match keywords in rubric against student answer.
    Always returns exactly (score, matched_keywords, explanations).
    Handles malformed rubric entries safely.
    """
    if not rubric_keywords:
        return 0.0, [], []

    score = 0.0
    matched_keywords: List[str] = []
    explanations: List[str] = []

    for keyword in rubric_keywords:
        try:
            kw_text = keyword.get("keyword")
            if not isinstance(kw_text, str) or not kw_text.strip():
                logger.warning(f"Skipping malformed rubric keyword: {keyword}")
                continue

            if kw_text.lower() in student_answer.lower():
                matched_keywords.append(kw_text)
                score += float(keyword.get("weight", 1.0))
                explanation = keyword.get("explanation")
                if isinstance(explanation, str) and explanation.strip():
                    explanations.append(explanation)
        except Exception as e:
            logger.warning(f"Error processing rubric keyword {keyword}: {e}")
            continue

    return score, matched_keywords, explanations


def evaluate_question(
    student_answer: Optional[str],
    expected_answers: List[str],
    rubric_keywords: List[Dict[str, Any]],
    max_marks: float = 1.0,
    method: str = "semantic",
    threshold: float = 0.75,
) -> Dict[str, Any]:
    """
    Evaluate a single student answer against expected answers and rubric.
    Returns a dict with: score, feedback, similarity, matched_keywords, explanations.
    """
    student_answer = clean_text(student_answer or "")
    if not student_answer:
        return {
            "score": 0.0,
            "feedback": "No answer provided.",
            "matched_keywords": [],
            "similarity": 0.0,
            "explanations": [],
        }

    # --- Similarity check ---
    best_similarity = 0.0
    for expected in expected_answers:
        cleaned = clean_text(expected)
        sim = (
            compute_similarity(student_answer, cleaned)
            if method == "semantic"
            else string_similarity(student_answer, cleaned)
        )
        best_similarity = max(best_similarity, sim)

    # --- Rubric keyword scoring ---
    rubric_score, matched_keywords, explanations = 0.0, [], []
    try:
        if rubric_keywords:
            rubric_score, matched_keywords, explanations = match_keywords(
                student_answer, rubric_keywords
            )
    except Exception as e:
        logger.warning(f"match_keywords failed: {e}")

    # --- Final scoring ---
    if rubric_keywords:
        score = min(rubric_score, max_marks)
        feedback = (
            f"Matched {len(matched_keywords)} keyword(s)."
            if matched_keywords
            else "No key concepts found."
        )
    else:
        if best_similarity >= 0.95:
            score = max_marks
            feedback = "Perfect answer."
        elif best_similarity >= threshold:
            score = round(max_marks * best_similarity, 2)
            feedback = f"Partial match ({int(best_similarity * 100)}%)."
        else:
            score = 0.0
            feedback = "Answer does not match."

    return {
        "score": round(score, 2),
        "feedback": feedback,
        "similarity": round(best_similarity, 2),
        "matched_keywords": matched_keywords,
        "explanations": explanations,
    }


def grade_submission_using_guide(
    student_answers: List[str], guide: List[Dict[str, Any]], method: str = "semantic"
) -> Dict[str, Any]:
    """
    Grade a full submission against a structured guide.
    Each guide item:
    {
        "id": "q1",
        "question": "...",
        "answers": ["...", "..."],
        "rubric": [{"keyword": "...", "weight": 1.0, "explanation": "..."}, ...],
        "max_marks": 2.0
    }
    """
    assert len(student_answers) == len(guide), "Answer count must match guide length."

    total_score = 0.0
    max_total = 0.0
    per_question_results: List[Dict[str, Any]] = []

    for idx, (student_ans, guide_item) in enumerate(zip(student_answers, guide)):
        expected = guide_item.get("answers", [])
        rubric = guide_item.get("rubric", [])
        max_marks = guide_item.get("max_marks", 1.0)

        result = evaluate_question(
            student_answer=student_ans,
            expected_answers=expected,
            rubric_keywords=rubric,
            max_marks=max_marks,
            method=method,
        )

        result.update(
            {
                "question_id": guide_item.get("id", f"q{idx+1}"),
                "student_answer": student_ans,
                "expected_answers": expected,
                "max_marks": max_marks,
                "question": guide_item.get("question", ""),
            }
        )

        total_score += result["score"]
        max_total += max_marks
        per_question_results.append(result)

    percentage = round((total_score / max_total) * 100, 2) if max_total > 0 else 0.0

    return {
        "total_score": round(total_score, 2),
        "percentage": percentage,
        "per_question": per_question_results,
        "feedback_summary": generate_summary_feedback(per_question_results),
    }


def generate_summary_feedback(per_question_results: List[Dict[str, Any]]) -> str:
    """Generate high-level feedback summary for all questions."""
    correct = sum(1 for r in per_question_results if r["score"] >= r["max_marks"])
    partial = sum(1 for r in per_question_results if 0 < r["score"] < r["max_marks"])
    wrong = sum(1 for r in per_question_results if r["score"] == 0)

    parts = []
    if correct:
        parts.append(f"{correct} correct")
    if partial:
        parts.append(f"{partial} partial")
    if wrong:
        parts.append(f"{wrong} incorrect")

    return "You got: " + ", ".join(parts) + "." if parts else "No answers provided."


# ===== Backward compatibility =====


def calculate_score(answer: str, keywords: List[str], max_score: float) -> float:
    """Legacy simple scoring for unit tests."""
    matched = sum(1 for kw in keywords if kw.lower() in (answer or "").lower())
    return round((matched / len(keywords)) * max_score, 2) if keywords else 0.0


def grade_answer(answer: str, rubric: Dict[str, Any]) -> Dict[str, Any]:
    """Legacy grading wrapper for old tests."""
    return evaluate_question(
        student_answer=answer,
        expected_answers=rubric.get("answers", []),
        rubric_keywords=rubric.get("rubric", []),
        max_marks=rubric.get("max_marks", 1.0),
        method="semantic",
    )
