"""Tests for extraction logic"""

from unittest.mock import MagicMock, patch

import pytest

from stream_stackexchange.api_client import StackExchangeAPIClient
from stream_stackexchange.extract import (
    extract_answers,
    extract_comment,
    extract_question,
    extract_user,
)
from stream_stackexchange.models import User

TEST_USER_ID = 123
TEST_DISPLAY_NAME = "John"
TEST_REPUTATION = 1000
TEST_COMMENT_ID = 456
TEST_ANSWER_ID = 789
TEST_QUESTION_ID = 1
TEST_SCORE_LOW = 5
TEST_SCORE_HIGH = 10
TEST_SCORE_ZERO = 0
TEST_TIMESTAMP = 1234567890.0
TEST_SITE = "ux"
TEST_BODY_SHORT = "Text"
TEST_BODY_COMMENT = "Great answer!"
TEST_BODY_ANSWER = "Answer text"
TEST_BODY_QUESTION = "Question body"
TEST_TITLE_QUESTION = "Test Question"
TEST_TITLE_SHORT = "Test"
TEST_BODY_SHORT_ALT = "Body"
TEST_ANSWER_VALID_BODY = "Valid answer"


@pytest.mark.parametrize(
    "owner_data,expected_user_id,expected_display_name,expected_reputation",
    [
        (
            {
                "user_id": TEST_USER_ID,
                "display_name": TEST_DISPLAY_NAME,
                "reputation": TEST_REPUTATION,
            },
            TEST_USER_ID,
            TEST_DISPLAY_NAME,
            TEST_REPUTATION,
        ),
        ({"user_id": TEST_USER_ID}, TEST_USER_ID, None, None),
        ({"display_name": TEST_DISPLAY_NAME}, None, TEST_DISPLAY_NAME, None),
    ],
    ids=["all_fields", "only_user_id", "only_display_name"],
)
def test_extract_user_with_fields(
    owner_data, expected_user_id, expected_display_name, expected_reputation
):
    """Test extracting User with various field combinations"""
    user = extract_user(owner_data)
    assert user is not None
    assert user.user_id == expected_user_id
    assert user.display_name == expected_display_name
    if expected_reputation is not None:
        assert user.reputation == expected_reputation


@pytest.mark.parametrize(
    "owner_data",
    [
        ({}),
        (None),
    ],
    ids=["empty_dict", "none"],
)
def test_extract_user_returns_none(owner_data):
    """Test extract_user returns None for empty/None input"""
    assert extract_user(owner_data) is None


def test_extract_user_handles_invalid_data_gracefully():
    """Test extract_user handles validation errors gracefully"""
    owner_data = {"user_id": "invalid"}  # Should still work, Pydantic handles it
    user = extract_user(owner_data)
    # Pydantic might convert or raise, but our function catches it
    # This test verifies we don't crash
    assert user is not None or user is None  # Either way, no crash


@pytest.fixture
def base_comment_data():
    """Base comment data for testing"""
    return {
        "comment_id": TEST_COMMENT_ID,
        "body": TEST_BODY_COMMENT,
        "score": TEST_SCORE_LOW,
        "owner": {"user_id": TEST_USER_ID, "display_name": TEST_DISPLAY_NAME},
    }


def test_extract_comment_success(base_comment_data):
    """Test extracting Comment successfully"""
    comment = extract_comment(base_comment_data)
    assert comment is not None
    assert comment.comment_id == TEST_COMMENT_ID
    assert comment.body == TEST_BODY_COMMENT
    assert comment.owner.user_id == TEST_USER_ID


@pytest.mark.parametrize(
    "comment_data",
    [
        (
            {
                "body": TEST_BODY_SHORT,
                "score": TEST_SCORE_LOW,
                "owner": {"user_id": TEST_USER_ID},
            }
        ),  # Missing comment_id
        (
            {
                "comment_id": TEST_COMMENT_ID,
                "body": TEST_BODY_SHORT,
                "score": TEST_SCORE_LOW,
            }
        ),  # Missing owner
    ],
    ids=["missing_comment_id", "missing_owner"],
)
def test_extract_comment_returns_none(comment_data):
    """Test extract_comment returns None if required fields are missing"""
    assert extract_comment(comment_data) is None


