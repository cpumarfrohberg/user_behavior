"""StackExchange API client for HTTP requests"""

import os
import time
from typing import Any

import requests

from config import APIEndpoint


class StackExchangeAPIClient:
    """Handles HTTP requests to StackExchange API"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = APIEndpoint.BASE_URL
        self.questions_endpoint = APIEndpoint.QUESTIONS

    def get_questions(
        self, site: str, tag: str | None = None, page: int = 1, pagesize: int = 50
    ) -> dict[str, Any]:
        """
        Fetch questions from StackExchange API

        Args:
            site: StackExchange site (e.g., "ux")
            tag: Optional tag to filter by
            page: Page number
            pagesize: Number of items per page

        Returns:
            API response as dict
        """
        url = f"{self.base_url}/{self.questions_endpoint}"
        params = {
            "site": site,
            "sort": "votes",
            "order": "desc",
            "pagesize": pagesize,
            "page": page,
            "key": self.api_key,
            "filter": "withbody",
        }

        if tag:
            params["tagged"] = tag

        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_answers(self, question_id: int, site: str) -> dict[str, Any]:
        """
        Fetch answers for a question

        Args:
            question_id: Question ID
            site: StackExchange site

        Returns:
            API response as dict
        """
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
        time.sleep(1)  # Rate limiting
        return data

    def get_comments(self, post_id: int, site: str, post_type: str) -> dict[str, Any]:
        """
        Fetch comments for a question or answer

        Args:
            post_id: Question ID or Answer ID
            site: StackExchange site
            post_type: "question" or "answer"

        Returns:
            API response as dict
        """
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
        time.sleep(0.5)  # Rate limiting
        return data
