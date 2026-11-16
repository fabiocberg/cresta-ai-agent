"""Exercise the real sandbox. --book creates ONE synthetic passenger and booking."""
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom-code"))
from marina.flight_api import FlightAPI, HTTPTransport


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book", action="store_true")
    parser.add_argument("--date", default=(date.today() + timedelta(days=30)).isoformat())
    args = parser.parse_args()
    api = FlightAPI(HTTPTransport(os.environ.get("FLIGHT_API_KEY", "")))
    evidence = {"kind": "direct_sandbox_api_smoke", "is_cresta_conversation_export": False,
                "generated_at": datetime.now(timezone.utc).isoformat(), "steps": []}
    search = api.search_flights("JFK", "LAX", args.date, 1)
    evidence["steps"].append({"tool": "search_flights", "result": search})
    success = search.get("success") is True and bool(search.get("flights"))
    if success and args.book:
        # Reserved example domain and fictional NANP phone number; no user PII.
        # Unique per run: the service rejects an already registered email with 409.
        email = "marina.sandbox." + uuid4().hex[:12] + "@example.com"
        passenger = api.save_passenger("Marina", "SandboxTest", email,
                                       "12025550123", "1990-05-15")
        evidence["steps"].append({"tool": "save_passenger_information", "result": passenger})
        success = passenger.get("success") is True
        if success:
            booking = api.book_flight(passenger["passenger_id"], search["flights"][0]["flight_id"], "window")
            evidence["steps"].append({"tool": "book_flight", "result": booking})
            success = booking.get("success") is True
    evidence["successful"] = success
    path = ROOT / "results" / ("live-api-booking.json" if args.book else "live-api-search.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"successful": success, "steps": len(evidence["steps"]), "evidence": str(path)}))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(run())