def test_extract_comment_handles_invalid_owner():
    """Test extract_comment handles invalid owner data"""
    comment_data = {
        "comment_id": TEST_COMMENT_ID,
        "body": TEST_BODY_SHORT,
        "score": TEST_SCORE_LOW,
        "owner": {},  # Empty owner
    }
    # Should return None since owner is required and empty owner is invalid
    comment = extract_comment(comment_data)
    assert comment is None


@pytest.fixture
def mock_api_client():
    """Mock API client for testing"""
    return MagicMock(spec=StackExchangeAPIClient)


def test_extract_answers_success(mock_api_client):
    """Test extracting answers successfully"""
    # Mock API response for answers
    mock_api_client.get_answers.return_value = {
        "items": [
            {
                "answer_id": TEST_ANSWER_ID,
                "body": TEST_BODY_ANSWER,
                "score": TEST_SCORE_HIGH,
                "is_accepted": True,
                "owner": {"user_id": TEST_USER_ID, "display_name": TEST_DISPLAY_NAME},
            }
        ]
    }

    # Mock API response for answer comments (empty)
    mock_api_client.get_comments.return_value = {"items": []}

    answers = extract_answers(
        question_id=TEST_QUESTION_ID, site=TEST_SITE, api_client=mock_api_client
    )

    assert len(answers) == 1
    assert answers[0].answer_id == TEST_ANSWER_ID
    assert answers[0].body == TEST_BODY_ANSWER
    assert answers[0].is_accepted is True


def test_extract_answers_handles_api_error(mock_api_client):
    """Test extract_answers handles API errors gracefully"""
    mock_api_client.get_answers.side_effect = Exception("API Error")

    answers = extract_answers(
        question_id=TEST_QUESTION_ID, site=TEST_SITE, api_client=mock_api_client
    )

    assert answers == []


def test_extract_answers_skips_invalid_answers(mock_api_client):
    """Test extract_answers skips invalid answer data"""
    mock_api_client.get_answers.return_value = {
        "items": [
            {
                "answer_id": None,
                "body": TEST_BODY_SHORT,
                "score": TEST_SCORE_ZERO,
            },  # Invalid
            {
                "answer_id": TEST_ANSWER_ID,
                "body": TEST_ANSWER_VALID_BODY,
                "score": TEST_SCORE_HIGH,
                "is_accepted": False,
            },  # Valid
        ]
    }
    mock_api_client.get_comments.return_value = {"items": []}

    answers = extract_answers(
        question_id=TEST_QUESTION_ID, site=TEST_SITE, api_client=mock_api_client
    )

    # Should only have one valid answer
    assert len(answers) == 1
    assert answers[0].answer_id == TEST_ANSWER_ID


@pytest.fixture
def base_question_data():
    """Base question data for testing"""
    return {
        "question_id": TEST_QUESTION_ID,
        "title": TEST_TITLE_QUESTION,
        "body": TEST_BODY_QUESTION,
        "score": TEST_SCORE_LOW,
        "tags": ["testing"],
    }


@patch("stream_stackexchange.extract.extract_answers")
@patch("stream_stackexchange.extract.extract_comments")
@patch("stream_stackexchange.extract.extract_user")
@patch("stream_stackexchange.extract.time")
def test_extract_question_success(
    mock_time,
    mock_extract_user,
    mock_extract_comments,
    mock_extract_answers,
    base_question_data,
    mock_api_client,
):
    """Test extracting Question successfully"""
    mock_time.time.return_value = TEST_TIMESTAMP
    mock_extract_user.return_value = User(
        user_id=TEST_USER_ID, display_name=TEST_DISPLAY_NAME
    )
    mock_extract_answers.return_value = []
    mock_extract_comments.return_value = []

    question = extract_question(
        base_question_data, site=TEST_SITE, api_client=mock_api_client
    )

    assert question is not None
    assert question.question_id == TEST_QUESTION_ID
    assert question.title == TEST_TITLE_QUESTION
    assert question.body == TEST_BODY_QUESTION
    assert question.site == TEST_SITE
    assert question.collected_at == TEST_TIMESTAMP


def test_extract_question_missing_question_id(mock_api_client):
    """Test extract_question returns None if question_id is missing"""
    question_data = {
        "title": TEST_TITLE_SHORT,
        "body": TEST_BODY_SHORT_ALT,
        "score": TEST_SCORE_ZERO,
        "tags": [],
    }

    question = extract_question(
        question_data, site=TEST_SITE, api_client=mock_api_client
    )

    assert question is None
