import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from SeenanaStore.middleware import rate_limitter as rate_limit_module
from SeenanaStore.routes.rate_limit_routes import router as rate_limit_router


class RateLimiterTest(unittest.TestCase):
    def setUp(self):
        self.limiter = rate_limit_module.RateLimiter()

    def make_request(self, client_ip="127.0.0.1", user_id=None):
        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [],
            "client": (client_ip, 12345),
            "server": ("testserver", 80),
        }
        request = Request(scope)
        if user_id is not None:
            request.state.user_id = user_id
        return request

    async def call_next(self, request):
        return Response("ok")

    def send_request(self, request):
        return asyncio.run(
            self.limiter(request, self.call_next)
        )

    def test_allows_initial_burst_then_returns_429(self):
        with patch.object(
            rate_limit_module, "time", SimpleNamespace(monotonic=lambda: 10)
        ):
            responses = [
                self.send_request(self.make_request())
                for _ in range(6)
            ]

        self.assertEqual(
            [response.status_code for response in responses],
            [200] * 5 + [429],
        )

    def test_refills_tokens_after_elapsed_time(self):
        times = [10] * 5 + [11]
        clock = iter(times)
        with patch.object(
            rate_limit_module,
            "time",
            SimpleNamespace(monotonic=lambda: next(clock)),
        ):
            for _ in range(5):
                self.assertEqual(self.send_request(self.make_request()).status_code, 200)

            response = self.send_request(self.make_request())

        self.assertEqual(response.status_code, 200)

    def test_denial_preserves_partial_refill_and_sets_retry_after(self):
        times = [10] * 5 + [10.5, 11]
        clock = iter(times)
        with patch.object(
            rate_limit_module,
            "time",
            SimpleNamespace(monotonic=lambda: next(clock)),
        ):
            for _ in range(5):
                self.send_request(self.make_request())

            denied_response = self.send_request(self.make_request())
            allowed_response = self.send_request(self.make_request())

        self.assertEqual(denied_response.status_code, 429)
        self.assertEqual(denied_response.headers.get("retry-after"), "1")
        self.assertEqual(allowed_response.status_code, 200)

    def test_authenticated_users_get_separate_buckets(self):
        with patch.object(
            rate_limit_module, "time", SimpleNamespace(monotonic=lambda: 10)
        ):
            for _ in range(5):
                self.send_request(self.make_request(user_id="alice"))

            denied_response = self.send_request(self.make_request(user_id="alice"))
            other_user_response = self.send_request(
                self.make_request(user_id="bob")
            )

        self.assertEqual(denied_response.status_code, 429)
        self.assertEqual(other_user_response.status_code, 200)

    def test_update_endpoint_changes_policy_without_recreating_limiter(self):
        app = FastAPI()
        app.state.rate_limiter = self.limiter
        app.include_router(rate_limit_router)

        with TestClient(app) as client:
            response = client.put(
                "/admin/rate-limit",
                json={"capacity": 2, "refill_rate": 3},
            )
            policy_response = client.get("/admin/rate-limit")

        with patch.object(
            rate_limit_module, "time", SimpleNamespace(monotonic=lambda: 10)
        ):
            request_responses = [
                self.send_request(self.make_request()) for _ in range(3)
            ]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"capacity": 2, "refill_rate": 3.0},
        )
        self.assertEqual(policy_response.status_code, 200)
        self.assertEqual(policy_response.json(), response.json())
        self.assertEqual(
            [result.status_code for result in request_responses],
            [200, 200, 429],
        )

    def test_update_endpoint_rejects_invalid_policy(self):
        app = FastAPI()
        app.state.rate_limiter = self.limiter
        app.include_router(rate_limit_router)

        with TestClient(app) as client:
            response = client.put(
                "/admin/rate-limit",
                json={"capacity": 0, "refill_rate": 1},
            )

        self.assertEqual(response.status_code, 422)

    def test_strategy_can_be_replaced(self):
        class AlwaysRejectStrategy:
            def consume(self, identity):
                return 7

            def get_policy(self):
                return {"capacity": 1, "refill_rate": 1}

            def update_policy(self, policy):
                return policy

        self.limiter.set_strategy(AlwaysRejectStrategy())

        response = self.send_request(self.make_request())

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers.get("retry-after"), "7")


if __name__ == "__main__":
    unittest.main()
