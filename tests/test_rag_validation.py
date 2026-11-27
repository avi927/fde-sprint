"""Unit tests for the answer checks in app/rag.py (no LLM needed)."""

from app.rag import IDK_ANSWER, RagModelOutput, check_answer, extract_citations


def test_extract_citations_keeps_order_and_removes_duplicates():
    answer = "Yes [returns-guide#1], within 14 days [returns-guide#1] [shipping-guide#0]."
    assert extract_citations(answer) == ["returns-guide#1", "shipping-guide#0"]


def test_extract_citations_accepts_digits_in_the_slug():
    assert extract_citations("See [error-e4012-help#3].") == ["error-e4012-help#3"]


def test_valid_cited_answer_has_no_problems():
    output = RagModelOutput(answerable=True, answer="14 days [returns-guide#1].")
    assert check_answer(output, {"returns-guide#1"}) == []


def test_unknown_citation_is_a_problem():
    output = RagModelOutput(answerable=True, answer="14 days [made-up#9].")
    problems = check_answer(output, {"returns-guide#1"})
    assert len(problems) == 1
    assert "made-up#9" in problems[0]


def test_answer_without_citation_is_a_problem():
    output = RagModelOutput(answerable=True, answer="Returns take 14 days.")
    assert len(check_answer(output, {"returns-guide#1"})) == 1


def test_exact_idk_with_answerable_false_is_valid():
    output = RagModelOutput(answerable=False, answer=IDK_ANSWER)
    assert check_answer(output, set()) == []


def test_curly_apostrophe_idk_is_accepted():
    curly = IDK_ANSWER.replace("'", "\u2019")
    output = RagModelOutput(answerable=False, answer=curly)
    assert check_answer(output, set()) == []


def test_not_answerable_with_other_text_is_a_problem():
    output = RagModelOutput(answerable=False, answer="Probably 30 days.")
    assert len(check_answer(output, set())) == 1