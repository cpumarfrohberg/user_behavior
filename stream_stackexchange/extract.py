"""Extract and transform API responses to Pydantic models"""

import time
from typing import Any

from stream_stackexchange.api_client import StackExchangeAPIClient
from stream_stackexchange.models import Answer, Comment, Question, User


def extract_user(owner_data: dict[str, Any] | None) -> User | None:
    """
    Extract User from API owner data

    Args:
        owner_data: Raw owner data from API

    Returns:
        User instance or None
    """
    if not owner_data:
        return None

    try:
        # Create User - model accepts None for all fields
        return User(**owner_data)
    except Exception:
        # If validation fails, create minimal user with available data
        return User(
            user_id=owner_data.get("user_id"),
            display_name=owner_data.get("display_name"),
            reputation=owner_data.get("reputation"),
        )


def extract_comment(comment_data: dict[str, Any]) -> Comment | None:
    """
    Extract Comment from API data

    Args:
        comment_data: Raw comment data from API

    Returns:
        Comment instance or None
    """
    comment_id = comment_data.get("comment_id")
    if not comment_id:
        return None

    owner_data = comment_data.get("owner", {})
    if not owner_data:
        return None

    try:
        owner = User(**owner_data)
    except Exception:
        # Create minimal user if validation fails
        owner = User(user_id=None, display_name=None, reputation=None)

    try:
        return Comment(
            comment_id=comment_id,
            body=comment_data.get("body", ""),
            score=comment_data.get("score", 0),
            owner=owner,
        )
    except Exception:
        return None


def extract_answers(
    question_id: int, site: str, api_client: StackExchangeAPIClient
) -> list[Answer]:
    """
    Extract answers for a question from API

    Args:
        question_id: Question ID
        site: StackExchange site
        api_client: API client instance

    Returns:
        List of Answer instances
    """
    try:
        data = api_client.get_answers(question_id, site)
        answers = []

        for answer_data in data.get("items", []):
            try:
                answer_id = answer_data.get("answer_id")
                if not answer_id:
                    continue

                owner = extract_user(answer_data.get("owner"))

                # Fetch comments for this answer
                comments_data = api_client.get_comments(answer_id, site, "answer")
                answer_comments = []
                for comment_data in comments_data.get("items", []):
                    comment = extract_comment(comment_data)
                    if comment:
                        answer_comments.append(comment)

                answers.append(
                    Answer(
                        answer_id=answer_id,
                        body=answer_data.get("body", ""),
                        score=answer_data.get("score", 0),
                        is_accepted=answer_data.get("is_accepted", False),
                        owner=owner,
                        comments=answer_comments,
                    )
                )
            except Exception as e:
                print(
                    f"Warning: Error processing answer {answer_data.get('answer_id')}: {e}"
                )
                continue

        return answers
    except Exception as e:
        print(f"Error fetching answers for question {question_id}: {e}")
        return []


def extract_comments(
    post_id: int, site: str, post_type: str, api_client: StackExchangeAPIClient
) -> list[Comment]:
    """
    Extract comments for a question or answer from API

    Args:
        post_id: Question ID or Answer ID
        site: StackExchange site
        post_type: "question" or "answer"
        api_client: API client instance

    Returns:
        List of Comment instances
    """
    try:
        data = api_client.get_comments(post_id, site, post_type)
        comments = []

        for comment_data in data.get("items", []):
            comment = extract_comment(comment_data)
            if comment:
                comments.append(comment)

        return comments
    except Exception as e:
        print(f"Error fetching comments for {post_type} {post_id}: {e}")
        return []


def extract_question(
    question_data: dict[str, Any], site: str, api_client: StackExchangeAPIClient
) -> Question | None:
    """
    Extract Question from API data with all nested relationships

    Args:
        question_data: Raw question data from API
        site: StackExchange site
        api_client: API client instance

    Returns:
        Question instance or None
    """
    try:
        question_id = question_data.get("question_id")
        if not question_id:
            return None

        # Extract owner
        owner = extract_user(question_data.get("owner"))

        # Fetch answers
        answers = extract_answers(question_id, site, api_client)

        # Fetch question comments
        question_comments = extract_comments(question_id, site, "question", api_client)

        # Create Question
        return Question(
            question_id=question_id,
            title=question_data.get("title", ""),
            body=question_data.get("body", ""),
            score=question_data.get("score", 0),
            tags=question_data.get("tags", []),
            site=site,
            owner=owner,
            answers=answers,
            comments=question_comments,
            collected_at=time.time(),
        )
    except Exception as e:
        print(f"Error processing question {question_data.get('question_id')}: {e}")
        return None
