"""Tests for Neo4j ETL data extraction functions"""

import pytest

from neo4j_etl.src.extract import collect_batch_data

# Constants
TEST_USER_ID = 123
TEST_USER_ID_ALT = 456
TEST_DISPLAY_NAME = "John Doe"
TEST_REPUTATION = 1000

TEST_COMMENT_ID = 789
TEST_BODY_SHORT = "Short comment"
TEST_SCORE = 5

TEST_ANSWER_ID = 234
TEST_ANSWER_BODY_SHORT = "Short answer"
TEST_IS_ACCEPTED = True

TEST_QUESTION_ID = 345
TEST_QUESTION_ID_ALT = 678
TEST_TITLE = "How to test?"
TEST_QUESTION_BODY_SHORT = "Short question"
TEST_SITE = "stackoverflow"
TEST_COLLECTED_AT = 1234567890.0

TEST_TAG_VALID = "python"
TEST_TAG_VALID_ALT = "testing"


@pytest.fixture
def base_question_doc():
    """Base question document from MongoDB"""
    return {
        "question_id": TEST_QUESTION_ID,
        "title": TEST_TITLE,
        "body": TEST_QUESTION_BODY_SHORT,
        "score": TEST_SCORE,
        "tags": [TEST_TAG_VALID],
        "site": TEST_SITE,
        "collected_at": TEST_COLLECTED_AT,
        "owner": {
            "user_id": TEST_USER_ID,
            "display_name": TEST_DISPLAY_NAME,
            "reputation": TEST_REPUTATION,
        },
        "answers": [],
        "comments": [],
    }


def test_collect_batch_data_empty():
    """Test collect_batch_data with empty batch"""
    result = collect_batch_data([])

    assert result["questions"] == []
    assert result["users"] == []
    assert result["tags"] == []


def test_collect_batch_data_simple_question(base_question_doc):
    """Test collect_batch_data with a simple question (no answers/comments)"""
    result = collect_batch_data([base_question_doc])

    assert len(result["questions"]) == 1
    assert result["questions"][0]["question_id"] == TEST_QUESTION_ID
    assert len(result["users"]) == 1
    assert len(result["tags"]) == 1
    assert len(result["user_question_rels"]) == 1
    assert len(result["question_tag_rels"]) == 1


def test_collect_batch_data_with_answer(base_question_doc):
    """Test collect_batch_data with question and answer"""
    base_question_doc["answers"] = [
        {
            "answer_id": TEST_ANSWER_ID,
            "body": TEST_ANSWER_BODY_SHORT,
            "score": TEST_SCORE,
            "is_accepted": TEST_IS_ACCEPTED,
            "owner": {"user_id": TEST_USER_ID_ALT, "display_name": "Jane"},
            "comments": [],
        }
    ]

    result = collect_batch_data([base_question_doc])

    assert len(result["answers"]) == 1
    assert result["answers"][0]["answer_id"] == TEST_ANSWER_ID
    assert result["answers"][0]["is_accepted"] == TEST_IS_ACCEPTED
    assert len(result["question_answer_rels"]) == 1
    assert len(result["accepted_answer_rels"]) == 1
    assert len(result["user_answer_rels"]) == 1


def test_collect_batch_data_with_comment(base_question_doc):
    """Test collect_batch_data with question and comment"""
    base_question_doc["comments"] = [
        {
            "comment_id": TEST_COMMENT_ID,
            "body": TEST_BODY_SHORT,
            "score": TEST_SCORE,
            "owner": {"user_id": TEST_USER_ID_ALT, "display_name": "Jane"},
        }
    ]

    result = collect_batch_data([base_question_doc])

    assert len(result["comments"]) == 1
    assert len(result["question_comment_rels"]) == 1
    assert len(result["user_comment_rels"]) == 1


def test_collect_batch_data_user_deduplication(base_question_doc):
    """Test that same user is not duplicated across multiple questions"""
    question_doc_2 = base_question_doc.copy()
    question_doc_2["question_id"] = TEST_QUESTION_ID_ALT

    result = collect_batch_data([base_question_doc, question_doc_2])

    assert len(result["users"]) == 1
    assert len(result["user_question_rels"]) == 2


def test_collect_batch_data_tag_deduplication(base_question_doc):
    """Test that same tag is not duplicated"""
    base_question_doc["tags"] = [TEST_TAG_VALID, TEST_TAG_VALID, TEST_TAG_VALID_ALT]

    result = collect_batch_data([base_question_doc])

    assert len(result["tags"]) == 2
    assert set(result["tags"]) == {TEST_TAG_VALID, TEST_TAG_VALID_ALT}


def test_collect_batch_data_skips_invalid_question(base_question_doc):
    """Test that invalid questions are skipped"""
    invalid_question = {"invalid": "data"}  # Missing question_id

    result = collect_batch_data([base_question_doc, invalid_question])

    assert len(result["questions"]) == 1


def test_collect_batch_data_question_without_owner(base_question_doc):
    """Test question without owner (anonymous)"""
    base_question_doc.pop("owner")

    result = collect_batch_data([base_question_doc])

    assert len(result["questions"]) == 1
    assert len(result["users"]) == 0
    assert len(result["user_question_rels"]) == 0
