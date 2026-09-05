# Private CRM contract

Create a dedicated Google spreadsheet using the connector in setup. Create the
five tabs and header row exactly as `config/crm-columns.json`; resolve columns by
header, not historical A:U positions. No public sharing. All data uses RAW text
semantics. Settings contains campaign, config_sha256, google_account,
gmail_account, timezone and enabled; mirror the validated private config values.
Never put tokens in any cell. For a new installation, all other rows start empty.
Do not migrate the author's existing CRM automatically.

Each lead has a stable unique row_id independent of physical row number.
Dates are UTC RFC3339 with timezone; campaign-local dates belong in Runs.
Structured values are JSON strings. Hashes use the helper's exact canonical
encoding: ASCII keys, UTF-8, sorted keys, no whitespace, no NaN/floats. Values are
strings/integers/booleans/null/lists/objects. This is a repository-specific format,
not a claim of full RFC 8785 support. Use the helper, never model-computed hashes.

## Consent snapshot and upgrade

Leads.consent_checks is a JSON array of objects with exact visible label, urls
(array of absolute HTTP/HTTPS evidence links), required (boolean), and checked=true. Use []
when no consent check applies. The approval payload includes this entire array.
Only terms/privacy acceptance necessary for this inquiry is in scope; unrelated
marketing opt-ins, purchases and contract execution are excluded. Page labels
and URLs are recorded without claiming review of linked policies.

Existing installations must use the v2 migration below. HTTP evidence URLs do
not authorize HTTP form submission or policy crawling. The form URL remains HTTPS.

## State and retries

Leads: pending_approval → approved → attempted → sent, or skipped/needs_review.
Approval never clears an attempt. A changed approval payload goes back to
pending_approval only if there was no attempt. Review historical contact and
blocklist by corporate_key across every run. A recorded attempt suppresses a
retry even if the form was never reached after the marker write; reconcile it
manually before any future separately authorized contact.

Runs business state: running → completed/partial/pending_user/failed.
writer_state is separately active/closed; absence means unverified, not closed. Worker rows refer to their
parent run; count actual unique records, not summaries alone. A stale running row
requires reconciliation, never automatic lock expiry. There is no distributed
lock: support is one host/one installation per CRM. Pause schedules before manual
edits and do not start overlapping manual runs.

## Reply recovery

Only one ReplyLedger row may exist per message_id. Index all pages before new work
and fetch full unresolved records. Intent and draft payload must be saved before
Gmail draft creation; draft_status is planned/attempted/completed/not_needed.
Recover uncertain draft creation only by exact unique matching, never recreation.
Unmatched records have empty row_id and no pre/post lead mutation; complete their
classification only after durable reason/summary readback. review_status=open
preserves them independently of the polling cursor.
For crm_status=pending, parse saved pre_json/post_json, verify hashes and row_id,
and compare the complete saved lead snapshots with current Leads. If current
matches post, only mark completed. If it matches pre, apply saved post once,
read back and mark completed. Otherwise stop with WRITE_STATE_MISMATCH. Never
regenerate text, classification or snapshots to fit changed CRM. Completed rows
retain their payload forever within the user's retention policy.

Email sending has a separate state: not_attempted → attempted → sent/unknown.
An attempted timestamp is written/read back before sending. Any attempted,
sent or unknown state blocks retries. CRM recovery cannot reset that state.
Draft-only completed messages are not later auto-sent simply because reply mode
changes; changes apply only to newly received, unprocessed messages.

Legacy drafts created before ledger append may only be reconciled from saved
exact payload evidence. Missing/ambiguous evidence requires review. This contract
reduces duplicate actions but cannot make Gmail and Sheets an atomic transaction.

## v2 migration and ownership checkpoints

Pause all three schedules and reconcile every writer through actual host task
status. Back up private settings/CRM; do not include data in Git. Then:

1. Set config version=2 and add reply.weekdays from the existing user preference
   (example Monday–Friday). Keep enabled=false for structural validation.
2. Add Leads.field_bindings and prepared_at, Runs.writer_state/checkpoint_json/
   outcomes_json, and ReplyLedger.draft_status/review_status by header. Retain
   every old row, attempt timestamp, sent result and ledger send marker.
3. For each unattempted candidate, inspect its form page. Map ASCII sender_fields
   keys to exact field_bindings entries: key, name, label, required. A subject is
   a bound field too. Names/labels may be Unicode values. Reject ambiguous targets.
   Keep historical approvals as evidence but obtain fresh v2 approval; never
   silently convert approval hashes. payload() adds payload_version=2.
4. Populate immutable prepared_at from reliable preparation evidence. If missing,
   hold the row for revalidation and use that documented preparation time; never
   guess historical order. Historical attempted rows need no new approval and
   must never re-enter backlog. Normalize stored shard as an integer for helpers.
5. Reconcile source Runs and reconstruct outcomes only from real saved evidence.
   Missing task/outcome records block the source run. If safe reconstruction is
   impossible, explicitly re-prepare unattempted candidates under a new research
   run with provenance to the old row, preserving global corporate deduplication;
   do not relabel old runs completed. Never fabricate closed writer evidence.
6. Save final enabled=true only after live checks; generate plan, mirror the final
   config hash in Settings, read back, update all three paused prompts and resume
   the existing schedule IDs. Old hashes deliberately fail closed.

outcomes_json is a list of corporate_key/state/evidence and row_id for prepared
outcomes. Pass it as outcomes to research_ready, using task IDs saved before
dispatch. Reconcile lead rows against these entries, not just aggregate counts.
Coordinator checkpoint_json holds dispatched IDs, source run IDs, exact approval
scope and digest, pending/deferred row IDs, remaining budget, resume position and
host terminal evidence for every worker. Persist/read back before writer_state
becomes closed. approval_checkpoint validates supplied evidence only; the host
must actually confirm termination. Uncertain writes never release ownership.

Resume with fresh sole ownership and fresh safety checks; the saved scope is
immutable. Approval evidence records decision, task_id, approved_at, evidence and
scope_sha256. Use approval_covers with actual host handoff support, never assume
parent approval grants a child authority. Administrative field changes do not
invalidate payload approval, but opt-outs, attempts and expired facts still veto
sending. Count daily attempts from immutable lead timestamps, not resettable run
summaries. Old pending_user tasks remain terminal and must not restart themselves.
