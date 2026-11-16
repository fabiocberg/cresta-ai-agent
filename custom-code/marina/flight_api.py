"""Small, dependency-free boundary for the interview's sandbox API.

No retry on writes: a lost response may still mean a passenger/booking was created.
Never return server error text, request headers or passenger records to the model.
"""

import json
import math
import re
import socket
from datetime import date
from urllib import error, request
from uuid import UUID

BASE_URL = "https://fde-interview-flight-booking.voice-staging.cresta.ai"


class APIError(Exception):
    def __init__(self, code, *, uncertain=False):
        self.code = code
        self.uncertain = uncertain


def failure(code, *, uncertain=False):
    return {"success": False, "error": code, "outcome_unknown": uncertain}


def text(value, field, limit=120):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(field)
    if any(ord(c) < 32 for c in value):
        raise ValueError(field)
    return value.strip()


def iso_date(value, field, *, future, today):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(field)
    parsed = date.fromisoformat(value)
    if (future and parsed < today) or (not future and parsed >= today):
        raise ValueError(field)
    return value


def normalize_phone(value):
    value = text(value, "phone", 40)
    # Preserve the supplied country code; remove only common visual separators.
    # Do not guess a country, discard extensions, or accept alphabetic numbers.
    if not re.fullmatch(r"\+?[0-9 ().-]+", value):
        raise ValueError("phone")
    value = re.sub(r"[ ().-]", "", value)
    if not re.fullmatch(r"\+?[1-9][0-9]{6,14}", value):
        raise ValueError("phone")
    return value.removeprefix("+")


