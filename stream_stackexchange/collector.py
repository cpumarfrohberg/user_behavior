"""Main orchestrator for StackExchange data collection"""

import os

from config import DEFAULT_PAGES, DEFAULT_SITE, DEFAULT_TAG
from stream_stackexchange.api_client import StackExchangeAPIClient
from stream_stackexchange.extract import extract_question
from stream_stackexchange.models import Question
from stream_stackexchange.storage import MongoDBStorage
from stream_stackexchange.validate import is_relevant


class StackExchangeCollector:
    """Orchestrates StackExchange data collection pipeline"""

    def __init__(self):
        api_key = os.getenv("STACKEXCHANGE_API_KEY")
        if not api_key:
            raise ValueError("STACKEXCHANGE_API_KEY environment variable is required")

        self.api_client = StackExchangeAPIClient(api_key)
        self.storage = MongoDBStorage()

    def search_questions(
        self,
        site: str | None = None,
        tag: str | None = None,
        pages: int = DEFAULT_PAGES,
    ) -> list[Question]:
        """
        Search and extract questions from StackExchange

        Args:
            site: StackExchange site (default: DEFAULT_SITE)
            tag: Tag to filter by (default: DEFAULT_TAG)
            pages: Number of pages to fetch (default: DEFAULT_PAGES)

        Returns:
            List of Question instances
        """
        site = site or DEFAULT_SITE
        tag = tag or DEFAULT_TAG

        all_questions = []

        for page in range(1, pages + 1):
            try:
                print(f"   🔍 Fetching page {page}...")
                print(f"   📋 Site: {site}, Tag: {tag}")

                # Fetch questions from API
                data = self.api_client.get_questions(site, tag, page)
                questions = data.get("items", [])

                print(f"   📄 Found {len(questions)} questions on page {page}")

                if questions:
                    # Show sample question for debugging
                    sample = questions[0]
                    print(
                        f"   📝 Sample title: {sample.get('title', 'No title')[:60]}..."
                    )
                    print(f"   🏷️  Sample tags: {sample.get('tags', [])}")

                relevant_count = 0
                for question_dict in questions:
                    # Validate relevance
                    if not is_relevant(question_dict):
                        continue

                    # Extract question data
                    question = extract_question(question_dict, site, self.api_client)
                    if question:
                        all_questions.append(question)
                        relevant_count += 1

                print(f"   ✅ {relevant_count} questions passed relevance filter")

            except Exception as e:
                print(f"Error fetching page {page}: {e}")
                continue

        return all_questions

    def collect_and_store(
        self,
        site: str | None = None,
        tag: str | None = None,
        pages: int = DEFAULT_PAGES,
    ):
        """
        Collect questions and store in MongoDB

        Args:
            site: StackExchange site
            tag: Tag to filter by
            pages: Number of pages to fetch
        """
        questions = self.search_questions(site, tag, pages)

        if questions:
            stored_count = self.storage.store_questions(questions)
            print(f"Stored {stored_count} documents")
        else:
            print("No questions collected")

    def close(self):
        """Close connections"""
        self.storage.close()


def main():
    """Main entry point"""
    try:
        collector = StackExchangeCollector()
        collector.collect_and_store()
        collector.close()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
