from unittest.mock import MagicMock

import pytest

from neo4j_etl.src.inject import (
    NODE_LABELS,
    NODE_PROPERTY_MAP,
    process_batch,
    set_uniqueness_constraints,
)

TEST_USER_ID = 123
TEST_DISPLAY_NAME = "John Doe"
TEST_REPUTATION = 1000

TEST_COMMENT_ID = 789
TEST_BODY_SHORT = "Short comment"
TEST_SCORE = 5

TEST_ANSWER_ID = 234
TEST_ANSWER_BODY_SHORT = "Short answer"
TEST_IS_ACCEPTED = True

TEST_QUESTION_ID = 345
TEST_TITLE = "How to test?"
TEST_QUESTION_BODY_SHORT = "Short question"
TEST_SITE = "stackoverflow"
TEST_COLLECTED_AT = 1234567890.0

TEST_TAG_VALID = "python"


@pytest.fixture
def mock_tx():
    """Mock Neo4j transaction"""
    return MagicMock()


@pytest.fixture
def batch_data():
    """Sample batch data for testing"""
    return {
        "users": [
            {
                "user_id": TEST_USER_ID,
                "display_name": TEST_DISPLAY_NAME,
                "reputation": TEST_REPUTATION,
            }
        ],
        "tags": [TEST_TAG_VALID],
        "questions": [
            {
                "question_id": TEST_QUESTION_ID,
                "title": TEST_TITLE,
                "body": TEST_QUESTION_BODY_SHORT,
                "score": TEST_SCORE,
                "site": TEST_SITE,
                "collected_at": TEST_COLLECTED_AT,
            }
        ],
        "answers": [
            {
                "answer_id": TEST_ANSWER_ID,
                "body": TEST_ANSWER_BODY_SHORT,
                "score": TEST_SCORE,
                "is_accepted": TEST_IS_ACCEPTED,
            }
        ],
        "comments": [
            {
                "comment_id": TEST_COMMENT_ID,
                "body": TEST_BODY_SHORT,
                "score": TEST_SCORE,
            }
        ],
        "user_question_rels": [
            {"user_id": TEST_USER_ID, "question_id": TEST_QUESTION_ID}
        ],
        "question_answer_rels": [
            {"question_id": TEST_QUESTION_ID, "answer_id": TEST_ANSWER_ID}
        ],
        "accepted_answer_rels": [
            {"question_id": TEST_QUESTION_ID, "answer_id": TEST_ANSWER_ID}
        ],
    }


def test_set_uniqueness_constraints(mock_tx):
    """Test set_uniqueness_constraints creates correct constraint"""
    set_uniqueness_constraints(mock_tx, "User")

    assert mock_tx.run.called
    call_args = mock_tx.run.call_args
    query = call_args[0][0]

    assert "CREATE CONSTRAINT" in query
    assert "User" in query
    assert "user_id" in query
    assert "IS UNIQUE" in query


@pytest.mark.parametrize(
    "node_label,expected_property",
    [
        ("User", "user_id"),
        ("Question", "question_id"),
        ("Answer", "answer_id"),
        ("Comment", "comment_id"),
        ("Tag", "name"),
    ],
    ids=["user", "question", "answer", "comment", "tag"],
)
def test_set_uniqueness_constraints_all_labels(mock_tx, node_label, expected_property):
    set_uniqueness_constraints(mock_tx, node_label)

    assert mock_tx.run.called
    query = mock_tx.run.call_args[0][0]
    assert node_label in query
    assert expected_property in query


def test_set_uniqueness_constraints_invalid_label(mock_tx):
    """Test set_uniqueness_constraints skips invalid labels"""
    set_uniqueness_constraints(mock_tx, "InvalidLabel")

    assert not mock_tx.run.called


def test_process_batch_creates_nodes(mock_tx, batch_data):
    process_batch(mock_tx, batch_data)

    # Should call tx.run multiple times (once per node type + relationships)
    assert mock_tx.run.call_count >= 5  # At least 5 node types + relationships

    # Verify node creation queries were called
    call_args_list = [call[0][0] for call in mock_tx.run.call_args_list]

    assert any("MERGE (u:User" in query for query in call_args_list)
    assert any("MERGE (t:Tag" in query for query in call_args_list)
    assert any("MERGE (question:Question" in query for query in call_args_list)
    assert any("MERGE (answer:Answer" in query for query in call_args_list)
    assert any("MERGE (comment:Comment" in query for query in call_args_list)


def test_process_batch_creates_relationships(mock_tx, batch_data):
    process_batch(mock_tx, batch_data)

    call_args_list = [call[0][0] for call in mock_tx.run.call_args_list]

    # Verify relationship queries were called
    assert any("-[:ASKED]->" in query or "ASKED" in query for query in call_args_list)
    assert any(
        "-[:HAS_ANSWER]->" in query or "HAS_ANSWER" in query for query in call_args_list
    )
    assert any(
        "-[:ACCEPTED]->" in query or "ACCEPTED" in query for query in call_args_list
    )


def test_process_batch_empty_data(mock_tx):
    empty_batch = {
        "users": [],
        "tags": [],
        "questions": [],
        "answers": [],
        "comments": [],
    }

    process_batch(mock_tx, empty_batch)

    # Should still run (no errors), but may not call tx.run if all empty
    # The function should handle empty data gracefully


def test_process_batch_missing_keys(mock_tx):
    partial_batch = {
        "questions": [
            {
                "question_id": TEST_QUESTION_ID,
                "title": TEST_TITLE,
                "body": TEST_QUESTION_BODY_SHORT,
                "score": TEST_SCORE,
                "site": TEST_SITE,
                "collected_at": TEST_COLLECTED_AT,
            }
        ],
        # Missing other keys
    }

    process_batch(mock_tx, partial_batch)

    # Should handle missing keys gracefully
    assert mock_tx.run.called
