# AI Agent 51 — Marina design

Marina is the English-language AI reservations assistant for Ocean Airlines'
Sapphire line. The exercise supports new individual bookings. The generated
agent YAML is the upload source; `prompts/marina.md` is its readable prompt source.
When editing the prompt, synchronize its prompt section in `agent.yaml` before
validation/upload.

## Conversation flow

1. Identify as an AI assistant. Collect origin, destination, departure date and
   passenger count before search. Read a small shortlist but retain all results.
2. Select a returned flight. If a specifically requested flight is absent from
   the entire inventory, explain the limitation and invoke native Hangup.
   A successful empty search triggers the same required exit; an API error does
   not prove the route is unsupported.
3. Collect first name, last name, email, phone and date of birth; invoke the
   passenger-save tool and retain its returned ID.
4. Collect seat preference, read back the exact itinerary and obtain explicit
   booking consent. Invoke booking with the selected flight ID and saved
   passenger ID. Read the actual confirmation and final total with currency.
5. Offer further assistance, then end politely using native Hangup.

At any stage, a request for a human invokes Hangup as required by the packet.
At booking deferral, offer an explicitly simulated 30-minute hold, state its
relative expiry and invoke Hangup without booking. Never claim an actual hold
record. Identity questions receive a direct truthful answer. Existing-booking
changes, payments, cancellation/refund processing and policy advice are outside
scope.

## Tools and persisted state

- `search_flights(origin, destination, departure_date, passengers)` returns
  validated inventory. A new search invalidates prior flight selection even if
  it fails.
- `save_passenger_information(flight_id, first_name, last_name, email, phone,
  date_of_birth)` accepts only an ID from the current search. Group searches
  preserve the requested count but cannot create an unsupported group booking.
- `book_flight(passenger_id, flight_id, seat_preference, confirmed)` requires the
  current selected flight, this conversation's successfully saved passenger ID
  and a true consent flag. The model must base that flag on explicit caller words.

The state variable `marina_booking_state_v1` stores provenance, IDs, a passenger
fingerprint and booking outcome; raw passenger fields are not persisted there.
An unchanged successful passenger save is reused within the conversation.
A changed passenger clears the previous record before saving. Completed or
uncertain writes block further writes. Parallel tool calls are disabled.
There is no upstream idempotency/status API, so exactly-once execution after a
process crash between API success and variable persistence cannot be guaranteed.

## Runtime

Three strict async-generator functions use official `cresta-agent-sdk` 1.5 and
matching types 1.6 on Python 3.13+. Blocking live HTTP runs in a worker thread.
The API key is resolved through `get_secret('FLIGHT_API_KEY')`, mapped by
`custom-code/secrets.yaml`, and never included in model output. Requests target
only the supplied fixed API origin and sanitize errors without automatic retries.
Live requests bypass the SDK HTTP recorder. Director-controlled requests use the
SDK replay client without the live key, and fail closed without live fallback.
Replay stays on the serving event loop and awaits the initial OAuth token refresh
before the first request. OAuth failures return a sanitized tool error.

The official CLI scaffold configures native Hangup, en-US voice, welcome
identity disclosure and the supplied runtime guardrail structure. Deployed
search/save/book execution has succeeded. Fabio reports a successful voice booking.
The revision 12 native failure was traced to our replay OAuth cold-start and
event-loop integration. The corrected bundle passed the shared native suite;
consult the verification summary for the tested revision and exact run results.
See `docs/testing.md` and `results/verification-summary.json` for evidence and limits.

## Acceptance

Use `AI Agent 51 Testing`: 27 native cases, including two synthetic live-API
cases and 25 strict-mock cases. The manifest defines ten controlled responses.
Local tests and dry-run evidence do not replace actual platform transcripts.
Review prohibited writes, selected IDs, consent, totals and Hangup traces; export
real run details and rehearse the 2–4 minute Simulator demonstration. Sandbox
publication, testing and final delivery were authorized. The submission was sent
on November 8, 2026; see `delivery/2026-11-08/email-receipt.json`.
