"""Tests for validation logic"""

import pytest

from stream_stackexchange.validate import is_relevant


@pytest.fixture
def base_question():
    """Base question structure for testing"""
    return {"title": "Some title", "body": "Some body", "tags": []}


@pytest.mark.parametrize(
    "tags",
    [
        (["user-experience", "other-tag"]),
        (["usability"]),
        (["user-interface"]),
        (["interaction-design"]),
        (["advanced-user-experience"]),  # Partial match
    ],
    ids=[
        "user_experience",
        "usability",
        "user_interface",
        "interaction_design",
        "partial_match",
    ],
)
def test_relevant_by_ux_tag(base_question, tags):
    """Test question is relevant when it has UX-related tags"""
    question = base_question.copy()
    question["tags"] = tags
    assert is_relevant(question) is True


@pytest.mark.parametrize(
    "title,body",
    [
        ("How does user behavior affect UX?", "Some body text"),
        ("Some question", "This is about user satisfaction and frustration"),
        ("USER BEHAVIOR Questions", "Some body"),  # Case insensitive
    ],
    ids=["behavior_in_title", "behavior_in_body", "case_insensitive"],
)
def test_relevant_by_behavior_keyword(base_question, title, body):
    """Test question is relevant when title or body contains behavior keyword"""
    question = base_question.copy()
    question["title"] = title
    question["body"] = body
    assert is_relevant(question) is True


@pytest.mark.parametrize(
    "title,body,tags,expected",
    [
        (
            "How to install Python?",
            "I want to install Python",
            ["python", "installation"],
            False,
        ),
        ("", "", [], False),
        (
            "USER BEHAVIOR Questions",
            "Some body",
            ["USER-EXPERIENCE"],
            True,
        ),  # Case insensitive
    ],
    ids=["not_relevant", "empty", "case_insensitive_tag"],
)
def test_relevance_cases(title, body, tags, expected):
    """Test various relevance cases"""
    question = {"title": title, "body": body, "tags": tags}
    assert is_relevant(question) is expected
