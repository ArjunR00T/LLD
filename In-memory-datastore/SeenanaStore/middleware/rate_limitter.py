import math
import threading
import time
from collections import deque
from typing import Protocol

from fastapi import Request
from fastapi.responses import JSONResponse, Response


class RateLimitStrategy(Protocol):
    def consume(self, identity: str) -> int | None:
        """Return retry-after seconds when denied, otherwise None."""

    def get_policy(self) -> dict[str, int | float]:
        ...

    def update_policy(
        self, policy: dict[str, int | float]
    ) -> dict[str, int | float]:
        ...


class TokenBucketStrategy:
    def __init__(self, capacity: int = 5, refill_rate: float = 1):
        self._validate_policy(capacity, refill_rate)
        self._capacity = capacity
        self._refill_rate = refill_rate
        self._buckets: dict[str, dict[str, float]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _validate_policy(capacity: int, refill_rate: float):
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        if (
            isinstance(refill_rate, bool)
            or not isinstance(refill_rate, (int, float))
            or not math.isfinite(refill_rate)
            or refill_rate <= 0
        ):
            raise ValueError("refill_rate must be greater than zero")

    def get_policy(self) -> dict[str, int | float]:
        with self._lock:
            return {
                "capacity": self._capacity,
                "refill_rate": self._refill_rate,
            }

    def update_policy(
        self, policy: dict[str, int | float]
    ) -> dict[str, int | float]:
        if set(policy) != {"capacity", "refill_rate"}:
            raise ValueError("policy requires capacity and refill_rate")
        capacity = policy["capacity"]
        refill_rate = policy["refill_rate"]
        if (
            isinstance(capacity, bool)
            or not isinstance(capacity, int)
            or isinstance(refill_rate, bool)
            or not isinstance(refill_rate, (int, float))
        ):
            raise ValueError("invalid token bucket policy values")
        refill_rate = float(refill_rate)
        self._validate_policy(capacity, refill_rate)

        with self._lock:
            now = time.monotonic()
            # Refill under the old policy up to the update instant.
            for state in self._buckets.values():
                elapsed = max(0.0, now - state["updated_on"])
                state["tokens"] = min(
                    self._capacity,
                    state["tokens"] + self._refill_rate * elapsed,
                )
                state["tokens"] = min(capacity, state["tokens"])
                state["updated_on"] = now

            self._capacity = capacity
            self._refill_rate = refill_rate

            return {
                "capacity": self._capacity,
                "refill_rate": self._refill_rate,
            }

    def consume(self, identity: str) -> int | None:
        with self._lock:
            now = time.monotonic()
            state = self._buckets.get(identity)
            if state is None:
                self._buckets[identity] = {
                    "tokens": self._capacity - 1,
                    "updated_on": now,
                }
                return None

            elapsed = max(0.0, now - state["updated_on"])
            tokens = min(
                self._capacity,
                state["tokens"] + self._refill_rate * elapsed,
            )
            state["updated_on"] = now

            if tokens >= 1:
                state["tokens"] = tokens - 1
                return None

            state["tokens"] = tokens
            return math.ceil((1 - tokens) / self._refill_rate)


class SlidingWindowStrategy:
    def __init__(self, max_requests: int = 5, window_seconds: float = 60):
        self._validate_policy(max_requests, window_seconds)
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._windows: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _validate_policy(max_requests: int, window_seconds: float):
        if (
            isinstance(max_requests, bool)
            or not isinstance(max_requests, int)
            or max_requests < 1
        ):
            raise ValueError("max_requests must be a positive integer")
        if (
            isinstance(window_seconds, bool)
            or not isinstance(window_seconds, (int, float))
            or not math.isfinite(window_seconds)
            or window_seconds <= 0
        ):
            raise ValueError("window_seconds must be greater than zero")

    def get_policy(self) -> dict[str, int | float]:
        with self._lock:
            return {
                "max_requests": self._max_requests,
                "window_seconds": self._window_seconds,
            }

    def update_policy(
        self, policy: dict[str, int | float]
    ) -> dict[str, int | float]:
        if set(policy) != {"max_requests", "window_seconds"}:
            raise ValueError("policy requires max_requests and window_seconds")
        max_requests = policy["max_requests"]
        window_seconds = policy["window_seconds"]
        if (
            isinstance(max_requests, bool)
            or not isinstance(max_requests, int)
            or isinstance(window_seconds, bool)
            or not isinstance(window_seconds, (int, float))
        ):
            raise ValueError("invalid sliding window policy values")
        window_seconds = float(window_seconds)
        self._validate_policy(max_requests, window_seconds)

        with self._lock:
            self._max_requests = max_requests
            self._window_seconds = window_seconds
            self._windows.clear()
            return {
                "max_requests": self._max_requests,
                "window_seconds": self._window_seconds,
            }

    def consume(self, identity: str) -> int | None:
        with self._lock:
            now = time.monotonic()
            window = self._windows.setdefault(identity, deque())
            cutoff = now - self._window_seconds

            while window and window[0] <= cutoff:
                window.popleft()

            if len(window) >= self._max_requests:
                return max(
                    1,
                    math.ceil(window[0] + self._window_seconds - now),
                )

            window.append(now)
            return None


class RateLimiter:
    def __init__(
        self,
        strategy: RateLimitStrategy | None = None,
        capacity: int = 5,
        refill_rate: float = 1,
    ):
        self._strategy_lock = threading.Lock()
        self._strategy: RateLimitStrategy = (
            strategy
            if strategy is not None
            else TokenBucketStrategy(capacity=capacity, refill_rate=refill_rate)
        )

    def get_policy(self) -> dict[str, int | float]:
        with self._strategy_lock:
            strategy = self._strategy
        return strategy.get_policy()

    def update_policy(self, **policy: int | float) -> dict[str, int | float]:
        with self._strategy_lock:
            return self._strategy.update_policy(policy)

    def set_strategy(self, strategy: RateLimitStrategy):
        with self._strategy_lock:
            self._strategy = strategy

    async def __call__(self, request: Request, call_next) -> Response:
        user_id = getattr(request.state, "user_id", None)
        client_ip = request.client.host if request.client else "unknown"
        identity = (
            f"user:{user_id}" if user_id is not None else f"ip:{client_ip}"
        )

        with self._strategy_lock:
            strategy = self._strategy
        retry_after = strategy.consume(identity)

        if retry_after is not None:
            return JSONResponse(
                status_code=429,
                content="Maximum request limit reached, try again after sometime",
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)


async def rate_limitter(request: Request, call_next) -> Response:
    limiter: RateLimiter = request.app.state.rate_limiter
    return await limiter(request, call_next)
