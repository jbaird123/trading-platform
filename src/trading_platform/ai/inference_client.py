import logging
from typing import Any, Dict, List

import httpx
import pandas as pd

logger = logging.getLogger(__name__)


class AIInferenceClient:
    """Client for interacting with the AI model serving API."""

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url
        self.client = httpx.Client(timeout=5.0)  # 5-second timeout

    def predict(self, features: pd.DataFrame) -> List[Dict[str, Any]]:
        """Sends features to the AI model and returns predictions."""
        if features.empty:
            return []

        # Convert DataFrame to a list of dictionaries for JSON serialization
        payload = features.to_dict(orient="records")
        try:
            response = self.client.post(f"{self.base_url}/predict", json=payload)
            response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"AI inference request failed: {e}")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(
                f"AI inference HTTP error: {e.response.status_code} - {e.response.text}"
            )
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred during AI inference: {e}")
            return []

    def health_check(self) -> bool:
        """Checks the health of the AI model serving API."""
        try:
            response = self.client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.status_code == 200
        except httpx.RequestError as e:
            logger.error(f"AI inference health check failed: {e}")
            return False
        except httpx.HTTPStatusError as e:
            logger.error(
                f"AI inference health check HTTP error: {e.response.status_code} - {e.response.text}"
            )
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred during AI health check: {e}")
            return False
