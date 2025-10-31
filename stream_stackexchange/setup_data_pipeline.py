import os
import time

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from config import DEFAULT_SITE, DEFAULT_TAG, MONGODB_DB, MONGODB_URI, APIEndpoint

load_dotenv()

DEFAULT_PAGES = 2  # in StackExchange the first 2 pages contain the highest-quality, most relevant content


class User(BaseModel):
    """User/Owner information from StackExchange"""

    user_id: int | None = None
    display_name: str | None = None
    reputation: int | None = None

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, v):
        """Trim whitespace, handle None"""
        return v.strip() if v and isinstance(v, str) else None


class Comment(BaseModel):
    """Comment on a question or answer"""

    comment_id: int
    body: str
    score: int
    owner: User

    @field_validator("body", mode="before")
    @classmethod
    def normalize_body(cls, v):
        """Trim whitespace, ensure non-empty"""
        if v is None:
            return ""
        body = str(v).strip()
        return body if body else ""


class Answer(BaseModel):
    """Answer to a question"""

    answer_id: int
    body: str
    score: int
    is_accepted: bool
    owner: User | None = None
    comments: list[Comment] = Field(default_factory=list)

    @field_validator("body", mode="before")
    @classmethod
    def normalize_body(cls, v):
        """Trim whitespace"""
        return str(v).strip() if v else ""


class Question(BaseModel):
    """StackExchange question with answers and metadata"""

    question_id: int
    title: str
    body: str
    score: int
    tags: list[str] = Field(default_factory=list)
    site: str
    owner: User | None = None
    answers: list[Answer] = Field(default_factory=list)
    comments: list[Comment] = Field(default_factory=list)
    collected_at: float

    @field_validator("title", "body", "site", mode="before")
    @classmethod
    def normalize_strings(cls, v):
        """Trim whitespace"""
        return str(v).strip() if v else ""

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, v):
        """Remove empty tags, deduplicate"""
        if not v:
            return []
        tags = [str(t).strip() for t in v if t and str(t).strip()]
        return list(set(tags))  # Deduplicate


class StackExchangeCollector:
    """Collects StackExchange content and stores in MongoDB"""

    def __init__(self):
        self.api_key = os.getenv("STACKEXCHANGE_API_KEY")
        if not self.api_key:
            raise ValueError("STACKEXCHANGE_API_KEY environment variable is required")

        self.client = MongoClient(MONGODB_URI)
        self.db = self.client[MONGODB_DB]
        self.collection = self.db["stackexchange_content"]

        self.base_url = APIEndpoint.BASE_URL
        self.questions_endpoint = APIEndpoint.QUESTIONS
        self.comments_endpoint = APIEndpoint.COMMENTS

    def search_questions(
        self, site: str = None, tag: str = None, pages: int = DEFAULT_PAGES
    ) -> list[Question]:
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

    def _is_relevant(self, question: dict) -> bool:
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

    def _process_question(self, question: dict, site: str) -> Question | None:
        """Process question with minimal validation"""
        try:
            question_id = question.get("question_id")
            if not question_id:
                return None

            answers = self._get_answers(question_id, site)

            # Extract owner/user data - only create User if we have meaningful data
            owner_data = question.get("owner", {})
            owner = None
            if owner_data and (
                owner_data.get("user_id") or owner_data.get("display_name")
            ):
                try:
                    owner = User(**owner_data)
                except Exception:
                    owner = None  # Skip invalid owner, continue with question

            # Fetch comments for the question
            question_comments = self._get_comments(question_id, site, "question")

            # Create Question - Pydantic handles validation/normalization
            return Question(
                question_id=question_id,
                title=question.get("title", ""),
                body=question.get("body", ""),
                score=question.get("score", 0),
                tags=question.get("tags", []),
                site=site,
                owner=owner,
                answers=answers,
                comments=question_comments,
                collected_at=time.time(),
            )

        except Exception as e:
            print(f"Error processing question {question_id}: {e}")
            return None

    def _get_answers(self, question_id: int, site: str) -> list[Answer]:
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
            for answer_data in data.get("items", []):
                try:
                    answer_id = answer_data.get("answer_id")
                    if not answer_id:
                        continue

                    # Extract owner data - only create User if we have meaningful data
                    owner_data = answer_data.get("owner", {})
                    owner = None
                    if owner_data and (
                        owner_data.get("user_id") or owner_data.get("display_name")
                    ):
                        try:
                            owner = User(**owner_data)
                        except Exception:
                            owner = None

                    # Fetch comments for this answer
                    answer_comments = self._get_comments(answer_id, site, "answer")

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

            time.sleep(1)
            return answers

        except Exception as e:
            print(f"Error fetching answers for question {question_id}: {e}")
            return []

    def _get_comments(self, post_id: int, site: str, post_type: str) -> list[Comment]:
        """
        Fetch comments for a question or answer

        Args:
            post_id: The question_id or answer_id
            site: StackExchange site (e.g., "ux")
            post_type: Either "question" or "answer"

        Returns:
            List of Comment objects
        """
        try:
            # StackExchange API: /questions/{ids}/comments or /answers/{ids}/comments
            url = f"{self.base_url}/{post_type}s/{post_id}/comments"
            params = {
                "site": site,
                "key": self.api_key,
                "filter": "withbody",
                "sort": "creation",
                "order": "asc",
            }

            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            comments = []
            for comment_data in data.get("items", []):
                try:
                    comment_id = comment_data.get("comment_id")
                    if not comment_id:
                        continue

                    # Extract owner data - owner is required for comments
                    owner_data = comment_data.get("owner", {})
                    if not owner_data:
                        continue

                    try:
                        owner = User(**owner_data)
                    except Exception:
                        # Create minimal user if validation fails
                        owner = User(user_id=None, display_name=None, reputation=None)

                    comments.append(
                        Comment(
                            comment_id=comment_id,
                            body=comment_data.get("body", ""),
                            score=comment_data.get("score", 0),
                            owner=owner,
                        )
                    )
                except Exception as e:
                    print(
                        f"Warning: Error processing comment {comment_data.get('comment_id')}: {e}"
                    )
                    continue

            time.sleep(0.5)  # Rate limiting - comments endpoint is lighter
            return comments

        except Exception as e:
            print(f"Error fetching comments for {post_type} {post_id}: {e}")
            return []

    def _store_in_mongodb(self, documents: list[Question]) -> int:
        if not documents:
            return 0

        try:
            self.collection.create_index("question_id", unique=True)

            stored_count = 0
            skipped_count = 0
            for question in documents:
                try:
                    # Convert Pydantic model to dict for MongoDB
                    doc = question.model_dump()
                    self.collection.insert_one(doc)
                    stored_count += 1
                except DuplicateKeyError:
                    # Document already exists - check if update is needed
                    existing = self.collection.find_one(
                        {"question_id": question.question_id},
                        {"score": 1, "collected_at": 1},
                    )

                    # Update only if score changed or it's been more than 24 hours
                    needs_update = False
                    if existing:
                        score_changed = existing.get("score") != question.score
                        time_passed = (
                            question.collected_at - existing.get("collected_at", 0)
                            > 86400
                        )  # 24h in seconds
                        needs_update = score_changed or time_passed

                    if needs_update:
                        self.collection.update_one(
                            {"question_id": question.question_id}, {"$set": doc}
                        )
                        stored_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    print(f"Error storing question {question.question_id}: {e}")
                    # Don't increment counters for real errors

            if skipped_count > 0:
                print(f"   (Skipped {skipped_count} unchanged duplicates)")
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
