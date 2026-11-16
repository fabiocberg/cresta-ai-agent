"""Run the actual Director response fixtures through SDK tools without live HTTP."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from cresta.agent.sdk.context.context import Context

from functions.booking import book_flight, save_passenger_information, search_flights
from tests.functions.test_booking import invoke

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = json.loads((ROOT / 'tests/native-manifest.json').read_text())
RULES = {rule['id']: rule for rule in MANIFEST['rules']}
PASSENGER = dict(first_name='Jane', last_name='Example', email='jane@example.com',
                 phone='+12025550123', date_of_birth='1990-05-15')


def response(rule_id):
    rule = RULES[rule_id]
    return httpx.Response(rule['status'], json=json.loads((ROOT / rule['body_file']).read_text()))


@pytest.mark.asyncio
async def test_fixture_booking_reaches_sdk_replay_and_keeps_real_returned_total():
    with Context.with_context(mock_config='{' + '"mock_scenario":"native-fixture-check"}'), patch('marina.cresta_transport.AsyncClient.post', new_callable=AsyncMock) as replay, patch('marina.flight_api.request.urlopen') as live:
        replay.return_value = response('search-ok')
        result, state = await invoke(search_flights, origin='JFK', destination='LAX',
                                      departure_date=MANIFEST['departure_date'], passengers=1)
        assert len(result['flights']) == 20
        flight_id = result['flights'][-1]['flight_id']  # Inventory beyond spoken shortlist.
        replay.return_value = response('save-ok')
        result, state = await invoke(save_passenger_information, state, flight_id=flight_id, **PASSENGER)
        passenger_id = result['passenger_id']
        replay.return_value = response('book-ok')
        result, state = await invoke(book_flight, state, passenger_id=passenger_id,
                                     flight_id=flight_id, seat_preference='window', confirmed=True)
        assert result['confirmation_code'] == 'MOCK51'
        assert result['total_price'] == 244.99
        assert replay.call_args.kwargs['json']['flight_id'] == flight_id
        assert replay.call_count == 3
        live.assert_not_called()


@pytest.mark.asyncio
async def test_changed_route_fixture_invalidates_old_flight_before_any_write():
    with Context.with_context(mock_config='{' + '"mock_scenario":"native-fixture-check"}'), patch('marina.cresta_transport.AsyncClient.post', new_callable=AsyncMock) as replay:
        replay.return_value = response('search-lax')
        result, state = await invoke(search_flights, origin='JFK', destination='LAX',
                                      departure_date=MANIFEST['departure_date'], passengers=1)
        old_id = result['flights'][0]['flight_id']
        replay.return_value = response('search-sfo')
        result, state = await invoke(search_flights, state, origin='JFK', destination='SFO',
                                      departure_date=MANIFEST['departure_date'], passengers=1)
        assert old_id not in {flight['flight_id'] for flight in result['flights']}
        result, _ = await invoke(save_passenger_information, state, flight_id=old_id, **PASSENGER)
        assert result['error'] == 'flight_not_in_current_search'
        assert replay.call_count == 2


@pytest.mark.asyncio
async def test_unconfirmed_booking_fixture_blocks_retry_across_tool_turns():
    with Context.with_context(mock_config='{' + '"mock_scenario":"native-fixture-check"}'), patch('marina.cresta_transport.AsyncClient.post', new_callable=AsyncMock) as replay:
        replay.return_value = response('search-ok')
        result, state = await invoke(search_flights, origin='JFK', destination='LAX',
                                      departure_date=MANIFEST['departure_date'], passengers=1)
        flight_id = result['flights'][0]['flight_id']
        replay.return_value = response('save-ok')
        result, state = await invoke(save_passenger_information, state, flight_id=flight_id, **PASSENGER)
        args = dict(passenger_id=result['passenger_id'], flight_id=flight_id,
                    seat_preference='window', confirmed=True)
        replay.return_value = response('book-503')
        result, state = await invoke(book_flight, state, **args)
        assert result['outcome_unknown'] is True
        assert 'confirmation_code' not in result
        result, _ = await invoke(book_flight, state, **args)
        assert result['error'] == 'previous_write_unconfirmed'
        assert replay.call_count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize('rule_id,expected', [
    ('search-empty', 'no_flights'), ('search-503', 'service_unavailable')])
async def test_search_failure_fixtures_never_expose_bookable_inventory(rule_id, expected):
    with Context.with_context(mock_config='{"mock_scenario":"native-fixture-check"}'), patch('marina.cresta_transport.AsyncClient.post', new_callable=AsyncMock, return_value=response(rule_id)) as replay, patch('marina.flight_api.request.urlopen') as live:
        result, state = await invoke(search_flights, origin='JFK', destination='LAX',
                                     departure_date=MANIFEST['departure_date'], passengers=1)
        assert result.get('status', result.get('error')) == expected
        result, _ = await invoke(save_passenger_information, state, flight_id='FLMADEUP', **PASSENGER)
        assert result['success'] is False
        assert replay.call_count == 1
        live.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('rule_id,expected', [
    ('save-409', 'passenger_already_exists'), ('save-503', 'service_unavailable')])
async def test_save_failure_fixtures_cannot_provide_a_booking_identity(rule_id, expected):
    with Context.with_context(mock_config='{"mock_scenario":"native-fixture-check"}'), patch('marina.cresta_transport.AsyncClient.post', new_callable=AsyncMock) as replay, patch('marina.flight_api.request.urlopen') as live:
        replay.return_value = response('search-ok')
        result, state = await invoke(search_flights, origin='JFK', destination='LAX',
                                     departure_date=MANIFEST['departure_date'], passengers=1)
        flight_id = result['flights'][0]['flight_id']
        replay.return_value = response(rule_id)
        result, state = await invoke(save_passenger_information, state, flight_id=flight_id, **PASSENGER)
        assert result['error'] == expected
        assert 'passenger_id' not in result
        result, _ = await invoke(book_flight, state, passenger_id='550e8400-e29b-41d4-a716-446655440000',
                                 flight_id=flight_id, seat_preference='window', confirmed=True)
        assert result['success'] is False
        assert replay.call_count == 2
        live.assert_not_called()
