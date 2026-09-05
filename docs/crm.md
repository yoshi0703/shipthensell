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

## State and retries

Leads: pending_approval → approved → attempted → sent, or skipped/needs_review.
Approval never clears an attempt. A changed approval payload goes back to
pending_approval only if there was no attempt. Review historical contact and
blocklist by corporate_key across every run. A recorded attempt suppresses a
retry even if the form was never reached after the marker write; reconcile it
manually before any future separately authorized contact.

Runs: running → completed/partial/pending_user/failed. Worker rows refer to their
parent run; count actual unique records, not summaries alone. A stale running row
requires reconciliation, never automatic lock expiry. There is no distributed
lock: support is one host/one installation per CRM. Pause schedules before manual
edits and do not start overlapping manual runs.

## Reply recovery

Only one ReplyLedger row may exist per message_id. Scan all pages before new work.
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

If draft creation succeeded before ledger append, reuse exactly one matching
thread/reply-to/recipient/subject/body draft after readback. Multiple drafts or
changed contents require review. This contract reduces duplicate actions but
cannot make Gmail and Sheets an atomic transaction.
