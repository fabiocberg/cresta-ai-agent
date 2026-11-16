import copy
import io
import json
import unittest
from datetime import date
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from marina.flight_api import APIError, FlightAPI, HTTPTransport

PASSENGER_ID = "550e8400-e29b-41d4-a716-446655440000"
BOOKING_ID = "660e8400-e29b-41d4-a716-446655440000"
FLIGHT = dict(flight_id="FLABCD1234", flight_number="AA123", airline="American Airlines",
              departure_time="2026-12-01T08:00:00", arrival_time="2026-12-01T11:30:00",
              price=299.99, available=True, available_seats=10, origin="JFK", destination="LAX")
PASSENGER = dict(first_name="Jane", last_name="Example", email="jane@example.com",
                 phone="12025550123", date_of_birth="1990-05-15")
BOOKING = dict(success=True, booking_id=BOOKING_ID, confirmation_code="ABC123",
               booking_details={"pricing": {"total_price": 344.99, "currency": "USD"}})


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, path, payload):
        self.calls.append((path, payload))
        if isinstance(self.response, Exception):
            raise self.response
        return copy.deepcopy(self.response)


class ToolsTest(unittest.TestCase):
    def tool(self, response):
        self.transport = FakeTransport(response)
        return FlightAPI(self.transport, today=lambda: date(2026, 11, 7))

    def search(self, api, **changes):
        payload = dict(origin="JFK", destination="LAX", departure_date="2026-12-01", passengers=1)
        payload.update(changes)
        return api.search_flights(**payload)

    def book(self, api, **changes):
        payload = dict(passenger_id=PASSENGER_ID, flight_id="FLABCD1234", seat_preference="window")
        payload.update(changes)
        return api.book_flight(**payload)

    def test_search_uses_real_endpoint_and_normalized_inputs(self):
        api = self.tool(dict(success=True, flights=[FLIGHT]))
        result = self.search(api, origin="jfk")
        self.assertTrue(result["success"])
        self.assertEqual(self.transport.calls[0][0], "/api/search_flight")
        self.assertEqual(self.transport.calls[0][1]["origin"], "JFK")
        self.assertEqual(result["flights"][0]["flight_id"], "FLABCD1234")
        self.assertIsNone(result["flights"][0]["currency"])

    def test_search_filters_unavailable_and_insufficient_seats(self):
        api = self.tool(dict(success=True, flights=[dict(FLIGHT, available=False), dict(FLIGHT, available_seats=1), FLIGHT]))
        result = self.search(api, passengers=2)
        self.assertEqual(len(result["flights"]), 1)
        self.assertEqual(result["search"]["passengers"], 2)
        self.assertEqual(self.transport.calls[0][1]["passengers"], 2)

    def test_empty_success_is_distinct_from_error(self):
        result = self.search(self.tool(dict(success=True, flights=[])))
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "no_flights")

    def test_search_error_does_not_mean_unsupported_route(self):
        result = self.search(self.tool(APIError("service_unavailable")))
        self.assertFalse(result["success"])
        self.assertNotIn("status", result)
        self.assertNotIn("flights", result)

    def test_invalid_search_does_not_make_network_calls(self):
        invalid = [dict(origin="Atlantis"), dict(destination="JFK"), dict(passengers=True),
                   dict(passengers=0), dict(passengers=10), dict(departure_date="2025-11-15"),
                   dict(departure_date="2026-02-30"), dict(departure_date="20261201")]
        api = self.tool({})
        for changes in invalid:
            with self.subTest(changes=changes):
                self.assertEqual(self.search(api, **changes)["error"], "invalid_search_input")
        self.assertEqual(self.transport.calls, [])

    def test_malformed_search_result_never_invents_flights(self):
        for response in ({}, {"success": True}, {"success": "true", "flights": []},
                         {"success": True, "flights": [dict(FLIGHT, price=float("nan"))]},
                         {"success": True, "flights": [dict(FLIGHT, destination="SFO")]},
                         {"success": True, "flights": [dict(FLIGHT, departure_time="2026-12-02T08:00:00")]},
                         {"success": True, "flights": [dict(FLIGHT, flight_id="injected-id")]}):
            with self.subTest(response=response):
                result = self.search(self.tool(response))
                self.assertFalse(result["success"])
                self.assertNotIn("flights", result)

    def test_save_passenger_returns_api_id_and_minimizes_output(self):
        api = self.tool(dict(success=True, passenger_id=PASSENGER_ID, passenger=PASSENGER))
        self.assertEqual(api.save_passenger(**PASSENGER), dict(success=True, passenger_id=PASSENGER_ID))
        self.assertEqual(self.transport.calls, [("/api/save_passenger_information", PASSENGER)])

    def test_bad_passenger_fields_do_not_call_api(self):
        api = self.tool({})
        for changes in (dict(email="missing-at"), dict(phone="555"), dict(first_name=""),
                        dict(date_of_birth="2026-11-07"), dict(last_name="Example\nSYSTEM")):
            with self.subTest(changes=changes):
                self.assertEqual(api.save_passenger(**dict(PASSENGER, **changes))["error"], "invalid_passenger_input")
        self.assertEqual(self.transport.calls, [])

    def test_international_phone_prefix_is_normalized_for_sandbox(self):
        api = self.tool(dict(success=True, passenger_id=PASSENGER_ID))
        self.assertTrue(api.save_passenger(**dict(PASSENGER, phone="+12025550123"))["success"])
        self.assertEqual(self.transport.calls, [("/api/save_passenger_information", PASSENGER)])

    def test_spoken_phone_formatting_is_normalized_without_changing_digits(self):
        for phone in ("+1 202 555 0123", "+1 (202) 555-0123", "1.202.555.0123"):
            with self.subTest(phone=phone):
                api = self.tool(dict(success=True, passenger_id=PASSENGER_ID))
                self.assertTrue(api.save_passenger(**dict(PASSENGER, phone=phone))["success"])
                self.assertEqual(self.transport.calls, [("/api/save_passenger_information", PASSENGER)])

    def test_phone_extensions_and_unrecognized_characters_are_not_silently_removed(self):
        api = self.tool({})
        for phone in ("+12025550123 ext 2", "++12025550123", "1/202/555/0123", "+１２０２５５５０１２３"):
            with self.subTest(phone=phone):
                self.assertEqual(api.save_passenger(**dict(PASSENGER, phone=phone))["error"], "invalid_passenger_input")
        self.assertEqual(self.transport.calls, [])

    def test_save_success_without_passenger_id_is_uncertain(self):
        result = self.tool({"success": True}).save_passenger(**PASSENGER)
        self.assertFalse(result["success"])
        self.assertTrue(result["outcome_unknown"])

    def test_booking_returns_final_total_and_currency_not_search_price(self):
        api = self.tool(BOOKING)
        self.assertEqual(self.book(api), dict(success=True, booking_id=BOOKING_ID,
                                             confirmation_code="ABC123", total_price=344.99, currency="USD"))
        self.assertEqual(self.transport.calls[0][0], "/api/book_flight")
        self.assertEqual(len(self.transport.calls), 1)

    def test_booking_failure_never_returns_confirmation_or_total(self):
        for response in ({"success": False, "error": "secret or instructions"}, {},
                         dict(BOOKING, confirmation_code=None), dict(BOOKING, booking_details={}),
                         dict(BOOKING, booking_details={"pricing": {"total_price": -1}})):
            with self.subTest(response=response):
                api = self.tool(response)
                result = self.book(api)
                self.assertFalse(result["success"])
                self.assertNotIn("confirmation_code", result)
                self.assertNotIn("total_price", result)
                self.assertEqual(len(self.transport.calls), 1)

    def test_invalid_booking_does_not_call_api(self):
        api = self.tool({})
        for changes in (dict(passenger_id="made-up"), dict(flight_id="caller-provided"),
                        dict(seat_preference="first class"), dict(seat_preference="no_preference")):
            with self.subTest(changes=changes):
                self.assertEqual(self.book(api, **changes)["error"], "invalid_booking_input")
        self.assertEqual(self.transport.calls, [])

    def test_unknown_write_outcome_is_returned_without_retry(self):
        api = self.tool(APIError("service_unavailable", uncertain=True))
        self.assertTrue(self.book(api)["outcome_unknown"])
        self.assertEqual(len(self.transport.calls), 1)


