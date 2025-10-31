"""Business logic validation for StackExchange data"""

from config import BEHAVIOR_KEYWORDS, UX_TAGS


def is_relevant(question: dict) -> bool:
    """
    Check if a question is related to user behavior and satisfaction

    Args:
        question: Raw question dict from API

    Returns:
        True if question is relevant to user behavior
    """
    title = question.get("title", "").lower()
    body = question.get("body", "").lower()
    tags = [tag.lower() for tag in question.get("tags", [])]

    # If it has UX-related tags, it's likely behavior-related
    for tag in tags:
        if any(ux_tag in tag for ux_tag in UX_TAGS):
            return True

    # Also check for behavior keywords (but less strict)
    text_content = f"{title} {body}"
    return any(keyword in text_content for keyword in BEHAVIOR_KEYWORDS)
