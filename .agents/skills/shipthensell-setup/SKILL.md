---
name: shipthensell-setup
description: Set up ShipThenSell when a user explicitly asks to install its sales workflow and register its three Codex desktop automations.
---

# Setup

Read `docs/setup.md`, `docs/crm.md` and `config/example.json` completely.
Use the user's language. Explain that initial outreach is approved per batch and
reply sending is an optional separate authorization. Set up the requested scope
without asking the same question twice. Never run a live campaign during setup.

1. Run `python3 scripts/shipthensell.py init`. It preserves any existing config.
2. Gather missing product facts with evidence URLs, target region/industry/queries,
   sender identity, chosen accounts, timezone and a model available on this host.
   Ask whether reply mode should stay draft-only or automatically answer positive,
   question and scheduling replies. Record the exact explicit authorization text
   only for auto-send. Never infer it from "set up" or a config value alone.
3. Check connectors and account identity live. Connect Google Drive/Sheets, Gmail,
   Calendar and the Codex in-app browser; let the user complete authentication.
   Use a dedicated private CRM, following `docs/crm.md`. Before creating a new
   spreadsheet, explain that it stores prospects, messages and run history; the
   explicit setup request covers this campaign resource. Do not edit an unrelated
   spreadsheet. Resolve its ID by connector readback, never by title alone.
4. Resolve the saved local project through `list_projects`; if it isn't saved,
   ask the user to add this clone as a project. Do not invent a project ID.
   Select a supported model/effort. Verify the scheduler timezone against the
   chosen timezone in the app. A timezone in prompt prose is not a scheduler
   setting; stop if the app cannot honor it. Do not approximate DST with UTC.
5. Save the completed config with enabled=false, then run `validate` for structural
   checks. Initialize the exact CRM headers and read back account identities.
   After live checks pass, save enabled=true, generate `plan`, then record that
   final file hash and enabled value in CRM Settings and read back both. All
   schedule pins must use this same final config; no hash from the disabled file.
6. This setup request explicitly asks for three standalone project schedules.
   Discover the current `automation_update` tool and use its live schema.
   Use project cron automations in the local environment; do not use heartbeat
   tasks. Translate the plan's schedule intent into the scheduler's supported
   recurrence. Do not write `automation.toml`, use shell cron or invent an API.
   Use each plan prompt verbatim; it pins shared dependencies, its phase dependencies and private config.
7. Read `.shipthensell/installation.json` if present, and inspect the current
   automation inventory by the tool's documented mechanism before creating.
   Match campaign marker + project + phase. Update matching IDs in place; never
   duplicate them. Multiple matches: stop and report the IDs for resolution.
   Register all three PAUSED first; persist each returned ID immediately. Read
   all three back, then activate and read back again. On partial failure, pause
   only this installation's newly activated tasks and report what remains.
8. Save IDs, project ID, phase, recurrence, status, timezone evidence, pinned
   config hash and returned readback in `.shipthensell/installation.json`.
   Report actual names/times/status and any remaining gate. Never claim a future
   run succeeded from successful registration.

Reruns preserve unrelated automations and existing preferences. A code/config
change requires reviewing the diff and regenerating the plan while affected tasks
are paused. Update affected phase prompts in place; shared/config/schema changes
require all three prompts and CRM Settings to be consistent. Read docs/crm.md
for the v2 migration before resuming an existing installation. Missing tools or unreadable state blocks
activation, not local setup work. To stop, update only these saved IDs to PAUSED
through the tool and read back; keep CRM and logs intact.
