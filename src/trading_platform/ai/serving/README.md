# AI Model Serving

This directory contains the FastAPI application for serving AI model predictions.

## How to Run

1.  **Install Dependencies:**
    Ensure you have `fastapi` and `uvicorn` installed. If using Poetry, run:
    ```bash
    poetry install
    ```

2.  **Start the Server:**
    Navigate to the project root directory and run the following command:
    ```bash
    uvicorn src.trading_platform.ai.serving.app:app --host 0.0.0.0 --port 8000 --reload
    ```
    This will start the FastAPI server, typically accessible at `http://localhost:8000`. The `--reload` flag is useful for development as it automatically reloads the server on code changes.

## API Endpoints Documentation

This API follows a RESTful design with versioning and provides endpoints for model inference, health checks, and metrics.

### API Versioning Strategy

API endpoints are prefixed with `/v1/` (e.g., `/v1/predict`) to indicate the API version. This strategy allows for backward-compatible evolution of the API. Future major changes will introduce new version prefixes (e.g., `/v2/`).

### Authentication

All endpoints require API key authentication. Provide your API key in the `X-API-Key` HTTP header.

**Error Codes:**
*   `401 Unauthorized`: Returned if the `X-API-Key` header is missing or the provided API key is invalid.

### Endpoints

#### 1. `POST /v1/predict`

Receives a list of features and returns a trading signal prediction.

*   **Description:** This endpoint is used to obtain a trading signal (long, short, or flat) and its associated probability from the AI model based on provided features.
*   **Request Payload (`PredictionRequest`):
    ```json
    {
      "features": [
        {"name": "feature_1", "value": 0.1},
        {"name": "feature_2", "value": 0.2},
        {"name": "feature_3", "value": 0.3}
      ]
    }
    ```
    - `features`: A list of objects, where each object has:
        - `name` (string): The name of the feature.
        - `value` (float): The numerical value of the feature.

*   **Response Payload (`PredictionResponse`):
    ```json
    {
      "signal": "long",
      "probability": 0.85,
      "model_version": "v1.0"
    }
    ```
    - `signal` (string): The predicted trading signal (`long`, `short`, or `flat`).
    - `probability` (float): The confidence score or probability of the predicted signal.
    - `model_version` (string): The version of the model that generated the prediction.

*   **Usage Example (using `curl`):
    ```bash
    curl -X POST "http://localhost:8000/v1/predict" \
         -H "Content-Type: application/json" \
         -H "X-API-Key: your-super-secret-api-key" \
         -d '{
               "features": [
                 {"name": "RSI", "value": 65.5},
                 {"name": "MACD_Hist", "value": 0.012},
                 {"name": "ATR", "value": 0.0005}
               ]
             }'
    ```

#### 2. `GET /v1/health`

Health check endpoint.

*   **Description:** Verifies the operational status of the AI model serving application.
*   **Response Payload:
    ```json
    {
      "status": "ok",
      "version": "1.0.0"
    }
    ```
*   **Usage Example (using `curl`):
    ```bash
    curl -X GET "http://localhost:8000/v1/health" \
         -H "X-API-Key: your-super-secret-api-key"
    ```

#### 3. `GET /v1/metrics`

Monitoring endpoint to expose metrics.

*   **Description:** Provides a placeholder for exposing operational metrics of the AI model serving application. Actual metrics collection would be implemented here.
*   **Response Payload:
    ```json
    {
      "status": "metrics_endpoint_placeholder",
      "message": "Metrics collection not yet implemented.",
      "available_metrics": ["request_count", "error_rate", "prediction_distribution"],
      "version": "1.0.0"
    }
    ```
*   **Usage Example (using `curl`):
    ```bash
    curl -X GET "http://localhost:8000/v1/metrics" \
         -H "X-API-Key: your-super-secret-api-key"
    ```

## Scalability, High Availability, and Low Latency Considerations

For production deployment, the following aspects should be addressed to ensure the serving infrastructure meets performance and reliability requirements:

*   **Scalability:**
    *   **Horizontal Scaling:** Deploy multiple instances of the FastAPI application behind a load balancer.
    *   **Asynchronous Processing:** Utilize FastAPI's asynchronous capabilities and potentially integrate with message queues (e.g., RabbitMQ, Kafka) for handling prediction requests.
    *   **Efficient Model Loading:** Optimize model loading to minimize startup time for new instances.

*   **High Availability:**
    *   **Redundancy:** Deploy across multiple availability zones/regions.
    *   **Health Checks:** Implement robust health checks (as already provided by `/health` endpoint) for load balancers and orchestration systems (e.g., Kubernetes).
    *   **Graceful Degradation:** Design the system to handle failures of individual components without complete service interruption.

*   **Low Latency:**
    *   **ONNX Runtime:** Leverage ONNX Runtime for highly optimized model inference.
    *   **Hardware Acceleration:** Utilize GPUs or specialized AI accelerators if available and beneficial for model type.
    *   **Caching:** Implement caching mechanisms for frequently requested predictions or pre-computed features.
    *   **Efficient Data Transfer:** Minimize data serialization/deserialization overhead.

## A/B Testing Capabilities

To implement A/B testing, the serving infrastructure would need to:
*   Route a percentage of incoming requests to different model versions (e.g., a champion model vs. a challenger model).
*   Collect metrics for each model version to compare their performance in production.
*   Provide mechanisms to dynamically adjust traffic allocation based on observed performance.

## Auto-Scaling Policies

For dynamic scaling of the model serving infrastructure, consider implementing policies based on:
*   **CPU Utilization:** Scale out when CPU usage exceeds a threshold, scale in when it drops.
*   **Request Latency:** Scale out if average prediction latency increases beyond acceptable limits.
*   **Request Queue Depth:** Scale out if the number of pending requests grows.
*   **Custom Metrics:** Integrate with monitoring systems to use custom metrics (e.g., number of active users, specific business metrics) for scaling decisions.
*   **Scheduled Scaling:** Implement time-based scaling for predictable traffic patterns.
*   **Container Orchestration:** Leverage features of container orchestration platforms (e.g., Kubernetes Horizontal Pod Autoscaler) to automate scaling.

