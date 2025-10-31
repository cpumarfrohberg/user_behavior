"""Neo4j injection operations for StackExchange data"""

from typing import Any

# Node labels for constraints
NODE_LABELS = ["User", "Question", "Answer", "Comment", "Tag"]

# Mapping of node labels to their unique property names
NODE_PROPERTY_MAP = {
    "User": "user_id",
    "Question": "question_id",
    "Answer": "answer_id",
    "Comment": "comment_id",
    "Tag": "name",
}


def set_uniqueness_constraints(tx, node_label: str) -> None:
    """Create uniqueness constraint for a node label"""
    property_name = NODE_PROPERTY_MAP.get(node_label)
    if not property_name:
        return

    query = f"""
    CREATE CONSTRAINT IF NOT EXISTS FOR (n:{node_label})
    REQUIRE n.{property_name} IS UNIQUE;
    """
    tx.run(query, {})


def _create_nodes(tx, batch_data: dict[str, Any]) -> None:
    """Create all node types in a single transaction"""
    # Users
    if users_data := batch_data.get("users"):
        query = """
        UNWIND $users AS user
        MERGE (u:User {user_id: user.user_id})
        SET u.display_name = user.display_name,
            u.reputation = user.reputation
        """
        tx.run(query, {"users": users_data})

    # Tags
    if tags_data := batch_data.get("tags"):
        query = """
        UNWIND $tags AS tag_name
        MERGE (t:Tag {name: tag_name})
        """
        tx.run(query, {"tags": tags_data})

    # Questions
    if questions_data := batch_data.get("questions"):
        query = """
        UNWIND $questions AS q
        MERGE (question:Question {question_id: q.question_id})
        SET question.title = q.title,
            question.body = q.body,
            question.score = q.score,
            question.site = q.site,
            question.collected_at = q.collected_at
        """
        tx.run(query, {"questions": questions_data})

    # Answers
    if answers_data := batch_data.get("answers"):
        query = """
        UNWIND $answers AS a
        MERGE (answer:Answer {answer_id: a.answer_id})
        SET answer.body = a.body,
            answer.score = a.score,
            answer.is_accepted = a.is_accepted
        """
        tx.run(query, {"answers": answers_data})

    # Comments
    if comments_data := batch_data.get("comments"):
        query = """
        UNWIND $comments AS c
        MERGE (comment:Comment {comment_id: c.comment_id})
        SET comment.body = c.body,
            comment.score = c.score
        """
        tx.run(query, {"comments": comments_data})


def _create_relationship(
    tx,
    relationships: list[dict[str, Any]],
    source_label: str,
    source_property: str,
    source_key: str,
    rel_type: str,
    target_label: str,
    target_property: str,
    target_key: str,
) -> None:
    """Generic function to create relationships between nodes"""
    if not relationships:
        return

    query = f"""
    UNWIND $rels AS rel
    MATCH (source:{source_label} {{{source_property}: rel.{source_key}}})
    MATCH (target:{target_label} {{{target_property}: rel.{target_key}}})
    MERGE (source)-[:{rel_type}]->(target)
    """
    tx.run(query, {"rels": relationships})


def _create_relationships(tx, batch_data: dict[str, Any]) -> None:
    """Create all relationship types in a single transaction"""
    # User relationships
    _create_relationship(
        tx,
        batch_data.get("user_question_rels", []),
        "User",
        "user_id",
        "user_id",
        "ASKED",
        "Question",
        "question_id",
        "question_id",
    )

    _create_relationship(
        tx,
        batch_data.get("user_answer_rels", []),
        "User",
        "user_id",
        "user_id",
        "ANSWERED",
        "Answer",
        "answer_id",
        "answer_id",
    )

    _create_relationship(
        tx,
        batch_data.get("user_comment_rels", []),
        "User",
        "user_id",
        "user_id",
        "COMMENTED",
        "Comment",
        "comment_id",
        "comment_id",
    )

    # Question relationships
    _create_relationship(
        tx,
        batch_data.get("question_answer_rels", []),
        "Question",
        "question_id",
        "question_id",
        "HAS_ANSWER",
        "Answer",
        "answer_id",
        "answer_id",
    )

    _create_relationship(
        tx,
        batch_data.get("question_comment_rels", []),
        "Question",
        "question_id",
        "question_id",
        "HAS_COMMENT",
        "Comment",
        "comment_id",
        "comment_id",
    )

    _create_relationship(
        tx,
        batch_data.get("question_tag_rels", []),
        "Question",
        "question_id",
        "question_id",
        "HAS_TAG",
        "Tag",
        "name",
        "tag_name",
    )

    _create_relationship(
        tx,
        batch_data.get("accepted_answer_rels", []),
        "Question",
        "question_id",
        "question_id",
        "ACCEPTED",
        "Answer",
        "answer_id",
        "answer_id",
    )

    # Answer relationships
    _create_relationship(
        tx,
        batch_data.get("answer_comment_rels", []),
        "Answer",
        "answer_id",
        "answer_id",
        "HAS_COMMENT",
        "Comment",
        "comment_id",
        "comment_id",
    )


def process_batch(tx, batch_data: dict[str, Any]) -> None:
    """
    Process a batch of questions in a single transaction:
    Create all nodes and relationships atomically

    Args:
        tx: Neo4j transaction
        batch_data: Dictionary containing all collected data for the batch
    """
    _create_nodes(tx, batch_data)
    _create_relationships(tx, batch_data)
