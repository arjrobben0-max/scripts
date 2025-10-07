import pytest
from smartscripts.ai.question_alignment import align_questions_to_answers, find_best_match

# === Test find_best_match ===
def test_find_best_match_simple():
    question = "What is the capital of France?"
    answers = [
        "The capital of France is Paris.",
        "Berlin is the capital of Germany.",
        "Madrid is the capital of Spain."
    ]

    best_answer, score = find_best_match(question, answers)
    assert best_answer == "The capital of France is Paris."
    assert score > 0.8  # Expect a high similarity score

def test_find_best_match_no_good_match():
    question = "What is the chemical symbol for water?"
    answers = [
        "The Earth revolves around the Sun.",
        "Cats are mammals.",
        "Paris is beautiful in spring."
    ]

    best_answer, score = find_best_match(question, answers)
    assert best_answer in answers  # Still returns something
    assert score < 0.5  # Low similarity expected

def test_find_best_match_paraphrase():
    question = "Explain the process of photosynthesis."
    answers = [
        "Photosynthesis allows plants to convert sunlight into energy.",
        "Plants breathe oxygen at night.",
        "The water cycle involves evaporation."
    ]

    best_answer, score = find_best_match(question, answers)
    assert "photosynthesis" in best_answer.lower()
    assert score > 0.7

# === Test align_questions_to_answers ===
def test_align_questions_to_answers_basic():
    questions = [
        "What is 2 + 2?",
        "Define photosynthesis.",
        "Name the largest planet."
    ]

    answers = [
        "Photosynthesis is the process by which green plants make food.",
        "The largest planet is Jupiter.",
        "2 + 2 equals 4."
    ]

    alignment = align_questions_to_answers(questions, answers)

    # alignment should map each question to the best matching answer
    assert len(alignment) == len(questions)
    assert alignment[questions[0]] == "2 + 2 equals 4."
    assert alignment[questions[1]] == "Photosynthesis is the process by which green plants make food."
    assert alignment[questions[2]] == "The largest planet is Jupiter."

def test_align_questions_to_answers_empty():
    questions = []
    answers = []
    alignment = align_questions_to_answers(questions, answers)
    assert alignment == {}

# === Run tests if script is executed directly ===
if __name__ == "__main__":
    pytest.main()
