"""Validation functions for Neo4j ETL -
Trusts MongoDB data structure, validates only Neo4j-specific requirements
"""

from typing import Any

# Neo4j-specific constants
QUESTION_BODY_MAX_LENGTH = 500
ANSWER_BODY_MAX_LENGTH = 500
COMMENT_BODY_MAX_LENGTH = 200


def _truncate_text(text: str | None, max_length: int) -> str:
    """Truncate text to max_length if needed"""
    if not text:
        return ""
    text_str = str(text)
    return text_str[:max_length] if len(text_str) > max_length else text_str


def _validate_post_with_body(
    data: dict[str, Any],
    id_field_name: str,
    body_max_length: int,
    additional_fields: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Helper to validate posts with body truncation (questions, answers, comments)

    Args:
        data: Post data dict from MongoDB
        id_field_name: Name of the ID field (e.g., "question_id", "answer_id")
        body_max_length: Max length for body truncation
        additional_fields: Dict of field_name -> default_value to include in result

    Returns:
        Validated post dict with truncated body or None if invalid
    """
    post_id = data.get(id_field_name)
    if not post_id:
        return None

    body = data.get("body", "")
    result = {
        id_field_name: post_id,
        "body": _truncate_text(body, body_max_length),
        "score": data.get("score", 0),
    }

    if additional_fields:
        for field_name, default_value in additional_fields.items():
            result[field_name] = data.get(field_name, default_value)

    return result


def validate_user(user_data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Validate User data for Neo4j injection

    Args:
        user_data: User dict from MongoDB

    Returns:
        Validated user dict or None if invalid
    """
    # User is optional, so if user_id is missing, that's okay
    user_id = user_data.get("user_id")
    if user_id is None:
        return None  # Skip users without IDs

    return {
        "user_id": user_id,
        "display_name": user_data.get("display_name"),
        "reputation": user_data.get("reputation"),
    }


def validate_comment(comment_data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Validate Comment data for Neo4j injection

    Args:
        comment_data: Comment dict from MongoDB

    Returns:
        Validated comment dict with truncated body or None if invalid
    """
    comment_id = comment_data.get("comment_id")
    if not comment_id:
        return None

    body = comment_data.get("body", "")
    return {
        "comment_id": comment_id,
        "body": _truncate_text(body, COMMENT_BODY_MAX_LENGTH),
        "score": comment_data.get("score", 0),
    }


def validate_answer(answer_data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Validate Answer data for Neo4j injection

    Args:
        answer_data: Answer dict from MongoDB

    Returns:
        Validated answer dict with truncated body or None if invalid
    """
    return _validate_post_with_body(
        answer_data,
        "answer_id",
        ANSWER_BODY_MAX_LENGTH,
        {"is_accepted": False},
    )


def validate_question(question_data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Validate Question data for Neo4j injection

    Args:
        question_data: Question dict from MongoDB

    Returns:
        Validated question dict with truncated body or None if invalid
    """
    return _validate_post_with_body(
        question_data,
        "question_id",
        QUESTION_BODY_MAX_LENGTH,
        {
            "title": "",
            "site": "",
            "collected_at": 0.0,
        },
    )


def validate_tag(tag_name: str | None) -> str | None:
    """
    Validate Tag name for Neo4j injection

    Args:
        tag_name: Tag name string

    Returns:
        Normalized tag name or None if invalid
    """
    if not tag_name:
        return None
    tag_str = str(tag_name).strip()
    return tag_str if tag_str else None
