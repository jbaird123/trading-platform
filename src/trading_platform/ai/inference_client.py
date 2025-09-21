import logging
import time
from typing import Any, Dict, List

import httpx
import pandas as pd

logger = logging.getLogger(__name__)


class AIInferenceClient:
    """Client for interacting with the AI model serving API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 5.0,
        retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.client = httpx.Client(timeout=self.timeout)

    def _send_request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Helper to send HTTP requests with retry logic."""
        for attempt in range(self.retries):
            try:
                response = self.client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.RequestError as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{self.retries}: "
                    f"Request to {url} failed: {e}"
                )
                if attempt < self.retries - 1:
                    time.sleep(self.backoff_factor * (2**attempt))
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error on {url}: {e.response.status_code} - {e.response.text}"
                )
                raise  # Re-raise HTTP status errors immediately
            except Exception as e:
                logger.error(f"An unexpected error occurred on {url}: {e}")
                raise  # Re-raise other unexpected errors immediately
        raise httpx.RequestError(f"Max retries exceeded for {url}", request=None)

    def predict(self, features: pd.DataFrame) -> List[Dict[str, Any]]:
        """Sends features to the AI model and returns predictions."""
        if features.empty:
            return []

        payload = features.to_dict(orient="records")
        try:
            response = self._send_request(
                "POST", f"{self.base_url}/predict", json=payload
            )
            return response.json()
        except httpx.RequestError:
            logger.error("AI inference request failed after retries.")
            return []
        except httpx.HTTPStatusError:
            logger.error("AI inference HTTP error.")
            return []
        except Exception:
            logger.error("An unexpected error occurred during AI inference.")
            return []

    def health_check(self) -> bool:
        """Checks the health of the AI model serving API."""
        try:
            response = self._send_request("GET", f"{self.base_url}/health")
            return response.status_code == 200
        except httpx.RequestError:
            logger.error("AI inference health check failed after retries.")
            return False
        except httpx.HTTPStatusError:
            logger.error("AI inference health check HTTP error.")
            return False
        except Exception:
            logger.error("An unexpected error occurred during AI health check.")
            return False
