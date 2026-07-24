# Scenario definitions

Phase 2 provides one JSON file per required scenario, validated against `contracts/scenario.schema.json`:

`working`, `relaxing`, `sleeping`, `reading_in_bed`, `hot_room`, `stuffy_air`, `polluted_air`, `strong_sunlight`, `quiet_comfort`, and `empty_room`.

Scenario files contain Vietnamese display text, duration, initial actions at minute zero, and optional later actions. They contain no executable Python.
