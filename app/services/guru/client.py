import logging
from typing import Optional

import httpx

from app.core.config import settings
from app.services.guru.schemas import (
    GuruContact,
    GuruProduct,
    GuruTransaction,
)

logger = logging.getLogger(__name__)


class GuruClient:
    def __init__(self):
        self.base_url = settings.GURU_API_URL.rstrip("/")
        self.api_key = settings.GURU_API_KEY
        self.ingresso_group_id = settings.GURU_INGRESSO_GROUP_ID
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0,
        )

    def _paginate(self, endpoint: str, params: dict | None = None) -> list[dict]:
        all_items = []
        params = params or {}
        params.setdefault("limit", 50)

        while True:
            response = self._client.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()

            items = data if isinstance(data, list) else data.get("data", data)
            if isinstance(items, list):
                all_items.extend(items)
            else:
                all_items.append(items)
                break

            cursor = None
            if isinstance(data, dict):
                cursor = data.get("cursor_next") or data.get("next_cursor")

            if not cursor:
                break

            params["cursor"] = cursor

        return all_items

    def find_contact_by_cpf(self, cpf: str) -> Optional[GuruContact]:
        try:
            items = self._paginate("/contacts", params={"doc": cpf})
            if not items:
                return None
            return GuruContact.model_validate(items[0])
        except httpx.HTTPStatusError as e:
            logger.error(f"Guru API error finding contact: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error finding contact by CPF: {e}")
            raise

    def get_transactions_for_contact(self, contact_id: str) -> list[GuruTransaction]:
        try:
            items = self._paginate("/transactions", params={"contact_id": contact_id})
            return [GuruTransaction.model_validate(item) for item in items]
        except httpx.HTTPStatusError as e:
            logger.error(f"Guru API error getting transactions: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error getting transactions: {e}")
            raise

    def get_all_products(self) -> list[GuruProduct]:
        try:
            items = self._paginate("/products")
            return [GuruProduct.model_validate(item) for item in items]
        except httpx.HTTPStatusError as e:
            logger.error(f"Guru API error getting products: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error getting products: {e}")
            raise

    def get_ingresso_products(self) -> list[GuruProduct]:
        all_products = self.get_all_products()
        if not self.ingresso_group_id:
            logger.warning("GURU_INGRESSO_GROUP_ID not set, returning all products")
            return all_products
        return [
            p for p in all_products
            if p.group and p.group.id == self.ingresso_group_id
        ]
