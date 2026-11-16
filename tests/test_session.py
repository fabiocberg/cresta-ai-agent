import json
import unittest
from datetime import date

from marina.flight_api import APIError, FlightAPI
from marina.session import BookingSession, STATE_KEY
from tests.test_flight_api import FakeTransport, FLIGHT, PASSENGER, PASSENGER_ID, BOOKING


class SessionTest(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport(dict(success=True, flights=[FLIGHT]))
        self.api = FlightAPI(self.transport, today=lambda: date(2026, 11, 7))
        self.session = BookingSession(self.api, {})

    def search(self, passengers=1):
        return self.session.search('JFK', 'LAX', '2026-12-01', passengers)

    def save(self, **changes):
        fields = dict(PASSENGER, **changes)
        return self.session.save(FLIGHT['flight_id'], **fields)

    def ready(self):
        self.search()
        self.transport.response = dict(success=True, passenger_id=PASSENGER_ID)
        self.assertTrue(self.save()['success'])

    def book(self, **changes):
        args = dict(passenger_id=PASSENGER_ID, flight_id=FLIGHT['flight_id'],
                    seat_preference='window', confirmed=True)
        args.update(changes)
        return self.session.book(**args)

    def test_cannot_save_or_book_before_search(self):
        self.assertFalse(self.save()['success'])
        self.assertFalse(self.book()['success'])
        self.assertEqual(self.transport.calls, [])

    def test_invented_flight_and_passenger_never_reach_api(self):
        self.ready()
        before = len(self.transport.calls)
        self.assertFalse(self.book(flight_id='FLFAKE')['success'])
        self.assertFalse(self.book(passenger_id='660e8400-e29b-41d4-a716-446655440000')['success'])
        self.assertEqual(len(self.transport.calls), before)

    def test_consent_required_and_success_cannot_be_repeated(self):
        self.ready()
        self.transport.response = BOOKING
        self.assertEqual(self.book(confirmed=False)['error'], 'explicit_consent_required')
        self.assertEqual(len(self.transport.calls), 2)
        self.assertTrue(self.book()['success'])
        self.assertEqual(self.book()['error'], 'booking_already_completed')
        self.assertFalse(self.search()['success'])
        self.assertEqual(len(self.transport.calls), 3)

    def test_uncertain_write_blocks_all_further_operations_across_turns(self):
        self.ready()
        self.transport.response = APIError('service_unavailable', uncertain=True)
        self.assertTrue(self.book()['outcome_unknown'])
        self.session = BookingSession(self.api, self.session.variables())
        before = len(self.transport.calls)
        for result in (self.book(), self.save(), self.search()):
            self.assertTrue(result['outcome_unknown'])
        self.assertEqual(len(self.transport.calls), before)

    def test_failed_search_invalidates_previous_selection(self):
        self.ready()
        self.transport.response = APIError('service_unavailable')
        self.assertFalse(self.search()['success'])
        before = len(self.transport.calls)
        self.assertEqual(self.book()['error'], 'flight_not_in_current_search')
        self.assertEqual(len(self.transport.calls), before)

    def test_correction_failure_invalidates_old_passenger(self):
        self.ready()
        self.transport.response = APIError('passenger_already_exists')
        self.assertFalse(self.save(first_name='Janet')['success'])
        self.assertNotIn('passenger_id', self.session.state)
        before = len(self.transport.calls)
        self.assertFalse(self.book()['success'])
        self.assertEqual(len(self.transport.calls), before)

    def test_group_search_preserved_but_group_write_blocked(self):
        self.assertEqual(self.search(3)['search']['passengers'], 3)
        self.assertEqual(self.save()['error'], 'individual_booking_only')
        self.assertEqual(self.transport.calls[0][1]['passengers'], 3)
        self.assertEqual(len(self.transport.calls), 1)

    def test_reuse_unchanged_successful_save_without_duplicate_email_write(self):
        self.ready()
        self.session = BookingSession(self.api, self.session.variables())
        self.assertTrue(self.save()['already_saved'])
        self.assertEqual(len(self.transport.calls), 2)
        state = json.dumps(self.session.variables())
        for value in PASSENGER.values():
            self.assertNotIn(value, state)

    def test_phone_format_change_reuses_verified_passenger_across_turns(self):
        self.ready()
        self.session = BookingSession(self.api, self.session.variables())
        self.assertTrue(self.save(phone='+1 (202) 555-0123')['already_saved'])
        self.assertEqual(len(self.transport.calls), 2)

    def test_invalid_phone_correction_invalidates_old_passenger(self):
        self.ready()
        self.assertEqual(self.save(phone='555')['error'], 'invalid_passenger_input')
        self.assertNotIn('passenger_id', self.session.state)
        self.assertFalse(self.book()['success'])
        self.assertEqual(len(self.transport.calls), 2)

    def test_malformed_state_fails_closed(self):
        self.session = BookingSession(self.api, {STATE_KEY: '[]'})
        self.assertEqual(self.search()['error'], 'invalid_session_state')
        self.assertEqual(self.transport.calls, [])
