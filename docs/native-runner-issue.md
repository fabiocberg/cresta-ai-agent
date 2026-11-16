# Controlled replay: OAuth initialization diagnosis

The revision 12 shared run had 19 failed conversations, all with
`ERROR GENERATING RESPONSE`. These were execution failures, not 19 independently
established prompt defects. The failure was isolated to the authenticated HTTP
replay path used by native controlled tests.

## Evidence and root cause

A separate private diagnostic agent left the original candidate unchanged while
comparing the same search request with and without strict mocking:

- A constant custom tool executed successfully in both modes. This rules out a
  general inability of Cresta's runner to invoke custom code with mocks.
- The original deployed bundle executed live search, but failed with a mock.
  Downloaded bundle source matched the local booking and transport modules.
- An instrumented search caught `OAuth2TokenUnavailableError` in the official
  SDK's `OAuth2ClientCredentials.access_token`, reached from replay HTTP auth.
  The mock header was a string, variables were a dictionary, and the replay base
  URL was configured. This was not the previously suspected null-input adapter.

The SDK's synchronous `apply_auth` reads a cached token and raises if the first
background refresh has not completed. Its documented async initialization path
is to await `refresh()`. Our transport did not await this warmup and did not
catch `OAuth2Error`. It also started a temporary event loop inside a worker for
each replay, although the shared OAuth provider owns loop-bound background work
and an HTTP client. These are integration defects in our code; the evidence does
not justify labeling all 19 failures a Cresta outage or defect.

Diagnostic run: `01a1bb75-0e37-739f-9675-669385c6cacc`, private agent revision 3.
`results/native-replay-diagnostic.json` preserves the actual exception type,
phase and stack frames without tokens or exception messages. The CLI's two
"passed" values on that diagnostic are not acceptance results: those probe cases
intentionally had no evaluators.

## Correction

- Dispatch replay from the booking worker onto the serving event loop.
- Await initial/stale OAuth token refresh before sending replay requests, with a
  bounded timeout. Use the platform-provisioned provider; no personal token or
  live airline API key is copied into replay requests.
- Convert OAuth errors into sanitized `mock_replay_unavailable` tool results,
  without falling back to live HTTP or retrying booking/passenger writes.
- Regression tests exercise real SDK OAuth and replay clients at the mocked
  network boundary, across two actual tool invocations. They cover successful
  startup and rejected authentication. Twenty SDK tests pass locally.

The corrected bundle first passed 24/27 shared native cases on revision 16 with
zero generation errors; the other three failures were reused live emails and a
premature closing after an uncertain booking. After fixture/prompt corrections,
revision 19 passed **27/27 shared cases** and **22/22 supplemental live cases**,
with zero generation errors. `results/verification-summary.json` contains exact
run IDs. Revision 18/19 caller-simulator errors and seat-evaluator false negatives
remain in historical exports. The final injection case supplies fixed attacker
turns while executing real agent responses. The seat judge now distinguishes the
documented API enum constraint from forbidden seating-policy claims.

## Evaluator false positive fixed

A constant tool returning only a diagnostic marker incorrectly passed the old
search-outage evaluator: its negative criteria plus graceful closure did not
require evidence of the controlled error itself. The generator now embeds each
controlled-response case's required setup in its judge prompt. Missing, different
or fabricated output must fail. Seven existing cases were updated while retaining
their dates and platform identity.

The same constant tool correctly fails the strengthened native evaluator, with
an explanation that `success=false`, `error=service_unavailable`, and
`outcome_unknown=false` are absent. Negative-control run:
`01a1bb77-5f16-7d13-aad7-cc13e321d1ec`, preserved in
`results/native-negative-control-detail.json`. This intentional failure is not
included in acceptance totals.

## Earlier diagnostic limitations

The earlier trace reported a remote function stream error without an exception
body. Invocation inspection returned PermissionDenied, and newer trace lookups
returned an inconsistent conversation/trace association. These limits remain
recorded, but the instrumented tool supplied direct evidence without requiring
server logs. No support or recruiter message was sent.
