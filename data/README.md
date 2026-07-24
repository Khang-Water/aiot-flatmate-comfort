# Data ownership

- `scenarios/`: committed human-readable scenario definitions.
- `generated/`: reproducible simulator output; generated CSV/JSON files stay untracked.
- Runtime SQLite database will live at `data/flatmate.db` by default and stay untracked.

No external smart-home dataset is required. Python generator supplies every field needed by apartment, dashboard, assistant, and evaluation flows.
