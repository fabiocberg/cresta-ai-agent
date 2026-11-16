# Implementation decisions and API observations

Source: the two attachments to “Cresta AI Agent Developer Role - Next Steps,”
received November 4, 2026. Target names: **AI Agent 51**, **AI Agent 51 Testing**,
**AI Agent 51 Secret**. AI coding assistance is expressly permitted by the packet.

- Three distinct API operations follow search → passenger save → booking. The
  prompt guides dialogue; conversation variables enforce current-search IDs,
  passenger-save provenance, a consent flag and repeat/unknown-write guards.
  The API boundary validates payloads and outputs. Local tests do not prove
  model behavior; Director conversation
  tests must independently verify tool traces and spoken answers.
- The API returns operating airlines such as American Airlines and Delta. Preserve
  returned data rather than fabricating “Ocean Airlines” flight inventory.
- Live search on November 7 accepted `XXX → YYY` and generated 20 flights.
  The supplied contract has no route catalog; `/api/airports` and `/openapi.json`
  returned 404. There is no defensible airline route allowlist to invent. Empty
  successful searches trigger the mandated unsupported-route exit; controlled
  fixtures exercise it. Real route coverage remains an upstream API limitation.
- Search returned base fares without a currency. Booking returned pricing with
  currency `USD`, taxes and fees, and a higher final total. Read the API's final
  total; do not infer a universal tax percentage or promise a final total earlier.
- Passenger count exists in search, but booking takes just one passenger ID.
  Group completion is undefined. Search the requested count, explain the limit,
  and ask before changing to a single passenger. Do not fake a group booking.
- The hold is a 30-minute **simulation** expressly allowed by the packet. No hold
  endpoint or invented reservation ID. Phrase expiry relative to the current call
  to avoid inventing a clock or timezone. End the call after the offer.
- Human requests invoke Hangup, as the exercise explicitly requires. This unusual
  requirement takes priority over a conventional contact-center transfer.
- No automatic write retries. Timeouts, 5xx or invalid success responses after
  writes can leave an unknown outcome. Do not create a duplicate booking while
  trying to recover. There is no documented idempotency/status endpoint.
- A duplicate email returns HTTP 409 and an existing passenger ID. It does not
  verify or update the supplied passenger details. Treat it as a distinct conflict
  rather than silently booking with an unverified old record. No lookup/update
  endpoint is documented. Smoke runs use unique synthetic email addresses.
- Only synthetic passenger details are used in development and demo scripts.
  Credentials and original email PDFs remain in ignored `.private/` storage.
  The secret must be bound through the actual Cresta scaffold, never prompt text.

# Evidence so far

A direct sandbox API probe completed search → save → booking on November 7,
2026. The returned confirmation code was `A8254F`; total `211.35 USD`, compared
with the search base fare `183.78`. This verifies the API contract, **not** a
deployed Cresta agent. The original synthetic response is ignored under
`.private/booking-probe.json`.

The account and official CLI are authenticated. The agent and three SDK schemas
pass local CLI validation. All 27 native cases were installed and executed. Remote validation passes with
the deployed bundle. Actual run details are exported separately from local test
results. Native mock conversations fail with a remote-function stream error,
while live conversations and local SDK replay checks succeed. See `testing.md`.

The SDK HTTP client is used for strict Director replay without a live API key
or live fallback. Live API requests use bounded urllib requests to avoid the
SDK HTTP recorder capturing credentials or passenger payloads. Platform
conversation traces can still contain synthetic caller data and tool results.

Variables store IDs, search provenance, a passenger-field fingerprint and the
booking result rather than raw passenger fields. Parallel tool calls are
disabled. The guards cannot guarantee exactly-once execution across a crash
between API success and state persistence without upstream idempotency support.

The requested secret name is `AI Agent 51 Secret`. The CLI exposes a technical
ID, mapped to `ai-agent-51-secret` in `custom-code/secrets.yaml`. Verify the
platform's naming rules use that technical ID; the supplied UI accepted it.
No separate CLI display-name setting has been established.

The owner requested a review and an explicit confirmation before delivery.
Sandbox implementation, publication and testing were subsequently authorized.
Fabio subsequently gave final confirmation on November 8, 2026. The submission
was sent in the original email thread with both complete JSON test exports;
see `delivery/2026-11-08/email-receipt.json`.
