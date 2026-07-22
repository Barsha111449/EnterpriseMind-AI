import os
from typing import Any

import httpx


BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "http://127.0.0.1:8000",
)


class APIClientError(Exception):
    """Raised when the frontend cannot communicate with the backend."""


def get_health() -> dict[str, Any]:
    """Retrieve the FastAPI backend health status."""

    try:
        response = httpx.get(
            f"{BACKEND_URL}/health",
            timeout=10.0,
        )

        response.raise_for_status()

        return response.json()

    except httpx.HTTPError as exc:
        raise APIClientError(
            "The frontend could not connect to the backend."
        ) from exc