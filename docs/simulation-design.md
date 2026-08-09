# Simulation and dataset design

## Clock and reproducibility

- Default seed: `42`.
- Default tick: two real seconds.
- Each tick advances one simulated minute.
- Reset restores seed, clock, state, active scenario, and deterministic future sequence.
- Generate 24 hours of baseline history at one-minute cadence for charts.

Generated runtime files live under `data/generated/` and are ignored by source control.

## Dataset columns

Sensor history includes timestamp, temperature, humidity, CO2, PM2.5, ambient light, noise, presence, bed occupancy, desk occupancy, window, curtain position, computer watts, and inferred context.

Device history includes timestamp, device ID, property, previous value, new value, source, request/action ID, and reason.

Scenario files follow `contracts/scenario.schema.json` and contain metadata, initial actions, timed actions, and duration.

## Baseline behavior

- Temperature follows daily sinusoidal drift plus bounded seeded noise; AC gradually moves it toward target.
- Humidity follows weather-like drift; AC and humidity device influence it gradually.
- CO2 rises with presence and closed window, falls faster with open window.
- PM2.5 receives small random disturbances; purifier reduces it by speed.
- Ambient light follows time of day and curtain position; active lights add local illumination.
- Noise combines baseline, fan, AC, purifier, and scenario contributions.
- Power follows device states and computer activity.
- All values are clamped to plausible configured bounds.

Context remains deterministic:

- `working`: desk occupied, computer active, bed empty.
- `sleeping`: bed occupied, late period, desk empty.
- `reading_in_bed`: bed occupied plus explicit reading scenario/request.
- `relaxing`: room present, bed and desk empty.
- `away`: room not present.

User correction can temporarily override inferred context.

Manual controls also feed preference learning. After a successful manual command, storage checks the latest action for each explicitly supplied property. Evidence is recorded only when that prior action came from the assistant within 30 simulated minutes and its output equals the manual command's starting value. Three identical targets under the same inferred context confirm a `learned` preference.

## Required scenarios

| ID | Main state |
| --- | --- |
| `working` | Desk occupied, computer active, warm room |
| `relaxing` | Present in living zone, neutral conditions |
| `sleeping` | Bed occupied, late time, low light |
| `reading_in_bed` | Bed occupied, bedside reading context |
| `hot_room` | High temperature and humidity |
| `stuffy_air` | High CO2, closed window |
| `polluted_air` | High PM2.5 |
| `strong_sunlight` | High lux, open curtain, rising heat |
| `quiet_comfort` | High device noise while cooling |
| `empty_room` | No resident or occupied zones |

Scenario actions use the same validation path as manual and assistant actions. Scenario activation and scenario-driven changes are recorded but do not create preference evidence.
