"""SDK replay for Director mocks; narrow, unrecorded HTTP for live requests.

Replay fails closed. Live credentials/payloads bypass the SDK HTTP recorder.
"""
import asyncio
import json

import httpx
from cresta.agent.sdk.context.context import Context
from cresta.agent.sdk.api.auth import get_cresta_auth_provider
from cresta.agent.sdk.ext.auth.oauth2 import (
    OAuth2ClientCredentials, OAuth2Error, OAuth2TokenUnavailableError,
)
from cresta.agent.sdk.network.asyncclient import AsyncClient

from marina.flight_api import APIError, BASE_URL, HTTPTransport


class CrestaTransport(HTTPTransport):
    def __init__(self, api_key, timeout=12, *, replay_loop=None):
        super().__init__(api_key, timeout)
        self.replay_loop = replay_loop

    def __call__(self, path, payload):
        mock_config = Context.get_context("mock_config")
        if mock_config is None:
            return super().__call__(path, payload)
        # The SDK routes only string headers to replay. A dict or invalid header
        # must not silently select its normal HTTP path.
        try:
            parsed = json.loads(mock_config) if isinstance(mock_config, str) else None
        except (ValueError, TypeError):
            parsed = None
        if not isinstance(parsed, dict) or not parsed:
            raise APIError("mock_replay_unavailable")
        if self.replay_loop is not None:
            # The booking state machine runs in a worker. Keep the SDK's shared
            # OAuth client and background refresh on the serving event loop.
            return asyncio.run_coroutine_threadsafe(
                self.replay(path, payload), self.replay_loop).result()
        return asyncio.run(self.replay(path, payload))

    async def replay(self, path, payload):
        try:
            provider = get_cresta_auth_provider()
            if isinstance(provider, OAuth2ClientCredentials):
                try:
                    provider.access_token()
                except OAuth2TokenUnavailableError:
                    # apply_auth is synchronous and does not wait for the first
                    # background refresh. Explicitly await the documented warmup.
                    async with asyncio.timeout(self.timeout):
                        await provider.refresh()
            async with AsyncClient(timeout=self.timeout) as client:
                response = await client.post(BASE_URL + path, json=payload,
                                             headers={"Content-Type": "application/json"})
            # Never include the live credential in replay requests.
            if response.status_code >= 400:
                if response.status_code == 409 and path == "/api/save_passenger_information":
                    raise APIError("passenger_already_exists")
                if response.status_code in (401, 403):
                    raise APIError("authentication_error")
                if response.status_code == 429:
                    raise APIError("rate_limited")
                if response.status_code < 500:
                    raise APIError("request_rejected")
                raise APIError("service_unavailable", uncertain=path != "/api/search_flight")
            if len(response.content) > 1_000_000:
                raise ValueError("oversize")
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError("response")
            return result
        except APIError:
            raise
        except (httpx.HTTPError, RuntimeError, KeyError, OAuth2Error, TimeoutError):
            raise APIError("mock_replay_unavailable") from None
        except (ValueError, UnicodeError):
            raise APIError("invalid_response", uncertain=path != "/api/search_flight") from None
