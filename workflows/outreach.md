# Outreach coordinator and workers

Follow common.md. No prospect discovery or new copy in this phase.
Acquire sole campaign writer ownership on this host. Reconcile all source research
runs for this campaign and pinned config hash, including earlier local dates.
Use research_ready on every source run's dispatched task records and persisted
outcomes; verify each selected lead's row_id, prepared outcome and payload readback.
Missing/duplicate worker records or active writers block that source run. A closed,
reconciled partial run can contribute its fully saved prepared rows. Record all
excluded runs and reasons. Never change a lead's original research_run_id.

Read the whole-CRM attempt index, cooldown and blocklist. Use select_backlog with
eligible source run IDs, campaign-local date/timezone and configured shard/budget.
Order by immutable prepared_at, then row_id. Count all attempts on this local date
per shard across all send runs, including unknown results and resumed checkpoints.
A resume on another local date recomputes that day's budget. Persist selected IDs
and deferred IDs; deferred unattempted rows remain eligible next day. Zero eligible
rows is a recorded zero, not an error. Revalidate old form/product evidence before
approval; changed payload needs research preparation and fresh approval.

Create at most one standalone worker per shard via create_thread with pinned
hashes, project/model/effort, campaign, source run IDs, send_run_id, assigned row IDs
and remaining daily budget. No subagents/child tasks. Persist every task ID and
track it to host-confirmed termination. Workers process their assigned rows only.

Freeze exact rows using manifest, including field bindings and consent checks.
Present every company, form URL, complete field values/bindings, full subject/body,
consent labels/URLs/required flags, row ID and payload hash, manifest hash and count.
State linked policies were not reviewed. Request explicit approval for input,
listed terms/privacy operations and one submit per unchanged row. Never summarize
unseen terms as safe or input before approval. Missing, empty, denied, timed-out
or arbitrary nonempty answers do not authorize anything; use a permitted host
confirmation mechanism, otherwise persist pending_user.

When the host explicitly supports approval handoff, the coordinator may present
the full combined manifest once. Build approval_scope(campaign, send_run_id,
config_hash, rows), show its digest, and record decision=approved, scope_sha256,
evidence, approved_at and task_id from actual explicit user approval. Workers use
approval_covers on their subset and fresh rows. Handoff requires verified host
support, never an assumed boolean. If unsupported, each worker presents its own
scope/manifest and obtains approval in that task. Split oversized displays into
complete separately approved batches; unseen/truncated text is never approved.
Host browser confirmations and personal consent gates remain independent.

For pending approval, workers save exact scope/manifest, pending row IDs, budget,
cursor and reason in checkpoint_json, read back and terminate. The coordinator
checks all dispatched worker IDs against host terminal evidence and saved records;
use approval_checkpoint before saving the coordinator checkpoint and readback.
Only then set writer_state=closed. If any termination/readback is unverified, keep
ownership active and defer replies. Timeouts cannot release ownership. A user
answer to an old task must not restart its writer. Resume only through the single
coordinator after fresh ownership, config/pin/identity checks, current row,
blocklist, cooldown and all-run attempt reads. Restore saved approval scope (and
original send_run_id), recheck handoff support, payloads and budget. Stale approval
is not permission to reconstruct changed payloads or invent approval evidence.

After approval, sequentially re-read each complete row and blocklist. Compare
canonical payload to the approved snapshot; only payload changes invalidate
approval. Internal state, approval_json and bookkeeping changes alone do not.
Fresh eligibility, product facts and attempt checks can still veto an unchanged
payload. Re-open the HTTPS official form in the in-app browser, inspect identity,
purpose, no-sales notices, CAPTCHA/auth/personal consent and required fields on
that page only. Compare field bindings and consent label/URL/required flags to the
snapshot. Any new value, field or consent change returns that item for preparation
and reapproval before input. Do not crawl policy pages or invent values.

Immediately before input and again before submit, enforce the remaining daily
per-shard budget against fresh CRM attempts from all runs. Input only approved
strings, perform listed permitted consent checks and inspect confirmation screens.
Write immutable submission_attempted_at and read it back before clicking submit
once. No Enter submission, double click or retries. Failed marker readback stops
the worker. Explicit success message/receipt/completion page is required to save
sent_at and success evidence; HTTP 200 or a missing button is insufficient.
Unknown result retains the attempt, becomes needs_review and stops that worker.
Post-send CRM failure also stops it without retry. The coordinator closes writer
ownership only after every worker is terminal and durable. Report confirmed sends,
attempts, deferred rows, pending approvals and failures separately. pending_user
means unfinished business even when writer_state is closed.
