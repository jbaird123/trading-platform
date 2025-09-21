from typing import Any, Dict, List

import httpx
import pandas as pd


class AIInferenceClient:
    """
    Client for interacting with the AI model serving API.
    """

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.Client()

    def predict(self, features: List[float]) -> Dict[str, Any]:
        """
        Sends a prediction request to the AI model serving API.

        Args:
            features: A list of numerical features for prediction.

        Returns:
            A dictionary containing the prediction and confidence.
        """
        if not isinstance(features, list) or not all(isinstance(f, (int, float)) for f in features):
            raise ValueError("Features must be a list of numbers.")

        url = f"{self.base_url}/predict"
        payload = {"features": features}
        response = self.client.post(url, json=payload)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()

    def __del__(self):
        self.client.close()


if __name__ == "__main__":
    # Example usage (requires the FastAPI app to be running)
    client = AIInferenceClient()
    try:
        # Example features (replace with actual feature data)
        dummy_features = [0.1, 0.2, 0.3, 0.4, 0.5]
        prediction_result = client.predict(dummy_features)
        print(f"Prediction Result: {prediction_result}")

        # Test with invalid features
        try:
            client.predict([1, "a", 3])
        except ValueError as e:
            print(f"Caught expected error: {e}")

    except httpx.HTTPStatusError as e:
        print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
        print("Please ensure the FastAPI server is running (e.g., `uvicorn trading_platform.ai.serving.app:app --reload`).")
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        print("Could not connect to the FastAPI server. Is it running?")

