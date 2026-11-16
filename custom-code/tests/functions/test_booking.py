import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from cresta.agent.sdk.context.context import Context
from cresta.agent.sdk.types import FunctionInput
from cresta.agent.types.types import GenerateAgain

from functions.booking import search_flights, save_passenger_information, book_flight
from marina.flight_api import APIError
from marina.cresta_transport import CrestaTransport


async def invoke(tool, variables=None, **args):
    outputs = [out async for out in tool(input=FunctionInput(variables=variables or {}), **args)]
    assert len(outputs) == 1
    assert not outputs[0].new_response  # JSON tool data must not be spoken directly.
    assert outputs[0].action.generate_again == GenerateAgain.YES
    return json.loads(outputs[0].tool_msg), outputs[0].variables


@pytest.mark.asyncio
async def test_sdk_round_trip_preserves_state_and_exact_booking_ids():
    flight = dict(flight_id='FLTEST1', flight_number='OA101', airline='Ocean Airlines',
                  departure_time='2099-01-01T08:00:00', arrival_time='2099-01-01T11:00:00',
                  price=100, available=True)
    pid = '550e8400-e29b-41d4-a716-446655440000'
    with patch('functions.booking.get_secret', return_value='local-test-only'), patch.object(CrestaTransport, '__call__') as post:
        post.return_value = dict(success=True, flights=[flight])
        result, state = await invoke(search_flights, origin='JFK', destination='LAX', departure_date='2099-01-01', passengers=1)
        assert result['flights'][0]['flight_id'] == 'FLTEST1'
        post.return_value = dict(success=True, passenger_id=pid)
        result, state = await invoke(save_passenger_information, state, flight_id='FLTEST1', first_name='Jane',
                                     last_name='Example', email='jane@example.com', phone='+12025550123', date_of_birth='1990-05-15')
        assert result['passenger_id'] == pid
        post.return_value = dict(success=True, booking_id='660e8400-e29b-41d4-a716-446655440000',
                                 confirmation_code='ABC123', booking_details={'pricing': {'total_price': 123.45, 'currency': 'USD'}})
        result, state = await invoke(book_flight, state, passenger_id=pid, flight_id='FLTEST1', seat_preference='window', confirmed=True)
        assert result['total_price'] == 123.45
        assert post.call_args.args == ('/api/book_flight', dict(passenger_id=pid, flight_id='FLTEST1', seat_preference='window'))
        result, _ = await invoke(book_flight, state, passenger_id=pid, flight_id='FLTEST1', seat_preference='window', confirmed=True)
        assert result['error'] == 'booking_already_completed'
        assert post.call_count == 3


@pytest.mark.asyncio
async def test_missing_secret_is_sanitized_without_network():
    with patch('functions.booking.get_secret', side_effect=RuntimeError('private secret detail')), patch.object(CrestaTransport, '__call__') as post:
        result, _ = await invoke(search_flights, origin='JFK', destination='LAX', departure_date='2099-01-01', passengers=1)
        assert result['error'] == 'configuration_error'
        assert 'private' not in json.dumps(result)
        post.assert_not_called()


def test_director_mock_uses_replay_without_api_key_or_live_fallback():
    response = httpx.Response(200, json={'success': True, 'flights': []})
    with Context.with_context(mock_config='{' + '"mock_scenario":"controlled-test"}'), patch('marina.cresta_transport.AsyncClient.post', new_callable=AsyncMock, return_value=response) as replay, patch('marina.flight_api.request.urlopen') as live:
        assert CrestaTransport('must-not-leak')('/api/search_flight', {})['success']
        assert 'X-API-Key' not in replay.call_args.kwargs['headers']
        live.assert_not_called()
        replay.side_effect = RuntimeError('replay not configured')
        with pytest.raises(APIError) as caught:
            CrestaTransport('must-not-leak')('/api/book_flight', {})
        assert caught.value.code == 'mock_replay_unavailable'
        live.assert_not_called()


@pytest.mark.asyncio
async def test_mock_context_survives_worker_thread_and_needs_no_live_secret():
    response = httpx.Response(200, json={'success': True, 'flights': []})
    with Context.with_context(mock_config='{' + '"mock_scenario":"controlled-test"}'), patch('functions.booking.get_secret') as secret, patch('marina.cresta_transport.AsyncClient.post', new_callable=AsyncMock, return_value=response) as replay:
        result, _ = await invoke(search_flights, origin='JFK', destination='LAX', departure_date='2099-01-01', passengers=1)
        assert result['status'] == 'no_flights'
        replay.assert_called_once()
        secret.assert_not_called()
