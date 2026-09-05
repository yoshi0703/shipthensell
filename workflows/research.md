# Research coordinator and workers

Follow common.md. Research is read-only on third-party sites: no form input,
confirmation navigation, submission or user send-approval request.

Create a Runs row with unique run_id, local_date, phase=research, state=running,
config hash, total ceiling = shards * waves * items_per_worker, writer_state=active. Resolve the saved
project via list_projects. The user-installed schedule explicitly authorizes new
standalone worker tasks; use create_thread, not subagents. Pass the configured
model/effort, local project, pinned hashes, campaign/run ID, shard and item limit.
After candidate discovery and queue persistence below, start workers for nonempty
assigned queues, at most the configured shard count. Each worker is sequential and
must not spawn tasks. Wait with bounded wait_threads calls. When a shard reaches
its item ceiling and supplies its cursor, create its next wave if configured.
Candidate exhaustion ends that shard normally; do not create empty replacement waves.
No more than shards tasks run concurrently. Never reuse a worker or fill missing
results with estimates. Persist each returned task ID and cursor in Runs.

The coordinator discovers candidate URLs with minimal legal identity evidence,
deduplicates against the private whole-CRM index and assigns corporate_key via
shard before deep inspection. Persist the candidate queue and search cursor in
Runs.cursor_json before dispatch. Reuse discovery results across shards and waves.
Unresolved legal identity stays needs_review; do not deep-research it in multiple
workers. Workers consume only their assigned bounded queue, following target
queries/region/industry and inspecting official sites; Google Maps is useful for local businesses, ordinary search
for other products. First record minimal identity and official business inquiry
form evidence. Only then collect additional relevant public observations and
compose the message using workflows/copywriting.md. Read it completely in this
phase only. Separate facts from hypotheses. Rank observations require query/location/time;
no fixed rank threshold is assumed for non-local products. Skip no form,
no-sales, consumer support/recruiting/booking-only forms, CAPTCHA, login, upload,
a host-required personal consent action, recipient identity mismatch, blocklist or recent
contact. Record why. Eligibility checks are limited to the form page as specified
in common.md. Do not open linked policy pages to investigate sales restrictions.
Record terms/privacy checkboxes in consent_checks: exact visible label, linked
absolute URLs, required boolean and checked=true for the intended operation.
Use an explicit empty list if no consent checks apply. Do not check them during
research. Do not select unrelated subscription/marketing opt-ins.

Deduplicate every corporate_key against previous candidates and contact history.
Only count unique assigned candidates processed in this run; a mistakenly assigned candidate is returned to the coordinator before deep
inspection and does not count toward the worker ceiling. A skip counts
as processed, not as prepared. Sources exhausted is a completed run with reason
exhausted; persistent tool failure is partial. No invented leads to reach quota.
Persist every outcome, including skips, in Runs.outcomes_json with corporate_key,
state (prepared/skipped/needs_review), evidence and row_id for prepared outcomes. Cursor includes query, result position,
last corporate_key, processed count and search evidence for the next wave.

Save eligible rows as pending_approval: all fields in crm-columns.json, immutable
row_id, campaign, research_run_id, corporate_key, shard, official URL chain,
recipient company, exact form URL, complete sender_fields JSON, field_bindings, exact body,
verified facts/evidence, observed_at and immutable prepared_at (UTC). Use stable
ASCII sender_fields keys with exact field_bindings name/label/required values,
including any subject field. Compute digest(payload(row)) with the helper; read
back every value. Repeated/ambiguous form labels require an unambiguous binding
before approval, never a guessed target. Unspecified form fields are not authorized. Workers write unique lead rows
and separate Runs rows, never shared counters. The coordinator derives totals
from all persisted worker records. Persist the expected dispatched task IDs in the coordinator checkpoint before
accepting results. Close each worker only after host-confirmed termination and
readback of all outcomes/lead rows. Use research_ready with decoded outcomes_json,
expected task IDs, pinned config hash and items_per_worker. Counts are ceilings;
missing records, duplicate identities and mismatched evidence cannot pass.
A reconciled partial run may expose only its fully saved prepared rows; verify
each row_id against its outcome and payload hash. Preserve partial/failure reasons
and unprocessed cursors. Persist readiness evidence and writer_state=closed on the
coordinator only after every writer is confirmed stopped. A process killed before
its records reconcile remains blocked, regardless of valid-looking lead rows.
