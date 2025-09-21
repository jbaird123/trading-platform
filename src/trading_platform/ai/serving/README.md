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

## Endpoints

*   **`/predict` (POST):** Accepts a JSON body with a `features` list and returns a prediction.
*   **`/health` (GET):** Returns the health status of the service.

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

## Example Usage (using `curl`)

**Health Check:**
```bash
curl http://localhost:8000/health
```

**Prediction:**
```bash
curl -X POST "http://localhost:8000/predict" -H "Content-Type: application/json" -d '{"features": [0.1, 0.2, 0.3, 0.4]}'
```
