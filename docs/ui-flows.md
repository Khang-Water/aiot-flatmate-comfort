# UI and interaction flows

## Visual direction

Cozy modern digital twin: warm wood and neutral surfaces, daylight-aware lighting, restrained status colors, rounded dashboard panels, and clear Vietnamese labels. Device color communicates state without being sole indicator.

## Navigation

| Route | Purpose |
| --- | --- |
| `/` | 3D apartment, context selector, assistant controls, current trace |
| `/dashboard` | Sensor tiles, latest 24-hour charts, and common device controls |
| `/history` | Recent conversations, final responses, status, and failures |

## Digital twin

- Orbit camera with reset control; no room editing.
- Resident moves among work, living, and bed contexts or disappears when away.
- User selects work desk, living room, reading in bed, sleeping, or away from the left context column.
- Kitchen and bathroom remain visual rooms only.
- Lights change brightness/color temperature visually.
- Curtain position, fan rotation, purifier/AC status, window state, and power indicators animate.
- Sensor overlay toggles show temperature, humidity, air quality, light, and noise.
- Reduced-motion setting stops walking and continuous rotations while preserving state changes.

Below the 3D view, show Vietnamese apartment state as a text/table equivalent for accessibility and WebGL fallback.

## Assistant panel

Vietnamese text and push-to-talk share the same assistant request flow. Optional wake mode waits for `Hey FlatMate` without removing text input.

Voice states:

1. Idle with text input and push-to-talk.
2. First microphone press starts browser audio recording.
3. Second microphone press stops capture and uploads audio to local faster-whisper.
4. Final Vietnamese transcript appears in the request field and submits one request.
5. Optional wake mode waits for `Hey FlatMate` (`en-US`) before audio recording.
6. Processing continues with ordered observable trace cards.
7. Completed with response and simulated state change.
8. Failed with retry action and unchanged-state notice.

Controls: push-to-talk, optional wake-mode toggle, text field, send, stop capture, automatic speech toggle, and stop speech.

## Dashboard

- Environment cards: temperature, humidity, CO2, PM2.5, light, noise.
- Summary tiles: occupancy/context, window, curtain, and computer state.
- Device cards: current values and manual controls using validated backend commands.
- Historical charts: temperature, humidity, CO2, PM2.5, light, and noise for the latest 24 hours, with hourly hover details.
- Scenario terminology and controls are not shown on the end-user dashboard.

Manual commands use the same backend validation and history path as model commands.

## Responsive behavior

- Wide desktop uses available page width up to 1920 px.
- Tablet stacks the digital-twin regions and lays context options horizontally.
- Mobile uses one-column cards, full-width controls, minimum 44 px touch targets, and a wider 3D camera view.
- Assistant trace payloads wrap or scroll without causing page-level horizontal overflow.
