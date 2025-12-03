"""StackExchange data collection functions"""

import os

from config import DEFAULT_PAGES, DEFAULT_SITE, DEFAULT_TAG
from stream_stackexchange.api_client import StackExchangeAPIClient
from stream_stackexchange.extract import extract_question
from stream_stackexchange.storage import MongoDBStorage
from stream_stackexchange.validate import is_relevant


def search_questions(
    api_client: StackExchangeAPIClient,
    storage: MongoDBStorage,
    site: str | None = None,
    tag: str | None = None,
    pages: int = DEFAULT_PAGES,
) -> int:
    """
    Search and extract questions from StackExchange, storing incrementally

    Args:
        api_client: StackExchange API client
        storage: MongoDB storage instance
        site: StackExchange site (default: DEFAULT_SITE)
        tag: Tag to filter by (default: DEFAULT_TAG)
        pages: Number of pages to fetch (default: DEFAULT_PAGES)

    Returns:
        Number of questions stored (int)
    """
    site = site or DEFAULT_SITE
    tag = tag or DEFAULT_TAG
    total_stored = 0

    for page in range(1, pages + 1):
        try:
            data = api_client.get_questions(site, tag, page)
            questions = data.get("items", [])

            # Collect and validate questions for this page
            page_questions = []
            for question_dict in questions:
                if not is_relevant(question_dict):
                    continue
                question = extract_question(question_dict, site, api_client)
                if question:
                    page_questions.append(question)

            # Store immediately after processing page
            if page_questions:
                try:
                    stored_count = storage.store_questions(page_questions)
                    total_stored += stored_count
                    print(
                        f"Page {page}: Stored {stored_count} questions (total: {total_stored})"
                    )
                except Exception as e:
                    print(f"Error storing page {page}: {e}")

        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            continue

    return total_stored


def collect_and_store(
    site: str | None = None,
    tag: str | None = None,
    pages: int = DEFAULT_PAGES,
) -> int:
    """
    Collect questions and store in MongoDB

    Args:
        site: StackExchange site
        tag: Tag to filter by
        pages: Number of pages to fetch

    Returns:
        Number of questions stored
    """
    api_key = os.getenv("STACKEXCHANGE_API_KEY")
    if not api_key:
        raise ValueError("STACKEXCHANGE_API_KEY environment variable is required")

    api_client = StackExchangeAPIClient(api_key)
    storage = MongoDBStorage()

    try:
        total_stored = search_questions(api_client, storage, site, tag, pages)
        if total_stored > 0:
            print(f"✅ Total stored: {total_stored} documents")
        return total_stored
    finally:
        storage.close()


def main():
    try:
        collect_and_store()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
