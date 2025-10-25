import os
import time
from typing import Dict, List

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

from config import DEFAULT_SITE, DEFAULT_TAG, MONGODB_DB, MONGODB_URI, APIEndpoint

load_dotenv()

DEFAULT_PAGES = 2  # in StackExchange the first 2 pages contain the highest-quality, most relevant content


class StackExchangeCollector:
    """Collects StackExchange content and stores in MongoDB"""

    def __init__(self):
        self.api_key = os.getenv("STACKEXCHANGE_API_KEY")
        if not self.api_key:
            raise ValueError("STACKEXCHANGE_API_KEY environment variable is required")

        self.client = MongoClient(MONGODB_URI)
        self.db = self.client[MONGODB_DB]
        self.collection = self.db["stackexchange_content"]

        self.base_url = APIEndpoint.BASE_URL.value
        self.questions_endpoint = APIEndpoint.QUESTIONS.value

    def search_questions(
        self, site: str = None, tag: str = None, pages: int = DEFAULT_PAGES
    ) -> List[Dict]:
        site = site or DEFAULT_SITE
        tag = tag or DEFAULT_TAG

        all_questions = []

        for page in range(1, pages + 1):
            url = f"{self.base_url}/{self.questions_endpoint}"
            params = {
                "site": site,
                "sort": "votes",
                "order": "desc",
                "pagesize": 50,
                "page": page,
                "key": self.api_key,
                "filter": "withbody",
            }

            if tag:
                params["tagged"] = tag

            try:
                print(f"   🔍 Fetching: {url}")
                print(f"   📋 Params: {params}")

                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()
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
                for question in questions:
                    if self._is_relevant(question):
                        question_data = self._process_question(question, site)
                        if question_data:
                            all_questions.append(question_data)
                            relevant_count += 1

                print(f"   ✅ {relevant_count} questions passed relevance filter")

                time.sleep(1)

            except Exception as e:
                print(f"Error fetching page {page}: {e}")
                continue

        return all_questions

    def _is_relevant(self, question: Dict) -> bool:
        """Check if a question is related to user behavior and satisfaction"""
        title = question.get("title", "").lower()
        body = question.get("body", "").lower()
        tags = [tag.lower() for tag in question.get("tags", [])]

        # If it has UX-related tags, it's likely behavior-related
        ux_tags = [
            "usability",
            "user-interface",
            "user-experience",
            "interaction-design",
            "user-research",
            "user-testing",
            "user-feedback",
            "user-satisfaction",
        ]

        for tag in tags:
            if any(ux_tag in tag for ux_tag in ux_tags):
                return True

        # Also check for behavior keywords (but less strict)
        behavior_keywords = [
            "behavior",
            "satisfaction",
            "frustration",
            "user",
            "usability",
        ]
        text_content = f"{title} {body}"

        return any(keyword in text_content for keyword in behavior_keywords)

    def _process_question(self, question: Dict, site: str) -> Dict:
        try:
            question_id = question.get("question_id")
            answers = self._get_answers(question_id, site)

            return {
                "question_id": question_id,
                "title": question.get("title", ""),
                "body": question.get("body", ""),
                "score": question.get("score", 0),
                "tags": question.get("tags", []),
                "site": site,
                "answers": answers,
                "collected_at": time.time(),
            }

        except Exception as e:
            print(f"Error processing question {question_id}: {e}")
            return None

    def _get_answers(self, question_id: int, site: str) -> List[Dict]:
        try:
            url = f"{self.base_url}/{self.questions_endpoint}/{question_id}/answers"
            params = {
                "site": site,
                "key": self.api_key,
                "filter": "withbody",
                "sort": "votes",
                "order": "desc",
            }

            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            answers = []
            for answer in data.get("items", []):
                answers.append(
                    {
                        "answer_id": answer.get("answer_id"),
                        "body": answer.get("body", ""),
                        "score": answer.get("score", 0),
                        "is_accepted": answer.get("is_accepted", False),
                    }
                )

            time.sleep(1)
            return answers

        except Exception as e:
            print(f"Error fetching answers for question {question_id}: {e}")
            return []

    def _store_in_mongodb(self, documents: List[Dict]) -> int:
        if not documents:
            return 0

        try:
            self.collection.create_index("question_id", unique=True)

            stored_count = 0
            for doc in documents:
                try:
                    self.collection.insert_one(doc)
                    stored_count += 1
                except Exception:
                    # Update existing document
                    self.collection.update_one(
                        {"question_id": doc["question_id"]}, {"$set": doc}
                    )
                    stored_count += 1

            return stored_count

        except Exception as e:
            print(f"Error storing in MongoDB: {e}")
            return 0

    def collect_and_store(
        self, site: str = None, tag: str = None, pages: int = DEFAULT_PAGES
    ):
        questions = self.search_questions(site, tag, pages)

        if questions:
            stored_count = self._store_in_mongodb(questions)
            print(f"Stored {stored_count} documents")
        else:
            print("No questions collected")

    def close(self):
        self.client.close()


def main():
    try:
        collector = StackExchangeCollector()
        collector.collect_and_store()
        collector.close()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
