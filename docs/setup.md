# Setup and lifecycle

## Requirements

Use a Codex desktop installation exposing project automations, task creation and
waiting, Google Drive/Sheets, Gmail, Google Calendar and the in-app browser.
Python 3.11+ runs the local helper without third-party packages. A plain CLI-only
session can generate the plan but cannot register desktop automations. Tool and
model availability varies by account. The setup skill checks the current host.
Local runs depend on the host and connected services being available; this repo
ships no hosted scheduler. Codex and external services may incur their own costs.

## One prompt

Clone the repository, add it as a local Codex project, and say:

> Set up ShipThenSell for my product. Ask me for the missing details, connect my
> CRM and mailbox, then register the three scheduled tasks in this project.

Codex uses the setup skill. It collects product evidence, sender fields, target
queries, locale, accounts, model and timezone. Defaults are 03:00 research, 10:00
outreach and reply checks every three hours. The research profile is three shards
and two waves, at most 50 candidates per worker: 300 researched candidates, not
300 qualified leads or guaranteed sends. Sending allows at most 50 attempts per
shard (150 total) by default; skipped/uncertain results are reported separately.
Change these limits deliberately in private config before activation.

Form inputs, listed terms/privacy checkbox operations and submissions wait for
a complete batch approval. Consent labels and URLs appear in that approval;
linked policies are not separately investigated. Host-required personal consent
steps still stop the item. Draft-only is
the default for replies. Users may explicitly authorize `send_after_quality_gate`
for positive, question and scheduling replies within the recorded campaign.
That mode does not authorize cold email, other recipients, forwarding, bookings,
contracts or consent bypass. Without a usable confirmation surface, outreach
remains pending. The setup itself sends no sales messages.

## Local commands

```sh
python3 scripts/shipthensell.py init
# Fill .shipthensell/config.json, retaining enabled=false.
python3 scripts/shipthensell.py validate
# Complete live checks, save enabled=true, then generate final pins.
python3 scripts/shipthensell.py plan
# Mirror final config hash in CRM Settings and read back before activation.
python3 -m unittest discover -s tests -v
```

`plan` writes a private reviewable plan; it makes no network calls and does not
install anything. Its pinned prompts instruct agents to verify source/config
hashes before calling any external tools. Config validation is structural, not
proof of authentication, consent, valid claims or working delivery. Codex must
perform the live checks in the setup skill.

## Updating, pausing and removing

Ask Codex to pause ShipThenSell; it reads the saved IDs and updates only those
three tasks through the automation tool. Verify PAUSED readback. To change a
schedule/config, pause, review edits, update CRM Settings and regenerate prompts,
then update the same IDs and resume. Do not simply pull new code and refresh
hashes unattended. On hash drift a run stops. To uninstall, ask Codex to delete
these three automation IDs; retain your private CRM and records unless you
explicitly request their deletion. Deleting the clone alone does not remove
scheduled tasks.

## Troubleshooting

- Missing connector/account: finish authentication in Codex; never copy tokens
  into JSON. A different signed-in mailbox is an error, not a fallback.
- Research below quota: reconciled saved rows remain eligible. Missing worker
  evidence or active writers block that source run; inspect Runs and cursors.
- Pending approval: review the full batch in its task. No answer means no send.
  Confirmed closed checkpoints permit reply monitoring; resume through the sole
  coordinator, never by reviving an old worker.
- Unknown delivery: reconcile the existing attempt with real evidence. Never
  retry automatically, even if a draft remains or CRM success was not recorded.
- Duplicate schedule/run/ledger ID: pause the campaign and reconcile ownership.
- Timezone mismatch: configure the scheduler's actual timezone before activation.

## Example config fields

`product.approved_facts` is an array of objects, for example:

```json
[{"claim": "Exports reports as CSV", "source_url": "https://example.com/docs/export"}]
```

Replace this synthetic claim with a verified capability of your product. The
validator requires the same mailbox for sender.email and gmail_account; aliases
are not supported in v1. Google Drive may use a separate authorized account.
`reply.auto_send_authorization` holds the user's actual scoped authorization text,
never a credential. Leave it empty in draft_only mode.

## v2 operating changes

Research counts are ceilings; reconciled closed partial runs can supply verified
prepared rows. Unattempted backlog from earlier dates remains eligible, ordered
by immutable prepared_at, subject to current evidence, cooldown and blocklist.
The attempt ceiling is per campaign-local day and shard across all runs/resumes.
Coordinator approval may cover exact worker subsets only if the host supports
handoff; otherwise worker-local approval is retained. These three changes widen
workflow eligibility/approval portability, not external action permissions.

The approval payload is v2 and includes field bindings. Read the CRM migration
before updating an existing installation. `reply.weekdays` uses 0=Monday through
6=Sunday; the example uses Monday–Friday. Preserve the user's operating preference.
Calendar access is checked only when producing scheduling proposals.

Offline setup dry run: use synthetic complete config with enabled=false; structural
validation must pass and plan generation must fail. Save enabled=true in an isolated
temporary clone, generate three PAUSED phase-pinned plans and compare the final file
hash. Fake CRM Settings must store/read back that hash. No registration, connector
writes or messages are performed by the test. Live identity/timezone/registration
checks remain setup requirements; offline success does not prove them.
