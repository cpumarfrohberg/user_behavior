"""Tests for StackExchange Pydantic models"""

import pytest

from stream_stackexchange.models import Answer, Comment, Question, User

TEST_USER_ID = 123
TEST_USER_ID_ALT = 456
TEST_DISPLAY_NAME = "John"
TEST_DISPLAY_NAME_FULL = "John Doe"
TEST_DISPLAY_NAME_ALT = "Jane"
TEST_REPUTATION = 1000
TEST_COMMENT_ID = 456
TEST_COMMENT_ID_ALT = 111
TEST_ANSWER_ID = 789
TEST_QUESTION_ID = 1
TEST_SCORE_LOW = 5
TEST_SCORE_HIGH = 10
TEST_SCORE_ALT = 2
TEST_TIMESTAMP = 1234567890.0
TEST_SITE = "ux"
TEST_BODY_COMMENT = "Great answer!"
TEST_BODY_ANSWER = "This is the answer"
TEST_BODY_QUESTION = "Testing question body"
TEST_BODY_ANSWER_TEXT = "Answer text"
TEST_BODY_COMMENT_TEXT = "Comment text"
TEST_TITLE_QUESTION = "How to test?"
TEST_TAGS = ["testing", "pytest"]


@pytest.fixture
def sample_comment_owner():
    """Sample User for comment testing"""
    return User(user_id=TEST_USER_ID, display_name=TEST_DISPLAY_NAME)


@pytest.fixture
def base_question_data():
    """Base question data for testing"""
    return {
        "question_id": TEST_QUESTION_ID,
        "title": TEST_TITLE_QUESTION,
        "body": TEST_BODY_QUESTION,
        "score": TEST_SCORE_LOW,
        "tags": TEST_TAGS,
        "site": TEST_SITE,
        "collected_at": TEST_TIMESTAMP,
    }


@pytest.mark.parametrize(
    "display_name_input,expected",
    [
        (TEST_DISPLAY_NAME_FULL, TEST_DISPLAY_NAME_FULL),
        (f"  {TEST_DISPLAY_NAME_FULL}  ", TEST_DISPLAY_NAME_FULL),
        (None, None),
        ("", None),  # Empty string becomes None
    ],
    ids=["normal", "with_whitespace", "none", "empty_string"],
)
def test_user_normalizes_display_name(display_name_input, expected):
    """Test display_name normalization (trim whitespace)"""
    user = User(
        user_id=TEST_USER_ID,
        display_name=display_name_input,
        reputation=TEST_REPUTATION,
    )
    assert user.display_name == expected


@pytest.mark.parametrize(
    "user_data,expected_fields",
    [
        (
            {
                "user_id": TEST_USER_ID,
                "display_name": TEST_DISPLAY_NAME_FULL,
                "reputation": TEST_REPUTATION,
            },
            {
                "user_id": TEST_USER_ID,
                "display_name": TEST_DISPLAY_NAME_FULL,
                "reputation": TEST_REPUTATION,
            },
        ),
        (
            {"user_id": TEST_USER_ID},
            {"user_id": TEST_USER_ID, "display_name": None, "reputation": None},
        ),
    ],
    ids=["all_fields", "only_user_id"],
)
def test_user_creation(user_data, expected_fields):
    """Test User creation with various field combinations"""
    user = User(**user_data)
    for field, expected_value in expected_fields.items():
        assert getattr(user, field) == expected_value


@pytest.mark.parametrize(
    "body_input,expected",
    [
        (TEST_BODY_COMMENT, TEST_BODY_COMMENT),
        (f"  {TEST_BODY_COMMENT}  ", TEST_BODY_COMMENT),
        (None, ""),
        ("", ""),
    ],
    ids=["normal", "with_whitespace", "none", "empty_string"],
)
def test_comment_normalizes_body(sample_comment_owner, body_input, expected):
    """Test body normalization (trim whitespace, handle None)"""
    comment = Comment(
        comment_id=TEST_COMMENT_ID,
        body=body_input,
        score=TEST_SCORE_LOW,
        owner=sample_comment_owner,
    )
    assert comment.body == expected


def test_comment_creation(sample_comment_owner):
    """Test creating Comment"""
    comment = Comment(
        comment_id=TEST_COMMENT_ID,
        body=TEST_BODY_COMMENT,
        score=TEST_SCORE_LOW,
        owner=sample_comment_owner,
    )
    assert comment.comment_id == TEST_COMMENT_ID
    assert comment.body == TEST_BODY_COMMENT
    assert comment.score == TEST_SCORE_LOW
    assert comment.owner.user_id == TEST_USER_ID


