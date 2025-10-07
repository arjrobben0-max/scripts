from typing import List, Dict
from smartscripts.ai.text_matching import find_best_match


def align_questions_to_answers(
    questions: List[str],
    answers: List[str],
    threshold: float = 0.5
) -> Dict[str, str]:
    """
    Aligns a list of plain questions with the most relevant answers.

    Args:
        questions (list[str]): List of question strings.
        answers (list[str]): List of answer strings.
        threshold (float): Minimum similarity score to accept a match.
                           If best score < threshold, still assigns the best available answer.

    Returns:
        dict[str, str]: Mapping {question: best_matching_answer}.
    """
    alignment: Dict[str, str] = {}

    for q in questions:
        if not answers:
            alignment[q] = ""
            continue

        best_answer, score = find_best_match(q, answers)

        # Always return the best available answer, even if below threshold
        alignment[q] = best_answer if best_answer else ""

    return alignment


def align_questions(
    student_blocks: List[str],
    guide_questions: List[Dict[str, str]],
    threshold: float = 0.7,
    use_gpt_fallback: bool = False
) -> Dict[str, str]:
    """
    Align OCR-extracted answer blocks with marking guide questions using semantic similarity.

    Args:
        student_blocks (list[str]): OCR text blocks from student's submission.
        guide_questions (list[dict]): Guide questions, each with 'id' and 'question' keys.
        threshold (float): Minimum similarity score to consider a confident match.
        use_gpt_fallback (bool): Whether to use GPT fallback for low-confidence matches.

    Returns:
        dict[str, str]: Mapping {guide_question_id: matched student answer text or "" if no match}
    """
    alignment: Dict[str, str] = {}
    used_indices = set()

    for gq in guide_questions:
        best_score = 0.0
        best_index = -1
        best_text = ""

        for i, text in enumerate(student_blocks):
            if i in used_indices:
                continue

            matched_text, score = find_best_match(
                student_answer=text,
                expected_answers=[gq["question"]],
                threshold=0.0,  # Always check all candidates
                use_gpt_fallback=use_gpt_fallback,
            )

            if score > best_score:
                best_score = score
                best_index = i
                best_text = text

        if best_score >= threshold:
            alignment[str(gq["id"])] = best_text
            used_indices.add(best_index)
        else:
            alignment[str(gq["id"])] = ""  # No confident match found

    return alignment


def batch_align_multiple_submissions(
    submissions: List[List[str]],
    guide_questions: List[Dict[str, str]],
    threshold: float = 0.7,
    use_gpt_fallback: bool = False
) -> List[Dict[str, str]]:
    """
    Align multiple students' OCR text blocks to guide questions.

    Args:
        submissions (list[list[str]]): List of OCR blocks per submission.
        guide_questions (list[dict]): Standard guide questions.
        threshold (float): Confidence threshold.
        use_gpt_fallback (bool): Whether to use GPT fallback.

    Returns:
        list[dict]: List of alignment dicts per submission.
    """
    return [
        align_questions(blocks, guide_questions, threshold, use_gpt_fallback)
        for blocks in submissions
    ]
