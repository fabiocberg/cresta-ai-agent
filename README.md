# Marina — Cresta interview example

Ocean Airlines Sapphire reservations voice agent for the interview exercise.
Platform names: **AI Agent 51**, **AI Agent 51 Testing**, **AI Agent 51 Secret**.

## Status

The agent and secret are active in the supplied Cresta sandbox. Remote validation
passes. Search → passenger registration → booking has completed through the
published agent, and Fabio reports a successful Simulator voice booking.

Local verification passes **55 tests**: 35 API/session/generator checks and 20
SDK integration checks. Revision **19** passes **27/27 native conversations**
(two live and 25 strict controlled cases) and **22/22 supplemental live-API
conversations**, with no generation errors in either final run.

The original 19 failures were traced to our replay authentication initialization
and event-loop integration. The corrected deployed bundle awaits OAuth refresh
on the serving loop. Native tool traces confirm controlled errors, safe unknown
write handling, inventory limits, identity, human requests and booking behavior.
See [test evidence](docs/testing.md) and [diagnosis](docs/native-runner-issue.md).
The local `results/` directory holds run IDs, logs and transcripts.
The submission and both conversation exports were sent in the original email
thread on November 8, 2026. The receipt and copies of the attachments are in
the local `delivery/` directory.

## Interactive draft preview

With the authenticated draft and local custom-code bridge running, start:

```sh
.venv/bin/python scripts/preview.py
```

Open `http://127.0.0.1:9138` on this computer. This loopback-only text interface
uses the official `cresta agent chat` CLI, the real Cresta model and the sandbox
API. It contains no alternative model or simulated chat replies. Use fictional
passenger details and a fresh `example.com` email for every new registration.
“Nova conversa” starts a separate conversation. Voice and the widget's anonymous
authentication are outside this local text preview. The draft requires its
CLI heartbeat, bridge and authenticated session to remain running.

## Implementation

| File | Responsibility |
| --- | --- |
| [Agent configuration](ai-agent-51/agent.yaml) | Official scaffold, voice, three custom tools and native Hangup |
| [Design](ai-agent-51/ARD.md) | Conversation flow and runtime boundaries |
| [Prompt](prompts/marina.md) | Identity, booking flow, required exits and limitations |
| [SDK tools](custom-code/functions/booking.py) | Supported function signatures, secret and variables |
| [Session](custom-code/marina/session.py) | Current-search IDs, saved passenger, consent flag and repeat-write guards |
| [API boundary](custom-code/marina/flight_api.py) | Validated requests and sanitized responses |
| [Transport](custom-code/marina/cresta_transport.py) | Live HTTP and strict Director SDK replay |
| [Native manifest](tests/native-manifest.json) | 27 cases: two live and 25 controlled, with ten response rules |
| [Requirements](docs/requirements.md) | Evidence and remaining acceptance work |

## Local verification

The SDK requires Python 3.13 or newer; this workspace uses Python 3.14 in
`.venv`. The API core uses only the standard library. SDK packages come from
Cresta's authenticated package index.

```sh
.venv/bin/python scripts/test_local.py
cd custom-code
../.venv/bin/python -m pytest -q tests --junitxml=../results/sdk-tests.xml
cd ..
PATH="$PWD/.venv/bin:$PATH" cresta custom-code validate ./custom-code --no-venv > results/custom-code-schemas.json
cresta agent validate ./ai-agent-51 --custom-code-schemas @results/custom-code-schemas.json --output json
cresta agent test push --test-local 'test_cases/*.yaml' --test-set 'AI Agent 51 Testing' --dry-run
```

The native cases and response fixtures are generated together by
`scripts/prepare_native_tests.py` (requires PyYAML). Regenerate before a later
session to select a future departure date and fresh synthetic emails. If mocks
have already been installed, update their remote bodies deliberately: the
installer reuses recorded rule IDs and does not overwrite their response bodies.
Synchronize case configuration and mock attachments before execution.

Local generator/evaluator tests also require Jinja2. Install the development
dependencies with `.venv/bin/python -m pip install -r requirements-dev.txt`
after configuring Cresta's package index.

## Direct API smoke

Privately set `FLIGHT_API_KEY` in the environment, then run:

```sh
.venv/bin/python scripts/smoke_api.py
# Creates one synthetic passenger and one sandbox booking:
.venv/bin/python scripts/smoke_api.py --book
```

The scripts use a unique `example.com` email, fictional passenger details and a
future departure. No write is retried automatically. Each run replaces its
corresponding latest evidence file. Scripts read process variables; they do not
automatically load `.env` files.

The SDK maps `FLIGHT_API_KEY` to technical ID `ai-agent-51-secret`. The requested
logical name is **AI Agent 51 Secret**; the CLI has no separate display-name
option. Verify the displayed name during publication. Keep credentials and
original attachments in ignored `.private/` storage or the secret store.

## Before the interview

Rehearse the 2–4 minute interview demonstration. Voice success is owner-reported;
no independently captured recording or verified demo duration is claimed.

## Platform command reference

The authenticated official CLI is the primary command reference: `cresta --help`,
`cresta agent test --help`, `cresta agent test schema --output json`, and
`cresta custom-code upload --help`. The private exercise attachments remain in
ignored `.private/` storage.
