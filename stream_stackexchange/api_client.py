import os
import time
from typing import Any

import requests

from config import DEFAULT_PAGE, DEFAULT_PAGESIZE, APIEndpoint, APIParameter


class StackExchangeAPIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = APIEndpoint.BASE_URL
        self.questions_endpoint = APIEndpoint.QUESTIONS

    def get_questions(
        self,
        site: str,
        tag: str | None = None,
        page: int = DEFAULT_PAGE,
        pagesize: int = DEFAULT_PAGESIZE,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{self.questions_endpoint}"
        params = {
            "site": site,
            "sort": APIParameter.SORT_VOTES,
            "order": APIParameter.ORDER_DESC,
            "pagesize": pagesize,
            "page": page,
            "key": self.api_key,
            "filter": APIParameter.FILTER_WITHBODY,
        }

        if tag:
            params["tagged"] = tag

        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_answers(self, question_id: int, site: str) -> dict[str, Any]:
        url = f"{self.base_url}/{self.questions_endpoint}/{question_id}/answers"
        params = {
            "site": site,
            "key": self.api_key,
            "filter": APIParameter.FILTER_WITHBODY,
            "sort": APIParameter.SORT_VOTES,
            "order": APIParameter.ORDER_DESC,
        }

        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        time.sleep(1)  # Rate limiting
        return data

    def get_comments(self, post_id: int, site: str, post_type: str) -> dict[str, Any]:
        url = f"{self.base_url}/{post_type}s/{post_id}/comments"
        params = {
            "site": site,
            "key": self.api_key,
            "filter": APIParameter.FILTER_WITHBODY,
            "sort": APIParameter.SORT_CREATION,
            "order": APIParameter.ORDER_ASC,
        }

        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        time.sleep(0.5)
        return data
