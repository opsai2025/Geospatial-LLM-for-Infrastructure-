"""Shared HTTP handling: identifiable headers, bounded retries, clear errors."""

from __future__ import annotations

import time
from typing import Any

import requests

import config


class ServiceError(Exception):
    """Base class for errors that should be shown to the user."""

    def __init__(self, message: str, *, service: str = "", status_code: int | None = None):
        super().__init__(message)
        self.service = service
        self.status_code = status_code

    @property
    def user_message(self) -> str:
        prefix = f"{self.service}: " if self.service else ""
        return prefix + str(self)


class ServiceTimeoutError(ServiceError):
    """The service did not answer in time (client or server-side timeout)."""


class ServiceUnavailableError(ServiceError):
    """The service could not be reached or reported itself as unavailable."""


class RateLimitError(ServiceError):
    """The service rejected the request because of its rate limit."""


class UnexpectedResponseError(ServiceError):
    """The service answered with something the app cannot interpret."""


class QueryTooLargeError(ServiceError):
    """The request area or result is too large for the service."""


class AllEndpointsFailedError(ServiceUnavailableError):
    """Every configured endpoint of a service was down or did not answer in time."""

    def __init__(self, service: str, failures: list[tuple[str, ServiceError]]):
        self.failures = failures
        tried = "; ".join(f"{url} ({failure_reason(exc)})" for url, exc in failures)
        super().__init__(
            f"None of the {len(failures)} configured endpoints answered. Tried: {tried}. "
            "Please try again later.",
            service=service,
        )

    @property
    def endpoints(self) -> list[str]:
        return [url for url, _ in self.failures]


def failure_reason(exc: ServiceError) -> str:
    """Short English reason for one failed endpoint."""
    if exc.status_code:
        return f"HTTP {exc.status_code}"
    if isinstance(exc, ServiceTimeoutError):
        return "timed out"
    if isinstance(exc, ServiceUnavailableError):
        return "connection failed"
    return str(exc)


def is_endpoint_down(exc: ServiceError) -> bool:
    """True when ``request_json`` failed because the endpoint itself is unreachable.

    That covers connection errors, client timeouts and HTTP 502/503/504 (after
    the bounded retries). A bad query (HTTP 400), rate limiting (429) or a
    malformed answer would fail the same way elsewhere, so they return False.
    """
    return isinstance(exc, (ServiceTimeoutError, ServiceUnavailableError)) and exc.status_code in (
        None,
        502,
        503,
        504,
    )


RETRYABLE_STATUS = {429, 502, 503, 504}


def create_session(user_agent: str = config.USER_AGENT) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "application/json",
        }
    )
    return session


def _retry_delay(response: requests.Response | None, attempt: int) -> float:
    delay = 2.0 * (attempt + 1)
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                delay = float(retry_after)
            except ValueError:
                pass
    return max(0.0, min(delay, config.HTTP_MAX_BACKOFF_S))


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    service: str,
    timeout: float,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    max_retries: int = config.HTTP_MAX_RETRIES,
) -> Any:
    """Send a request and return the decoded JSON body.

    Retries at most ``max_retries`` times, and only for rate limiting or
    temporary unavailability. Every failure is raised as a ``ServiceError``
    subclass with a message suitable for display.
    """
    attempt = 0
    while True:
        response: requests.Response | None = None
        try:
            response = session.request(method, url, params=params, data=data, timeout=timeout)
        except requests.Timeout as exc:
            raise ServiceTimeoutError(
                f"No response within {timeout:.0f} s. The service may be busy, or the request may be "
                "too large. Try again later or choose a smaller region.",
                service=service,
            ) from exc
        except requests.ConnectionError as exc:
            raise ServiceUnavailableError(
                "Could not connect to the service. Check your internet connection or the configured endpoint "
                f"({url}).",
                service=service,
            ) from exc
        except requests.RequestException as exc:
            raise ServiceError(f"Request failed: {exc}", service=service) from exc

        status = response.status_code
        if status in RETRYABLE_STATUS and attempt < max_retries:
            time.sleep(_retry_delay(response, attempt))
            attempt += 1
            continue

        if status == 429:
            raise RateLimitError(
                "Rate limit reached (HTTP 429). Please wait a minute before trying again.",
                service=service,
                status_code=status,
            )
        if status == 504:
            raise ServiceTimeoutError(
                "The service timed out (HTTP 504). It may be overloaded, or the region may be too large. "
                "Try again later or choose a smaller region.",
                service=service,
                status_code=status,
            )
        if status in (502, 503):
            raise ServiceUnavailableError(
                f"The service is temporarily unavailable (HTTP {status}). Please try again later.",
                service=service,
                status_code=status,
            )
        if status >= 400:
            snippet = (response.text or "").strip().replace("\n", " ")[:300]
            raise ServiceError(
                f"Request rejected with HTTP {status}." + (f" Details: {snippet}" if snippet else ""),
                service=service,
                status_code=status,
            )

        try:
            return response.json()
        except ValueError as exc:
            content_type = response.headers.get("Content-Type", "unknown")
            raise UnexpectedResponseError(
                f"Expected JSON but received '{content_type}'. The service may be under maintenance.",
                service=service,
                status_code=status,
            ) from exc
