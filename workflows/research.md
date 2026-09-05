# Research coordinator and workers

Follow common.md. Research is read-only on third-party sites: no form input,
confirmation navigation, submission or user send-approval request.

Create a Runs row with unique run_id, local_date, phase=research, state=running,
config hash, total target = shards * waves * items_per_worker. Resolve the saved
project via list_projects. The user-installed schedule explicitly authorizes new
standalone worker tasks; use create_thread, not subagents. Pass the configured
model/effort, local project, pinned hashes, campaign/run ID, shard and item limit.
Start three workers (or configured shard count). Each worker is sequential and
must not spawn tasks. Wait with bounded wait_threads calls. When a shard finishes
its exact item limit and supplies its cursor, create its next wave as a new task.
No more than shards tasks run concurrently. Never reuse a worker or fill missing
results with estimates. Persist each returned task ID and cursor in Runs.

Workers follow target queries/region/industry and inspect visible search results
and official sites; Google Maps is useful for local businesses, ordinary search
for other products. First record minimal identity and official business inquiry
form evidence. Only then collect additional relevant public observations and
compose a short message from approved product facts and verified recipient facts.
Separate facts from hypotheses. Rank observations require query/location/time;
no fixed rank threshold is assumed for non-local products. Skip no form,
no-sales, consumer support/recruiting/booking-only forms, CAPTCHA, login, upload,
a host-required personal consent action, identity mismatch, blocklist or recent
contact. Record why. Eligibility checks are limited to the form page as specified
in common.md. Do not open linked policy pages to investigate sales restrictions.
Record terms/privacy checkboxes in consent_checks: exact visible label, linked
absolute URLs, required boolean and checked=true for the intended operation.
Use an explicit empty list if no consent checks apply. Do not check them during
research. Do not select unrelated subscription/marketing opt-ins.

Deduplicate every corporate_key against previous candidates and contact history.
Only count unique assigned candidates processed in this run; nonassigned results
advance search position but do not count toward the worker target. A skip counts
as processed, not as prepared. If sources exhaust or tools fail, mark partial;
no invented leads to reach quota. Cursor includes query, result position,
last corporate_key, processed count and search evidence for the next wave.

Save eligible rows as pending_approval: all fields in crm-columns.json, immutable
row_id, campaign, research_run_id, corporate_key, shard, official URL chain,
recipient company, exact form URL, complete sender_fields JSON, exact body,
verified facts/evidence and observed_at. Compute payload SHA with the helper over
row_id, corporate_key, company, form_url, sender_fields, body and consent_checks; read back all
values. Unspecified form fields are not authorized. Workers write unique lead rows
and separate Runs rows, never shared counters. The coordinator derives totals
from all persisted worker records. Complete only if every expected wave/shard
has exactly items_per_worker unique records, matching config hash and task ID.
Record partial/error otherwise; outreach cannot proceed from a partial run.
