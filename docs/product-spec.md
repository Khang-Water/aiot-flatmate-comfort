# Product specification

## Goal

Demonstrate how a personalized AI assistant translates vague Vietnamese comfort requests into numerical settings for a simulated studio apartment.

Success means a presenter can:

1. Select or watch a simulated apartment situation.
2. Enter a Vietnamese request or speak it with push-to-talk in a supported browser.
3. See transcript, context, room snapshot, preference retrieval, model tool request, validation, state changes, and final response.
4. See the resident, apartment, devices, dashboard, charts, and history update together.
5. Correct an assistant-set device value manually and see repeated matching overrides become learned preference memory.

## User and environment

- One local user and one fixed studio apartment.
- Vietnamese UI, command recognition, and assistant replies.
- Optional English wake phrase: `Hey FlatMate`; push-to-talk remains the reliable voice entry point.
- Chrome or Edge on localhost or HTTPS deployment is primary browser target.
- Text input remains available when microphone permission, speech recognition, or continuous wake recognition fails.

## Apartment zones

- Work: desk, chair, computer, desk light, and occupancy indicator.
- Bed: bed, bedside light, and pressure/occupancy indicator.
- Living: resident idle area, main light, AC, fan, purifier, and humidity device.
- Window: window contact, curtain, and outdoor-light influence.
- Kitchen and bathroom: visual context only, without simulated automation.

## Simulated sensors

- Temperature, humidity, CO2, PM2.5, ambient light, and noise.
- Room presence, bed occupancy, and desk occupancy.
- Window state and curtain position.
- Computer and smart-plug power.

## Simulated devices

- AC, fan, main light, bedside light, purifier, motorized curtain, and controllable window.
- Humidifier/dehumidifier, computer, monitor, and safe smart plugs.

All commands change simulation state only.

## Primary screens

- Digital twin (`/`): responsive 3D apartment, context selector, sensor/device overlays, assistant request, and live pipeline trace.
- Dashboard (`/dashboard`): current metrics, common device controls, implicit-feedback capture from qualifying overrides, and hourly-hover charts limited to the latest 24 hours.
- Conversation history (`/history`): recent text/voice requests, final responses, status, and failures. Detailed tool history remains a Phase 7 enhancement.

## Visible assistant trace

Show observable system events, never private model chain-of-thought:

Current text flow:

`request received -> occupancy/context observed -> snapshot read -> preference lookup -> model request -> tool requested -> validation -> state applied -> assistant response`

Phase 5 adds:

`microphone active -> wake detected (optional) -> local ASR or browser SpeechRecognition -> current text flow -> backend Vietnamese TTS`

Each event includes status, timestamp, duration when known, safe input/output data, and concise model-provided rationale.

## Exclusions

- Real sensors or devices, moving robot, room editor, multi-user accounts.
- Security, cameras, emergency systems, alerts, mobile push notifications.
- Offline rule-based substitute for AI decisions.
- Photorealistic purchased assets in first version.
