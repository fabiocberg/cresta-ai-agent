# Verification report

Revision **19** of `ai-agent-51-20261107-808cff26` passed both complete platform
suites. The corrected bundle is `20261108-140157z-cli-2c7c068`. A fresh download
passes config, rules, schema and server validation; its prompt matches the source.

| Layer | Passed | Failed | Evidence |
| --- | --- | --- | --- |
| Local API/session/generator | 35 | 0 | `results/local-tool-tests.json` |
| SDK integration | 20 | 0 | `results/sdk-tests.xml` |
| Shared native suite: two live, 25 strict controlled | 27 | 0 | `results/cresta-final.json` |
| Supplemental live API suite | 22 | 0 | `results/native-live-final-detail.json` |

Shared run: `01a1bb86-901e-7f1b-8b3f-c2cb6da1fa78`. Supplemental run: `01a1bb85-87d4-7c61-86ba-f1f9b507367d`.
There are no `ERROR GENERATING RESPONSE` messages in either final run. These are
actual platform conversation exports, separate from the local test summary.
The supplemental suite does not replace the shared controlled suite.

## Original failures and corrections

Revision 12 passed only 8/27 shared cases, with 19 generation failures. A private
instrumented native tool isolated `OAuth2TokenUnavailableError`: our transport
used the SDK auth provider before initial refresh and started replay on temporary
worker loops despite the shared provider's loop-bound client/background work.
The deployed fix awaits initial refresh and runs replay on the serving loop.
OAuth errors are sanitized; no live fallback or automatic write retry was added.
Two new parametrized SDK cases exercise actual SDK auth/replay code at the mocked
network boundary across two tool invocations, for successful and rejected auth.
See [diagnosis and native probes](native-runner-issue.md).

Revision 16 then passed 24/27 shared and 22/22 supplemental cases. The remaining
shared failures were two reused live passenger emails and closing before the
caller could ask about an uncertain booking. Live fixture emails are now refreshed
before execution; uncertain-write conversations stay open for questions while
blocking another write. Revision 18 passed 26/27 shared and 21/22 supplemental:
the caller simulator emitted a **VISITOR** generation error and repeated its
attack instead of following the scenario, and a seat-only clarification failed
its evaluator. Both failures are retained, not counted as passes. Revision 19
clarifies that the caller still wants to book. Its first run retained the caller
generation failure and a seat-evaluator false negative. The API probe
(`results/seat-api-contract-probe.json`) confirms that `no_preference` is rejected;
requiring window, aisle or middle is an API constraint. The judge now distinguishes
that constraint from forbidden seat guarantees and change policies. The injection
case uses fixed visitor messages (attack, insistence, goodbye), with actual agent
responses generated between them, avoiding caller-model generation failures
without removing either attack. Both complete final suites pass. Earlier failed
runs remain available as revision 19 history.

Seven response-dependent evaluators now require evidence of the exact controlled
setup rather than accepting absence of unsafe operations alone. A constant
marker-only diagnostic tool failed the strengthened search-outage judge as
expected. This intentional negative-control failure is separate from acceptance.

## Coverage and evidence review

Local and native cases cover confirmed itinerary before passenger save, all five
passenger fields, current search/passenger IDs, invalid/out-of-order IDs, explicit
consent, actual confirmation/total/currency, passenger correction and reuse,
duplicate-write prevention, and uncertain-write blocking. Controlled cases cover
empty inventory, a requested flight outside the spoken shortlist, passenger
conflict, search/save outage and booking HTTP 503. Live cases cover identity,
scope, group limits, human requests at different stages, deferral and hold offer,
seat-only clarification, changing itinerary, and repeating confirmation.

Native metadata can repeat tool snapshots. Count operations using unique call
IDs or tool invocation counters/state; repeated metadata alone is not another
booking. Judges must inspect actual results, not caller claims or announcements.
The native Hangup aliases use fixed supported closings for normal calls, human
requests, unsupported inventory, and a simulated 30-minute hold offer. No backend
hold is created. The API accepts window, aisle or middle; no seat assignment or
later-change policy is promised.

## Repeat the tests

```sh
.venv/bin/python scripts/test_local.py
(cd custom-code && ../.venv/bin/python -m pytest -q tests --junitxml=../results/sdk-tests.xml)
.venv/bin/python scripts/refresh_native_live_cases.py
cresta agent test push --test-local 'test_cases/*.yaml' --test-set 'AI Agent 51 Testing' --yes
cresta agent test --agent ai-agent-51-20261107-808cff26 --revision 19 --test-suite 01a1b89f-ebb9-7067-9f77-b2cabd6e384f --concurrency 8 --results-file results/cresta-conversations-final.json --output jsonl
.venv/bin/python scripts/prepare_live_regression.py
cresta agent test --agent ai-agent-51-20261107-808cff26 --revision 19 --test-local 'test_cases/live_regression/final/*.yaml' --concurrency 8 --results-file results/native-live-final.json --output jsonl
```

Refresh the two shared live emails before every repeated run. Regenerating all
native cases also changes dates; deliberately update the remote mock bodies if
the fixture date changes. `scripts/install_native_tests.py` reuses remote rule
IDs and does not overwrite their bodies. Preserve mocks and set membership.
`agent test runs get --output json` returns an artifact path: copy that full
artifact, not just its summary. SDK commands require `.venv/bin` on PATH.

## Limits and delivery

`booking-timeout` uses controlled HTTP 503; actual socket timeouts are verified
locally. There is no upstream idempotency/status API, so exactly-once writes
across a process crash after API success and before state persistence cannot be
guaranteed. Simulator voice success is Fabio-reported; no independent recording
or verified 2–4 minute demonstration is claimed. Sandbox publication/testing are
authorized. Fabio explicitly authorized final delivery on November 8, 2026.
The submission and both complete JSON exports were sent in the original email
thread. The receipt is stored locally in `delivery/2026-11-08/email-receipt.json`.

Original revision 12 evidence is retained in `results/history/revision-12/`;
revision 16/18/19 exports and diagnostic failures remain separately labelled.
