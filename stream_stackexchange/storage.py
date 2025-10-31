"""MongoDB storage operations"""

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from config import MONGODB_COLLECTION, MONGODB_DB, MONGODB_URI
from stream_stackexchange.models import Question


class MongoDBStorage:
    """Handles MongoDB storage operations"""

    def __init__(self):
        self.client = MongoClient(MONGODB_URI)
        self.db = self.client[MONGODB_DB]
        self.collection = self.db[MONGODB_COLLECTION]

    def store_questions(self, questions: list[Question]) -> int:
        """
        Store questions in MongoDB

        Args:
            questions: List of Question instances

        Returns:
            Number of documents stored/updated
        """
        if not questions:
            return 0

        try:
            self.collection.create_index("question_id", unique=True)

            stored_count = 0
            skipped_count = 0
            for question in questions:
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

    def close(self):
        """Close MongoDB connection"""
        self.client.close()
