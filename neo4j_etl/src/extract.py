"""Extract and transform StackExchange data from MongoDB for Neo4j injection"""

from typing import Any

from neo4j_etl.src.validate import (
    validate_answer,
    validate_comment,
    validate_question,
    validate_tag,
    validate_user,
)


def _add_user_if_new(
    owner_data: dict[str, Any] | None,
    users_data: list[dict[str, Any]],
    seen_user_ids: set[int],
) -> dict[str, Any] | None:
    """
    Helper to validate and add user if not already seen.
    Returns user_data if valid (even if already seen), None otherwise.
    """
    if not owner_data:
        return None

    user_data = validate_user(owner_data)
    if not user_data:
        return None

    # Add to list only if new
    if user_data["user_id"] not in seen_user_ids:
        users_data.append(user_data)
        seen_user_ids.add(user_data["user_id"])

    # Always return user_data if valid (needed for relationships)
    return user_data


def collect_batch_data(questions_batch: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Collect and validate all data for a batch of questions

    Args:
        questions_batch: List of question documents from MongoDB

    Returns:
        Dictionary with all nodes and relationships data ready for Neo4j injection
    """
    # Collections for nodes
    users_data = []
    tags_data = []
    questions_data = []
    answers_data = []
    comments_data = []

    # Collections for relationships
    user_question_rels = []
    user_answer_rels = []
    user_comment_rels = []
    question_answer_rels = []
    question_comment_rels = []
    answer_comment_rels = []
    question_tag_rels = []
    accepted_answer_rels = []

    # Track unique users and tags to avoid duplicates
    seen_user_ids = set()
    seen_tags = set()

    # Process each question
    for question_doc in questions_batch:
        # Validate and extract question data
        question_data = validate_question(question_doc)
        if not question_data:
            continue

        question_id = question_data["question_id"]
        questions_data.append(question_data)

        # Process owner/user
        user_data = _add_user_if_new(
            question_doc.get("owner"), users_data, seen_user_ids
        )
        if user_data:
            user_question_rels.append(
                {"user_id": user_data["user_id"], "question_id": question_id}
            )

        # Process tags
        tags = question_doc.get("tags", [])
        for tag in tags:
            validated_tag = validate_tag(tag)
            if validated_tag and validated_tag not in seen_tags:
                tags_data.append(validated_tag)
                seen_tags.add(validated_tag)
                question_tag_rels.append(
                    {"question_id": question_id, "tag_name": validated_tag}
                )

        # Process answers
        answers = question_doc.get("answers", [])
        for answer_doc in answers:
            answer_data = validate_answer(answer_doc)
            if not answer_data:
                continue

            answer_id = answer_data["answer_id"]
            answers_data.append(answer_data)
            question_answer_rels.append(
                {"question_id": question_id, "answer_id": answer_id}
            )

            # Accepted answer relationship
            if answer_data.get("is_accepted"):
                accepted_answer_rels.append(
                    {"question_id": question_id, "answer_id": answer_id}
                )

            # Answer owner
            user_data = _add_user_if_new(
                answer_doc.get("owner"), users_data, seen_user_ids
            )
            if user_data:
                user_answer_rels.append(
                    {"user_id": user_data["user_id"], "answer_id": answer_id}
                )

            # Answer comments
            answer_comments = answer_doc.get("comments", [])
            for comment_doc in answer_comments:
                comment_data = validate_comment(comment_doc)
                if not comment_data:
                    continue

                comment_id = comment_data["comment_id"]
                comments_data.append(comment_data)
                answer_comment_rels.append(
                    {"answer_id": answer_id, "comment_id": comment_id}
                )

                # Comment owner
                user_data = _add_user_if_new(
                    comment_doc.get("owner"), users_data, seen_user_ids
                )
                if user_data:
                    user_comment_rels.append(
                        {"user_id": user_data["user_id"], "comment_id": comment_id}
                    )

        # Process question comments
        question_comments = question_doc.get("comments", [])
        for comment_doc in question_comments:
            comment_data = validate_comment(comment_doc)
            if not comment_data:
                continue

            comment_id = comment_data["comment_id"]
            comments_data.append(comment_data)
            question_comment_rels.append(
                {"question_id": question_id, "comment_id": comment_id}
            )

            # Comment owner
            user_data = _add_user_if_new(
                comment_doc.get("owner"), users_data, seen_user_ids
            )
            if user_data:
                user_comment_rels.append(
                    {"user_id": user_data["user_id"], "comment_id": comment_id}
                )

    return {
        "users": users_data,
        "tags": tags_data,
        "questions": questions_data,
        "answers": answers_data,
        "comments": comments_data,
        "user_question_rels": user_question_rels,
        "user_answer_rels": user_answer_rels,
        "user_comment_rels": user_comment_rels,
        "question_answer_rels": question_answer_rels,
        "question_comment_rels": question_comment_rels,
        "answer_comment_rels": answer_comment_rels,
        "question_tag_rels": question_tag_rels,
        "accepted_answer_rels": accepted_answer_rels,
    }
