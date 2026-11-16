# Simulator demonstration rehearsal

Target duration: 2–4 minutes. Fabio reports a successful voice booking in the
Simulator. This script is for interview rehearsal, not an independent recording
of that call. The agent is deployed in the supplied sandbox.

## Before the call

- Select **AI Agent 51** in Simulator and confirm the required tool versions and
  secret binding. Use a future departure date, such as 30 days from the call.
- Prepare a unique synthetic email at `example.com` for this run. Reusing an
  address causes a passenger conflict. Use a fictional name, `+12025550123`, and
  date of birth `1990-05-15`. Never use the applicant's real personal details.
- Open Director results separately so the API smoke is not mistaken for a
  conversation test. Keep credentials and passenger records off the shared view.

## Main call: approximately two minutes

1. Let Marina identify herself as an AI assistant. Ask for one passenger from
   JFK to LAX on the chosen date.
2. Ask once, “Are you an AI?” Verify a direct truthful answer and return to the
   booking flow. Select one of the flights actually returned by search.
3. Provide the synthetic first name, last name, email, phone, and birth date.
   Show that the save tool runs and returns a passenger ID before booking.
4. Request a window seat. Confirm the specific itinerary after Marina's
   readback. Verify exactly one booking call with the selected flight and the
   saved passenger ID.
5. Listen for the actual confirmation code and final total with currency. Close
   the conversation when Marina offers further help.

## One short recovery demonstration: approximately 30 seconds

Start a separate call and ask to speak to a human. The exercise explicitly
requires Hangup. Show that Marina ends the call without claiming a transfer or
continuing to collect details.

The booking-timeout case passed in the final revision 19 shared suite; its
Director trace is available for the walkthrough. A lost booking response leaves
an unknown outcome; Marina must not retry or claim a confirmed reservation.
Do not deliberately break the live secret for the demo.
The controlled conversation case uses HTTP 503 rather than a socket timeout;
explain that distinction if showing its trace.

## Explain the tradeoffs: approximately 30 seconds

- The tools validate inputs, preserve returned prices, sanitize errors, and never
  automatically repeat a write whose outcome is unknown.
- Search does not provide final taxes or currency. Confirmation uses the booking
  response; earlier prices are described as base fares.
- The exercise's fare hold is a 30-minute simulation, not a backend hold. An
  unsupported route uses a controlled empty-search fixture because the supplied
  API generates flights even for arbitrary airport codes.
- Show the final results: 27/27 shared native cases and 22/22 supplemental live
  cases passed. Local tests cover a separate layer; earlier failed runs remain
  available as diagnostic history.
