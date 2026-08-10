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

Daily routine represents one work-from-home resident:

- `sleeping`: 00:00–06:30 and 23:00–24:00.
- `relaxing`: 06:30–07:30 and 18:30–23:00.
- `working`: 07:30–11:45 and 13:00–17:30.
- `away`: 11:45–13:00 and 17:30–18:30.
- Windows open briefly at 06:30, 11:30, and 18:30. AC, curtains, main light, bedside light, computer, and monitor follow occupancy and time of day only while generating baseline history; runtime manual or assistant controls are not overwritten.

- Temperature follows daily sinusoidal drift plus bounded seeded noise; AC gradually moves it toward target.
- Humidity follows weather-like drift; AC and humidity device influence it gradually.
- CO2 uses exponential movement toward context-specific targets: lowest while away or ventilating, moderate while relaxing, higher after long work or sleep periods. This remains stable for accelerated multi-minute ticks.
- PM2.5 receives small random disturbances; open windows move it toward outdoor conditions and purifier reduces it by speed.
- Ambient light follows time of day and curtain position; active lights add local illumination.
- Noise combines time of day, occupancy, desk work, open-window outdoor sound, fan, AC, purifier, and scenario contributions.
- Power follows device states and computer activity.
- All values are clamped to plausible configured bounds.

Seed `42` baseline statistics:

| Sensor | Minimum | Median | Maximum |
| --- | ---: | ---: | ---: |
| Temperature | 25.8°C | 26.8°C | 29.5°C |
| Humidity | 54.9% | 61.9% | 70.2% |
| CO2 | 495.4 ppm | 841.5 ppm | 1,035.9 ppm |
| PM2.5 | 10.0 µg/m³ | 11.8 µg/m³ | 15.5 µg/m³ |
| Ambient light | 0 lux | 192.5 lux | 2,267.6 lux |
| Noise | 29.4 dB | 37.3 dB | 40.6 dB |

CO2 is at or above 1,000 ppm for 194 of 1,440 minutes (13.5%), concentrated near the end of closed-window work and sleep periods. A three-day accelerated-runtime check also keeps the latest day below the warning threshold for more than half its samples. The dedicated `stuffy_air` scenario remains the severe 1,800 ppm case.

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
