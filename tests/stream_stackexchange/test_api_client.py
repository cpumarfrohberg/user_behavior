"""Tests for API client"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from stream_stackexchange.api_client import StackExchangeAPIClient

TEST_API_KEY = "test_key"
TEST_BASE_URL = "https://api.stackexchange.com/2.3"
TEST_SITE = "ux"
TEST_TAG = "user-behavior"
TEST_QUESTION_ID = 123
TEST_POST_ID_QUESTION = 123
TEST_POST_ID_ANSWER = 456
TEST_PAGE = 1
TEST_QUESTION_ID_SMALL = 1
TEST_ANSWER_ID_SMALL = 1
TEST_COMMENT_ID_SMALL = 1


@pytest.fixture
def mock_response():
    """Mock HTTP response for testing"""
    response = MagicMock()
    response.raise_for_status.return_value = None
    return response


@pytest.fixture
def client():
    """API client instance for testing"""
    return StackExchangeAPIClient(api_key=TEST_API_KEY)


def test_init(client):
    """Test client initialization"""
    assert client.api_key == TEST_API_KEY
    assert client.base_url == TEST_BASE_URL


@patch("stream_stackexchange.api_client.requests.get")
@patch("stream_stackexchange.api_client.time.sleep")
def test_get_questions_success(mock_sleep, mock_get, client, mock_response):
    """Test successful get_questions call"""
    mock_response.json.return_value = {
        "items": [{"question_id": TEST_QUESTION_ID_SMALL}]
    }
    mock_get.return_value = mock_response

    result = client.get_questions(site=TEST_SITE, tag=TEST_TAG, page=TEST_PAGE)

    assert result == {"items": [{"question_id": TEST_QUESTION_ID_SMALL}]}
    mock_get.assert_called_once()
    assert mock_get.call_args[1]["params"]["site"] == TEST_SITE
    assert mock_get.call_args[1]["params"]["tagged"] == TEST_TAG


@patch("stream_stackexchange.api_client.requests.get")
def test_get_questions_without_tag(mock_get, client, mock_response):
    """Test get_questions without tag"""
    mock_response.json.return_value = {"items": []}
    mock_get.return_value = mock_response

    result = client.get_questions(site=TEST_SITE, tag=None, page=TEST_PAGE)

    assert result == {"items": []}
    # Should not have "tagged" in params
    assert "tagged" not in mock_get.call_args[1]["params"]


@patch("stream_stackexchange.api_client.requests.get")
@patch("stream_stackexchange.api_client.time.sleep")
def test_get_answers_success(mock_sleep, mock_get, client, mock_response):
    """Test successful get_answers call"""
    mock_response.json.return_value = {"items": [{"answer_id": TEST_ANSWER_ID_SMALL}]}
    mock_get.return_value = mock_response

    result = client.get_answers(question_id=TEST_QUESTION_ID, site=TEST_SITE)

    assert result == {"items": [{"answer_id": TEST_ANSWER_ID_SMALL}]}
    mock_get.assert_called_once()
    assert str(TEST_QUESTION_ID) in mock_get.call_args[0][0]  # question_id in URL


@patch("stream_stackexchange.api_client.requests.get")
def test_get_answers_raises_on_error(mock_get, client, mock_response):
    """Test get_answers raises on HTTP error"""
    mock_response.raise_for_status.side_effect = requests.HTTPError("404")
    mock_get.return_value = mock_response

    with pytest.raises(requests.HTTPError):
        client.get_answers(question_id=TEST_QUESTION_ID, site=TEST_SITE)


@pytest.mark.parametrize(
    "post_id,post_type,expected_items,expected_url_part",
    [
        (
            TEST_POST_ID_QUESTION,
            "question",
            [{"comment_id": TEST_COMMENT_ID_SMALL}],
            f"questions/{TEST_POST_ID_QUESTION}/comments",
        ),
        (TEST_POST_ID_ANSWER, "answer", [], f"answers/{TEST_POST_ID_ANSWER}/comments"),
    ],
    ids=["question", "answer"],
)
@patch("stream_stackexchange.api_client.requests.get")
@patch("stream_stackexchange.api_client.time.sleep")
def test_get_comments(
    mock_sleep,
    mock_get,
    client,
    mock_response,
    post_id,
    post_type,
    expected_items,
    expected_url_part,
):
    """Test get_comments for question and answer"""
    mock_response.json.return_value = {"items": expected_items}
    mock_get.return_value = mock_response

    result = client.get_comments(post_id=post_id, site=TEST_SITE, post_type=post_type)

    assert result == {"items": expected_items}
    assert expected_url_part in mock_get.call_args[0][0]