@pytest.mark.parametrize(
    "body_input,expected",
    [
        (TEST_BODY_ANSWER, TEST_BODY_ANSWER),
        (f"  {TEST_BODY_ANSWER}  ", TEST_BODY_ANSWER),
        (None, ""),
    ],
    ids=["normal", "with_whitespace", "none"],
)
def test_answer_normalizes_body(body_input, expected):
    """Test body normalization (trim whitespace)"""
    answer = Answer(
        answer_id=TEST_ANSWER_ID,
        body=body_input,
        score=TEST_SCORE_HIGH,
        is_accepted=False,
    )
    assert answer.body == expected


@pytest.mark.parametrize(
    "has_owner,expected_owner_id",
    [(False, None), (True, TEST_USER_ID)],
    ids=["without_owner", "with_owner"],
)
def test_answer_with_and_without_owner(has_owner, expected_owner_id):
    """Test Answer with and without owner"""
    owner = (
        User(user_id=TEST_USER_ID, display_name=TEST_DISPLAY_NAME)
        if has_owner
        else None
    )
    answer = Answer(
        answer_id=TEST_ANSWER_ID,
        body=TEST_BODY_ANSWER,
        score=TEST_SCORE_HIGH,
        is_accepted=False,
        owner=owner,
    )
    if expected_owner_id:
        assert answer.owner.user_id == expected_owner_id
    else:
        assert answer.owner is None
    assert answer.comments == []


def test_question_creation(base_question_data):
    """Test creating Question"""
    question = Question(**base_question_data)
    assert question.question_id == TEST_QUESTION_ID
    assert question.title == TEST_TITLE_QUESTION
    assert question.body == TEST_BODY_QUESTION
    assert question.score == TEST_SCORE_LOW
    assert question.tags == TEST_TAGS
    assert question.site == TEST_SITE
    assert question.answers == []
    assert question.comments == []


@pytest.mark.parametrize(
    "field,input_value,expected",
    [
        ("title", f"  {TEST_TITLE_QUESTION}  ", TEST_TITLE_QUESTION),
        ("body", f"  {TEST_BODY_QUESTION}  ", TEST_BODY_QUESTION),
        ("site", f"  {TEST_SITE}  ", TEST_SITE),
    ],
    ids=["title", "body", "site"],
)
def test_question_normalizes_strings(base_question_data, field, input_value, expected):
    """Test string field normalization (trim whitespace)"""
    base_question_data[field] = input_value
    question = Question(**base_question_data)
    assert getattr(question, field) == expected


@pytest.mark.parametrize(
    "tags_input,expected_tags",
    [
        (["testing", "pytest"], ["testing", "pytest"]),
        (["testing", "  pytest  ", "testing", "", "  "], ["testing", "pytest"]),
        ([], []),
        (["tag1", "tag1", "tag2"], ["tag1", "tag2"]),  # Deduplication
    ],
    ids=["normal", "with_whitespace_and_duplicates", "empty", "duplicates"],
)
def test_question_normalizes_tags(base_question_data, tags_input, expected_tags):
    """Test tag normalization (deduplicate, remove empty, trim)"""
    base_question_data["tags"] = tags_input
    question = Question(**base_question_data)
    assert set(question.tags) == set(expected_tags)
    assert len(question.tags) == len(expected_tags)


def test_question_with_nested_data(base_question_data):
    """Test Question with owner, answers, and comments"""
    owner = User(user_id=TEST_USER_ID, display_name=TEST_DISPLAY_NAME)
    answer = Answer(
        answer_id=TEST_ANSWER_ID,
        body=TEST_BODY_ANSWER_TEXT,
        score=TEST_SCORE_HIGH,
        is_accepted=True,
    )
    comment_owner = User(user_id=TEST_USER_ID_ALT, display_name=TEST_DISPLAY_NAME_ALT)
    comment = Comment(
        comment_id=TEST_COMMENT_ID_ALT,
        body=TEST_BODY_COMMENT_TEXT,
        score=TEST_SCORE_ALT,
        owner=comment_owner,
    )

    base_question_data.update(
        {
            "owner": owner,
            "answers": [answer],
            "comments": [comment],
        }
    )
    question = Question(**base_question_data)

    assert question.owner.user_id == TEST_USER_ID
    assert len(question.answers) == 1
    assert question.answers[0].answer_id == TEST_ANSWER_ID
    assert len(question.comments) == 1
    assert question.comments[0].comment_id == TEST_COMMENT_ID_ALT
