"""Exercise the real SDK replay HTTP contract, mocking only the network boundary."""
import base64
import asyncio
import json
from unittest.mock import patch

import httpx
import pytest
from cresta.agent.sdk.api.mock import CrestaAPIMockClient
from cresta.agent.sdk.context.context import Context
from cresta.agent.sdk.network.asyncclient import AsyncClient

from marina.cresta_transport import CrestaTransport
from marina.flight_api import APIError, BASE_URL
from functions.booking import search_flights
from cresta.agent.sdk.types import FunctionInput
from cresta.agent.sdk.ext.auth.oauth2 import OAuth2ClientCredentials


class TestAuth:
    __test__ = False

    def apply_auth(self, *, ctx):
        ctx.headers['Authorization'] = 'Bearer local-test-only'

    def on_unauthorized(self, *, response):
        pass


@pytest.mark.parametrize('status', [200, 503])
def test_real_sdk_replay_serializes_request_and_decodes_http_response(status):
    captured = []
    result = {'success': True, 'flights': []} if status == 200 else {'success': False}

    def handle(request):
        assert str(request.url) == 'https://replay.invalid/v1/customers/test/profiles/test/externalApiRequests:execute'
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={'response': {
            'statusCode': status,
            'headers': [{'key': 'content-type', 'value': 'application/json'}],
            'body': base64.b64encode(json.dumps(result).encode()).decode(),
        }})

    client = CrestaAPIMockClient()
    client.base_url = 'https://replay.invalid'
    client._http_client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    mock_config = {'mock_scenario': 'controlled-test', 'strict_mode': True}
    with Context.with_context(mock_config=json.dumps(mock_config), customer_id='test', profile_id='test'), \
            patch.object(client, '_auth', return_value=TestAuth()), \
            patch.object(AsyncClient, '_build_default_api_client', return_value=client), \
            patch('marina.flight_api.request.urlopen') as live:
        transport = CrestaTransport('must-not-leak')
        payload = {'origin': 'JFK', 'destination': 'LAX'}
        if status == 200:
            assert transport('/api/search_flight', payload) == result
        else:
            with pytest.raises(APIError) as caught:
                transport('/api/search_flight', payload)
            assert caught.value.code == 'service_unavailable'
        live.assert_not_called()
    assert len(captured) == 1
    replay = captured[0]
    assert replay['mock_config'] == mock_config
    assert replay['request']['canonicalUri'] == BASE_URL + '/api/search_flight'
    assert json.loads(base64.b64decode(replay['request']['body'])) == payload
    assert 'must-not-leak' not in json.dumps(replay)


@pytest.mark.parametrize('invalid', [{'strict_mode': True}, '', 'broken-json', '[]', '{}'])
def test_invalid_mock_context_fails_before_any_http(invalid):
    with Context.with_context(mock_config=invalid), \
            patch('marina.cresta_transport.AsyncClient') as sdk, \
            patch('marina.flight_api.request.urlopen') as live:
        with pytest.raises(APIError) as caught:
            CrestaTransport('must-not-leak')('/api/book_flight', {})
        assert caught.value.code == 'mock_replay_unavailable'
        sdk.assert_not_called()
        live.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('auth_status', [200, 401])
async def test_cold_oauth_replay_uses_serving_loop_and_sanitizes_auth_failure(auth_status):
    loop = asyncio.get_running_loop()
    token_requests, replay_requests = [], []

    def token_response(request):
        assert asyncio.get_running_loop() is loop
        token_requests.append(request)
        return httpx.Response(auth_status, json={
            'access_token': 'local-test-only', 'token_type': 'Bearer', 'expires_in': 3600,
            'error_description': 'private auth details',
        })

    def replay_response(request):
        assert asyncio.get_running_loop() is loop
        assert request.headers['Authorization'] == 'Bearer local-test-only'
        replay_requests.append(request)
        body = base64.b64encode(b'{"success":true,"flights":[]}').decode()
        return httpx.Response(200, json={'response': {'statusCode': 200, 'body': body}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(token_response)) as token_http:
        provider = OAuth2ClientCredentials(token_url='https://auth.invalid/token',
            client_id='test', client_secret='test', http_client=token_http, _autostart_refresh=False)
        def build_client():
            client = CrestaAPIMockClient()
            client.base_url = 'https://replay.invalid'
            client._http_client = httpx.AsyncClient(transport=httpx.MockTransport(replay_response))
            client._auth = lambda: provider
            return client
        try:
            with Context.with_context(mock_config='{"mock_scenario":"controlled-test","strict_mode":true}',
                                      customer_id='test', profile_id='test'), \
                    patch('marina.cresta_transport.get_cresta_auth_provider', return_value=provider), \
                    patch.object(AsyncClient, '_build_default_api_client', side_effect=build_client), \
                    patch('marina.flight_api.request.urlopen') as live:
                # Two real tool invocations exercise worker-to-serving-loop reuse,
                # not just a patched async HTTP response.
                for _ in range(2):
                    outputs = [out async for out in search_flights(input=FunctionInput(), origin='JFK',
                        destination='LAX', departure_date='2099-01-01', passengers=1)]
                    result = json.loads(outputs[0].tool_msg)
                    assert result['success'] is (auth_status == 200)
                    assert result.get('status' if auth_status == 200 else 'error') == (
                        'no_flights' if auth_status == 200 else 'mock_replay_unavailable')
                    assert 'private auth details' not in outputs[0].tool_msg
                live.assert_not_called()
            assert token_requests
            assert len(replay_requests) == (2 if auth_status == 200 else 0)
        finally:
            await provider.aclose()
