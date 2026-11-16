"""Conversation-scoped write guards; no raw passenger details in variables."""
import hashlib
import json

from marina.flight_api import failure, normalize_phone

STATE_KEY = "marina_booking_state_v1"


class BookingSession:
    def __init__(self, api, variables):
        self.api = api
        try:
            self.state = json.loads(variables.get(STATE_KEY, "{}"))
            if not isinstance(self.state, dict):
                raise ValueError("state")
            self.valid = True
        except (ValueError, TypeError):
            self.state, self.valid = {}, False

    def variables(self):
        return {STATE_KEY: json.dumps(self.state, separators=(",", ":"), allow_nan=False)}

    def guard(self):
        if not self.valid:
            return failure("invalid_session_state")
        if self.state.get("uncertain"):
            return failure("previous_write_unconfirmed", uncertain=True)
        if self.state.get("booking"):
            return failure("booking_already_completed")
        return None

    def track(self, result):
        if result.get("outcome_unknown"):
            self.state["uncertain"] = True
        return result

    def search(self, origin, destination, departure_date, passengers):
        blocked = self.guard()
        if blocked:
            return blocked
        # A failed new search also invalidates the old flight selection.
        self.state.pop("search", None)
        self.state.pop("selected_flight", None)
        result = self.api.search_flights(origin, destination, departure_date, passengers)
        if result["success"]:
            self.state["search"] = {"passengers": result["search"]["passengers"],
                                    "flights": [f["flight_id"] for f in result["flights"]]}
        return result

    def select(self, flight_id):
        blocked = self.guard()
        if blocked:
            return blocked
        search = self.state.get("search", {})
        if flight_id not in search.get("flights", []):
            return failure("flight_not_in_current_search")
        if search.get("passengers") != 1:
            return failure("individual_booking_only")
        return None

    def save(self, flight_id, first_name, last_name, email, phone, date_of_birth):
        blocked = self.select(flight_id)
        if blocked:
            return blocked
        try:
            phone = normalize_phone(phone)
        except (ValueError, TypeError):
            self.state.pop("passenger_id", None)
            self.state.pop("passenger_fingerprint", None)
            self.state.pop("selected_flight", None)
            return failure("invalid_passenger_input")
        fields = (first_name, last_name, email, phone, date_of_birth)
        fingerprint = hashlib.sha256(json.dumps(fields).encode()).hexdigest()
        # Reuse only this conversation's successfully saved, unchanged record.
        if fingerprint == self.state.get("passenger_fingerprint") and self.state.get("passenger_id"):
            self.state["selected_flight"] = flight_id
            return {"success": True, "passenger_id": self.state["passenger_id"], "already_saved": True}
        self.state.pop("passenger_id", None)
        self.state.pop("passenger_fingerprint", None)
        self.state.pop("selected_flight", None)
        result = self.track(self.api.save_passenger(*fields))
        if result["success"]:
            self.state.update(passenger_id=result["passenger_id"],
                              passenger_fingerprint=fingerprint, selected_flight=flight_id)
        return result

    def book(self, passenger_id, flight_id, seat_preference, confirmed):
        blocked = self.select(flight_id)
        if blocked:
            return blocked
        if flight_id != self.state.get("selected_flight"):
            return failure("flight_selection_not_saved")
        if not passenger_id or passenger_id != self.state.get("passenger_id"):
            return failure("passenger_not_saved")
        if confirmed is not True:
            return failure("explicit_consent_required")
        result = self.track(self.api.book_flight(passenger_id, flight_id, seat_preference))
        if result["success"]:
            self.state["booking"] = result
        return result