def money(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("price")
    if not math.isfinite(value) or value < 0:
        raise ValueError("price")
    return value


class HTTPTransport:
    def __init__(self, api_key, timeout=12):
        self.api_key = api_key
        self.timeout = timeout

    def __call__(self, path, payload):
        if not self.api_key:
            raise APIError("configuration_error")
        write = path != "/api/search_flight"
        req = request.Request(
            BASE_URL + path,
            data=json.dumps(payload, allow_nan=False).encode(),
            headers={"X-API-Key": self.api_key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                # A bounded read protects the tool from an unexpectedly large response.
                body = response.read(1_000_001)
        except error.HTTPError as exc:
            if exc.code in (401, 403):
                raise APIError("authentication_error") from None
            if exc.code == 429:
                raise APIError("rate_limited") from None
            if exc.code == 409 and path == "/api/save_passenger_information":
                # The API returns an existing ID but does not verify/update details.
                # Do not silently bind a new passenger's information to that record.
                raise APIError("passenger_already_exists") from None
            if 400 <= exc.code < 500:
                raise APIError("request_rejected") from None
            raise APIError("service_unavailable", uncertain=write) from None
        except (error.URLError, TimeoutError, socket.timeout, OSError):
            raise APIError("service_unavailable", uncertain=write) from None
        try:
            if len(body) > 1_000_000:
                raise ValueError("oversize")
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError("not an object")
            return data
        except (ValueError, UnicodeError):
            raise APIError("invalid_response", uncertain=write) from None


class FlightAPI:
    """Validated tools. Keep sequencing and caller consent in the conversation adapter."""

    def __init__(self, transport, today=date.today):
        self.transport = transport
        self.today = today

    def _post(self, path, payload):
        result = self.transport(path, payload)
        if not isinstance(result, dict) or not isinstance(result.get("success"), bool):
            raise APIError("invalid_response", uncertain=path != "/api/search_flight")
        if result["success"] is not True:
            raise APIError("request_rejected")
        return result

    def search_flights(self, origin, destination, departure_date, passengers):
        try:
            origin = text(origin, "origin", 3).upper()
            destination = text(destination, "destination", 3).upper()
            if not re.fullmatch(r"[A-Z]{3}", origin) or not re.fullmatch(r"[A-Z]{3}", destination):
                raise ValueError("airport")
            if origin == destination:
                raise ValueError("route")
            departure_date = iso_date(departure_date, "departure_date", future=True, today=self.today())
            if type(passengers) is not int or not 1 <= passengers <= 9:
                raise ValueError("passengers")
        except (ValueError, TypeError):
            return failure("invalid_search_input")
        try:
            result = self._post("/api/search_flight", dict(
                origin=origin, destination=destination, departure_date=departure_date, passengers=passengers,
            ))
            raw = result.get("flights")
            if not isinstance(raw, list):
                raise ValueError("flights")
            flights = []
            for flight in raw:
                if not isinstance(flight, dict) or type(flight.get("available")) is not bool:
                    raise ValueError("flight")
                if not flight["available"]:
                    continue
                # No invented airline, route, currency, fees or availability.
                item = {key: text(flight.get(key), key) for key in (
                    "flight_id", "flight_number", "airline", "departure_time", "arrival_time",
                )}
                if not re.fullmatch(r"FL[A-Za-z0-9]+", item["flight_id"]):
                    raise ValueError("flight_id")
                if not item["departure_time"].startswith(departure_date + "T"):
                    raise ValueError("departure_time")
                for field, expected in (("origin", origin), ("destination", destination)):
                    if field in flight and flight[field] != expected:
                        raise ValueError("route_mismatch")
                if "available_seats" in flight:
                    seats = flight["available_seats"]
                    if type(seats) is not int or seats < passengers:
                        continue
                item["base_fare_per_passenger"] = money(flight.get("price_per_passenger", flight.get("price")))
                item["listed_total"] = money(flight.get("total_price", item["base_fare_per_passenger"] * passengers))
                item["currency"] = flight.get("currency") if re.fullmatch(r"[A-Z]{3}", str(flight.get("currency"))) else None
                flights.append(item)
            return {"success": True, "status": "available" if flights else "no_flights", "flights": flights,
                    "search": dict(origin=origin, destination=destination, departure_date=departure_date, passengers=passengers)}
        except APIError as exc:
            return failure(exc.code, uncertain=exc.uncertain)
        except (ValueError, TypeError, KeyError):
            return failure("invalid_response")

    def save_passenger(self, first_name, last_name, email, phone, date_of_birth):
        try:
            payload = dict(first_name=text(first_name, "first_name"), last_name=text(last_name, "last_name"),
                           email=text(email, "email", 254), phone=normalize_phone(phone),
                           date_of_birth=iso_date(date_of_birth, "date_of_birth", future=False, today=self.today()))
            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", payload["email"]):
                raise ValueError("email")
        except (ValueError, TypeError):
            return failure("invalid_passenger_input")
        try:
            result = self._post("/api/save_passenger_information", payload)
            passenger_id = str(UUID(result.get("passenger_id")))
            return {"success": True, "passenger_id": passenger_id}
        except APIError as exc:
            return failure(exc.code, uncertain=exc.uncertain)
        except (ValueError, TypeError, AttributeError):
            return failure("invalid_response", uncertain=True)

    def book_flight(self, passenger_id, flight_id, seat_preference):
        try:
            passenger_id = str(UUID(passenger_id))
            if not isinstance(flight_id, str) or not re.fullmatch(r"FL[A-Za-z0-9]+", flight_id):
                raise ValueError("flight_id")
            if seat_preference not in ("window", "aisle", "middle"):
                raise ValueError("seat_preference")
        except (ValueError, TypeError, AttributeError):
            return failure("invalid_booking_input")
        try:
            result = self._post("/api/book_flight", dict(
                passenger_id=passenger_id, flight_id=flight_id, seat_preference=seat_preference,
            ))
            details = result.get("booking_details", {})
            price = money(details["pricing"]["total_price"])
            currency = details["pricing"].get("currency")
            if currency is not None and not re.fullmatch(r"[A-Z]{3}", str(currency)):
                raise ValueError("currency")
            return {"success": True, "booking_id": str(UUID(result.get("booking_id"))),
                    "confirmation_code": text(result.get("confirmation_code"), "confirmation_code", 32),
                    "total_price": price, "currency": currency}
        except APIError as exc:
            return failure(exc.code, uncertain=exc.uncertain)
        except (ValueError, TypeError, KeyError, AttributeError):
            return failure("invalid_response", uncertain=True)
