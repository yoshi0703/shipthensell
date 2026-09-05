# Outreach coordinator and workers

Follow common.md. No prospect discovery or new copy in this phase.
Find exactly one completed research coordinator run for today's campaign-local
date and pinned config hash. Verify every expected wave/shard worker record and
unique processed count from CRM; pending approvals alone do not prove completion.
If missing, duplicate or partial, stop before creating send workers. Exclude
already-attempted rows across every prior run. No eligible rows: record zero.

Create one standalone worker per shard via create_thread, with pinned hashes,
project, model/effort, research_run_id and send_run_id. No subagents or child tasks.
Pass only at most send_attempts_per_shard oldest eligible rows, ordered by row_id;
remaining rows stay pending and are reported as deferred (not sent or silently
moved to a later research run). Persist IDs and track each to completion. Keep
send run open while a worker waits for approval; do not detach and unlock it.

Worker: re-read blocklist, whole-CRM cooldown, identity, exact URL/fields/body and
attempt history. Freeze the rows in ascending row_id using helper `manifest`.
Present every recipient/company, official form URL, sender field, full message,
row ID and payload hash, plus manifest hash and count. Ask for one explicit batch
approval covering input, the listed terms/privacy checkbox operations and one
submit per unchanged row. Show every consent label and linked URL; state that
linked policy pages were not reviewed. Do not summarize unseen terms as safe. Use a permitted host
confirmation mechanism. Missing/empty/denied answers are not authorization;
without a supported mechanism leave pending. Never input third-party forms first.
Do not treat any arbitrary nonempty answer as approval; it must clearly approve
this exact manifest in this worker task. Record approval evidence/task/time/hash.

After approval, process sequentially. Re-read the complete row and blocklist and
compare to approved payload; any changed field requires reapproval of that row.
Re-open the official URL via Codex's in-app browser and inspect current purpose,
identity, no-sales restrictions, CAPTCHA/auth/consent and required fields on the
form page only. Do not investigate linked policy pages. Compare all consent
labels, URLs and required flags to the approved snapshot. Changed or additional
consent requires reapproval before checking it. Perform approved terms/privacy
checks without a separate consent approval when host tools allow delegation. Host
browser confirmations still apply. If extra fields or changed form require new
values, do not invent them. Stop that item before input. Enforce the per-shard
attempt budget by CRM readback, including unknown results and earlier attempts.

Input the exact approved fields, verify the confirmation screen if present,
write submission_attempted_at to CRM and read it back before clicking submit
once. On failed readback stop the entire worker. No Enter submission, double click
or retries. Only an explicit success message, receipt or verified completion page
proves success; HTTP 200, empty fields or a disappeared button do not.
Save sent_at and evidence only for confirmed success. Unknown result retains the
attempt, becomes needs_review and stops the worker. CRM failure after a send also
stops it without retry. Coordinator closes run only after every worker is terminal
(completed, pending_user, partial or failed) and no live writer remains. Record
attempts, confirmed sends, deferred rows and failures independently.
