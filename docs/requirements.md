# Requirements and evidence

Source: “Cresta AI Agent Developer Role - Next Steps” and its two PDFs.
The implementation is deployed in the supplied sandbox. Revision 19 passed all
55 local checks, 27 shared native cases and 22 supplemental live conversations.
Fabio authorized final delivery on November 8, 2026; the original email thread
now contains the submission and both complete JSON test exports. The receipt
is stored locally in `delivery/2026-11-08/email-receipt.json`.

| Requirement | Current evidence | Remaining work |
| --- | --- | --- |
| Marina, Ocean Airlines Sapphire voice agent | Prompt, active voice agent; Fabio reports successful voice booking | Rehearse the 2–4 minute interview demo |
| Search → save passenger → booking | Published happy paths and live regression with all three tools, real IDs, confirmation and total | Final outcomes in verification summary |
| Unsupported route / absent requested flight → Hangup | Prompt, full-inventory checks, native cases and local coverage | Passed in final shared suite |
| Deferral → simulated hold offer, expiry, Hangup without booking | Successful live stage-dependent conversations after passenger save; no backend hold invented | Passed in final shared suite |
| New bookings only; no payments, cancellation, refund or policy advice | Live refusal/redirect cases; seat-only clarification verified on revision 19 | Passed in final shared suite |
| Human request at any stage → Hangup | Live greeting, search, after passenger save, after booking and mixed-request cases | Passed in final shared suite |
| Actual passenger save with returned ID | Successful live conversations and SDK state checks | Passed in final shared and supplemental suites |
| Truthful AI disclosure | Welcome and successful live direct/adversarial/mid-booking cases | Passed in final shared suite |
| Custom code and secret integration | Deployed bundle, technical secret ID `ai-agent-51-secret`, passing remote validation | Keep final revision and bundle references in evidence |
| Official CLI | v1.0.0 installed, authenticated and used for publication/tests | Complete |
| Agent `AI Agent 51` active in environment | `results/platform-agent.json`, downloaded YAML and raw JSON snapshot | Keep latest revision verified |
| Secret `AI Agent 51 Secret` | Logical name mapped to platform-valid technical ID `ai-agent-51-secret`; live tools authenticate | No separate CLI display-name option established |
| Test set `AI Agent 51 Testing` | 27 installed native cases, three API definitions, ten response rules | Passed 27/27 on revision 19 |
| Structured tests and downloaded JSON results | Actual baseline and final run exports; local evidence separately labelled | Both full suites passed; evidence retained |
| Leave working agent in supplied environment | Active revision 19; fresh platform download validates; published booking and owner voice test succeeded | Owner review / demo rehearsal |
| Explain design in interview | README, ARD, decisions, demo and test report | Owner review / rehearsal |
| Independent work; AI assistance permitted | Implemented in the supplied workspace and sandbox | Submission sent in original email thread with owner authorization |

See [test report](testing.md) and `results/verification-summary.json` for final
counts, run IDs and historical failures. Historical
`results/agent-remote-validation.json` predates deployment and records the old
missing-bundle error; `results/platform-validation.json` is the current check.

The API generates flights for arbitrary airport codes, so empty inventory needs
a controlled response. `booking-timeout` uses HTTP 503 to exercise an unknown
write outcome; actual socket timeout handling is tested locally. Native evaluator
passes alone do not prove consent, exact ordering, or absence of duplicate writes:
review transcripts and actual tool calls. A boolean `confirmed` argument alone
does not prove spoken consent.

Sandbox implementation, testing and final delivery were authorized. Delivery is
complete; interview demonstration rehearsal remains the owner's next step.
