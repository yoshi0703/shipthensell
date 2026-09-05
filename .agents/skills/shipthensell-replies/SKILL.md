---
name: shipthensell-replies
description: Run the ShipThenSell replies phase within an explicitly configured campaign, following its pinned run contract.
---

# Reply triage

Read the repository AGENTS.md, workflows/common.md, workflows/replies.md,
docs/crm.md and config/crm-columns.json completely. Require the current task's
pinned file hashes and private campaign config. If no installed run or explicit
manual run scope exists, explain setup; do not enroll users or contact prospects.
Follow the phase contract exactly, including approval, identity and recovery gates.
For manual runs, first prove no coordinator or worker is active on this CRM.
Never override the host's tool permissions or infer approval from an empty answer.
