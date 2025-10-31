"""Tests for Neo4j ETL validation functions"""

import pytest

from neo4j_etl.src.validate import (
    ANSWER_BODY_MAX_LENGTH,
    COMMENT_BODY_MAX_LENGTH,
    QUESTION_BODY_MAX_LENGTH,
    validate_answer,
    validate_comment,
    validate_question,
    validate_tag,
    validate_user,
)

# Constants
TEST_USER_ID = 123
TEST_DISPLAY_NAME = "John Doe"
TEST_REPUTATION = 1000

TEST_COMMENT_ID = 789
TEST_BODY_SHORT = "Short comment"
TEST_BODY_LONG = "a" * 300  # Exceeds COMMENT_BODY_MAX_LENGTH (200)
TEST_SCORE = 5

TEST_ANSWER_ID = 234
TEST_ANSWER_BODY_SHORT = "Short answer"
TEST_ANSWER_BODY_LONG = "b" * 600  # Exceeds ANSWER_BODY_MAX_LENGTH (500)
TEST_IS_ACCEPTED = True

TEST_QUESTION_ID = 345
TEST_TITLE = "How to test?"
TEST_QUESTION_BODY_SHORT = "Short question"
TEST_QUESTION_BODY_LONG = "c" * 600  # Exceeds QUESTION_BODY_MAX_LENGTH (500)
TEST_SITE = "stackoverflow"
TEST_COLLECTED_AT = 1234567890.0

TEST_TAG_VALID = "python"


@pytest.fixture
def base_user_data():
    """Base user data for testing"""
    return {
        "user_id": TEST_USER_ID,
        "display_name": TEST_DISPLAY_NAME,
        "reputation": TEST_REPUTATION,
    }


@pytest.fixture
def base_comment_data():
    """Base comment data for testing"""
    return {
        "comment_id": TEST_COMMENT_ID,
        "body": TEST_BODY_SHORT,
        "score": TEST_SCORE,
    }


@pytest.fixture
def base_answer_data():
    """Base answer data for testing"""
    return {
        "answer_id": TEST_ANSWER_ID,
        "body": TEST_ANSWER_BODY_SHORT,
        "score": TEST_SCORE,
        "is_accepted": TEST_IS_ACCEPTED,
    }


@pytest.fixture
def base_question_data():
    """Base question data for testing"""
    return {
        "question_id": TEST_QUESTION_ID,
        "title": TEST_TITLE,
        "body": TEST_QUESTION_BODY_SHORT,
        "score": TEST_SCORE,
        "site": TEST_SITE,
        "collected_at": TEST_COLLECTED_AT,
    }


# validate_user tests
def test_validate_user_valid(base_user_data):
    """Test validate_user with valid data"""
    result = validate_user(base_user_data)

    assert result is not None
    assert result["user_id"] == TEST_USER_ID
    assert result["display_name"] == TEST_DISPLAY_NAME
    assert result["reputation"] == TEST_REPUTATION


@pytest.mark.parametrize(
    "user_id_input",
    [None, "missing"],  # "missing" means key doesn't exist
    ids=["none", "missing"],
)
def test_validate_user_no_id(base_user_data, user_id_input):
    """Test validate_user returns None when user_id is missing or None"""
    user_data = base_user_data.copy()
    if user_id_input == "missing":
        user_data.pop("user_id")
    else:
        user_data["user_id"] = user_id_input

    result = validate_user(user_data)
    assert result is None


# validate_comment tests
def test_validate_comment_valid(base_comment_data):
    """Test validate_comment with valid data"""
    result = validate_comment(base_comment_data)

    assert result is not None
    assert result["comment_id"] == TEST_COMMENT_ID
    assert result["body"] == TEST_BODY_SHORT
    assert result["score"] == TEST_SCORE


def test_validate_comment_no_id(base_comment_data):
    """Test validate_comment returns None when comment_id is missing"""
    comment_data = base_comment_data.copy()
    comment_data.pop("comment_id")

    result = validate_comment(comment_data)
    assert result is None


def test_validate_comment_body_truncation(base_comment_data):
    """Test validate_comment truncates long body to max length"""
    comment_data = base_comment_data.copy()
    comment_data["body"] = TEST_BODY_LONG

    result = validate_comment(comment_data)

    assert result is not None
    assert len(result["body"]) == COMMENT_BODY_MAX_LENGTH
    assert result["body"] == TEST_BODY_LONG[:COMMENT_BODY_MAX_LENGTH]


# validate_answer tests
def test_validate_answer_valid(base_answer_data):
    """Test validate_answer with valid data"""
    result = validate_answer(base_answer_data)

    assert result is not None
    assert result["answer_id"] == TEST_ANSWER_ID
    assert result["body"] == TEST_ANSWER_BODY_SHORT
    assert result["score"] == TEST_SCORE
    assert result["is_accepted"] == TEST_IS_ACCEPTED


def test_validate_answer_no_id(base_answer_data):
    """Test validate_answer returns None when answer_id is missing"""
    answer_data = base_answer_data.copy()
    answer_data.pop("answer_id")

    result = validate_answer(answer_data)
    assert result is None


def test_validate_answer_body_truncation(base_answer_data):
    """Test validate_answer truncates long body to max length"""
    answer_data = base_answer_data.copy()
    answer_data["body"] = TEST_ANSWER_BODY_LONG

    result = validate_answer(answer_data)

    assert result is not None
    assert len(result["body"]) == ANSWER_BODY_MAX_LENGTH
    assert result["body"] == TEST_ANSWER_BODY_LONG[:ANSWER_BODY_MAX_LENGTH]


# validate_question tests
def test_validate_question_valid(base_question_data):
    """Test validate_question with valid data"""
    result = validate_question(base_question_data)

    assert result is not None
    assert result["question_id"] == TEST_QUESTION_ID
    assert result["title"] == TEST_TITLE
    assert result["body"] == TEST_QUESTION_BODY_SHORT
    assert result["score"] == TEST_SCORE
    assert result["site"] == TEST_SITE
    assert result["collected_at"] == TEST_COLLECTED_AT


def test_validate_question_no_id(base_question_data):
    """Test validate_question returns None when question_id is missing"""
    question_data = base_question_data.copy()
    question_data.pop("question_id")

    result = validate_question(question_data)
    assert result is None


def test_validate_question_body_truncation(base_question_data):
    """Test validate_question truncates long body to max length"""
    question_data = base_question_data.copy()
    question_data["body"] = TEST_QUESTION_BODY_LONG

    result = validate_question(question_data)

    assert result is not None
    assert len(result["body"]) == QUESTION_BODY_MAX_LENGTH
    assert result["body"] == TEST_QUESTION_BODY_LONG[:QUESTION_BODY_MAX_LENGTH]


# validate_tag tests
@pytest.mark.parametrize(
    "tag_input,expected",
    [
        (TEST_TAG_VALID, TEST_TAG_VALID),
        ("  python  ", "python"),  # Whitespace stripped
        ("", None),  # Empty returns None
        ("   ", None),  # Whitespace-only returns None
        (None, None),  # None returns None
    ],
    ids=["valid", "with_whitespace", "empty", "whitespace_only", "none"],
)
def test_validate_tag(tag_input, expected):
    """Test validate_tag normalizes tag names"""
    result = validate_tag(tag_input)
    assert result == expected