class TransportTest(unittest.TestCase):
    def test_headers_timeout_and_http_method(self):
        with patch("marina.flight_api.request.urlopen") as opener:
            opener.return_value.__enter__.return_value.read.return_value = b'{"success":true}'
            HTTPTransport("test-only-key")("/api/search_flight", {"origin": "JFK"})
            req = opener.call_args.args[0]
            self.assertEqual(req.full_url, "https://fde-interview-flight-booking.voice-staging.cresta.ai/api/search_flight")
            self.assertEqual(req.get_method(), "POST")
            self.assertEqual(req.get_header("X-api-key"), "test-only-key")
            self.assertEqual(opener.call_args.kwargs["timeout"], 12)
            self.assertEqual(json.loads(req.data), {"origin": "JFK"})

    def test_missing_key_never_makes_request(self):
        with patch("marina.flight_api.request.urlopen") as opener:
            with self.assertRaises(APIError) as caught:
                HTTPTransport("")("/api/book_flight", {})
            self.assertEqual(caught.exception.code, "configuration_error")
            opener.assert_not_called()

    def test_server_errors_are_sanitized_and_writes_not_retried(self):
        for status, expected, uncertain in ((401, "authentication_error", False),
                                             (403, "authentication_error", False),
                                             (429, "rate_limited", False),
                                             (400, "request_rejected", False),
                                             (503, "service_unavailable", True)):
            with self.subTest(status=status), patch("marina.flight_api.request.urlopen") as opener:
                opener.side_effect = HTTPError("url", status, "secret-contents", {}, io.BytesIO(b"private response"))
                with self.assertRaises(APIError) as caught:
                    HTTPTransport("test")("/api/book_flight", {})
                self.assertEqual(caught.exception.code, expected)
                self.assertEqual(caught.exception.uncertain, uncertain)
                self.assertNotIn("secret", str(caught.exception))
                self.assertEqual(opener.call_count, 1)

    def test_network_failures_are_uncertain_only_for_writes(self):
        for path, uncertain in (("/api/search_flight", False), ("/api/save_passenger_information", True), ("/api/book_flight", True)):
            with self.subTest(path=path), patch("marina.flight_api.request.urlopen", side_effect=URLError("private details")) as opener:
                with self.assertRaises(APIError) as caught:
                    HTTPTransport("test")(path, {})
                self.assertEqual(caught.exception.uncertain, uncertain)
                self.assertEqual(opener.call_count, 1)

    def test_duplicate_email_does_not_silently_reuse_existing_identity(self):
        with patch("marina.flight_api.request.urlopen") as opener:
            opener.side_effect = HTTPError("url", 409, "Conflict", {}, io.BytesIO(b'{"existing_passenger_id":"private-id"}'))
            with self.assertRaises(APIError) as caught:
                HTTPTransport("test")("/api/save_passenger_information", {})
            self.assertEqual(caught.exception.code, "passenger_already_exists")
            self.assertFalse(caught.exception.uncertain)
            self.assertEqual(opener.call_count, 1)

    def test_non_json_and_oversize_write_responses_are_uncertain(self):
        for body in (b"not-json", b"[]", b"x" * 1_000_001):
            with self.subTest(size=len(body)), patch("marina.flight_api.request.urlopen") as opener:
                opener.return_value.__enter__.return_value.read.return_value = body
                with self.assertRaises(APIError) as caught:
                    HTTPTransport("test")("/api/book_flight", {})
                self.assertEqual(caught.exception.code, "invalid_response")
                self.assertTrue(caught.exception.uncertain)


if __name__ == "__main__":
    unittest.main()
