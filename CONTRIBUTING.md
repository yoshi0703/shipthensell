# Contributing

Open an issue with the workflow phase, expected/actual behavior and a redacted
reproduction. Never attach real CRM exports, email bodies or credentials.
Keep changes scoped. Run `python3 -m unittest discover -s tests -v` before a PR.
Tests must stay offline and use example.com/synthetic contacts. Workflow changes
should preserve explicit authorization, identity checks and no-retry semantics.
Include migration notes when changing headers, state or config. Changes to the
setup flow need a documented dry run; do not send real outreach to test a PR.

Useful next contributions: connector capability tests, additional CRM adapters,
setup usability and small, evidence-based outreach examples in more languages.
