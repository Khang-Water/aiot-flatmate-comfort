# FlatMate Comfort — Personalized AIoT Smart Room Assistant

## 1. Project Overview

**FlatMate Comfort** is an AIoT assistant for one combined living, working, and sleeping room in a small studio apartment.

The system converts natural-language requests such as:

> “It feels uncomfortable in here.”

into numerical device settings based on:

* Current environmental conditions
* Current device settings
* User location and activity
* Window and curtain state
* Time of day
* Recent conversation
* Explicit user preferences
* Previous user corrections

The main goal is not general home automation or safety monitoring.

The goal is to learn what vague expressions such as **comfortable**, **too warm**, **stuffy**, **too bright**, **help me focus**, or **prepare the room for sleep** mean for one specific user.

---

# 2. Core Idea

FlatMate acts as a personalized translation layer:

```text
Natural-language request
+ sensor readings
+ current device settings
+ detected activity
+ conversation history
+ user preference memory
        ↓
Numerical device targets
```

Example:

```text
User:
“It feels uncomfortable.”

Context:
- User sitting at desk
- Room temperature: 29°C
- Humidity: 73%
- Window: closed
- AC target: 27°C
- Fan: off

Learned preference:
- While working, user prefers 25°C
- Fan speed 1
- Brightness 70%

Result:
- AC target → 25°C
- Fan speed → 1
- Desk light → 70%
```

The LLM does not continuously monitor sensors. It retrieves the current room state when processing a user request.

---

# 3. Project Scope

The project controls only one studio room with four functional areas:

1. Work area
2. Bed area
3. General living area
4. Window area

```text
┌───────────────────────────────────────────┐
│ Window Area                               │
│                                           │
│ Window contact sensor                     │
│ Motorized curtain                         │
│ Outdoor-light sensor                      │
│                                           │
├─────────────────────┬─────────────────────┤
│ Bed Area            │ Work Area           │
│                     │                     │
│ Bed pressure sensor │ Desk occupancy      │
│ Bedside smart light │ Computer smart plug │
│                     │ Desk smart light    │
│                     │                     │
├─────────────────────┴─────────────────────┤
│ Living Area                               │
│                                           │
│ Voice assistant                           │
│ Temperature and humidity sensor           │
│ CO₂ and PM2.5 sensors                     │
│ mmWave presence sensor                    │
│ AC · Fan · Air purifier                   │
└───────────────────────────────────────────┘
```

Excluded from the project:

* Kitchen automation
* Bathroom automation
* Smart locks
* Security cameras
* Fire or gas emergency systems
* Automatic alerts
* Mobile push notifications
* Whole-house automation

All monitoring is displayed through the web dashboard.

---

# 4. Main Workflow

```text
User speaks
    ↓
Wake-word detection
    ↓
Speech-to-text
    ↓
Conversation orchestrator
    ↓
Retrieve:
- Relevant conversation history
- Relevant preferences
- Likely activity
- Available tools
    ↓
LLM requests room state
    ↓
Sensor and device snapshot returned
    ↓
LLM translates request into numbers
    ↓
Backend validates values
    ↓
Device commands are executed
    ↓
Tool results return to LLM
    ↓
Text-to-speech response
    ↓
Later user correction becomes preference evidence
```

---

# 5. Voice Assistant

The assistant can be a stationary desktop device. A moving robot is not required.

## Hardware

* Raspberry Pi 5, mini PC, or existing laptop
* USB microphone or microphone array
* Speaker
* Optional small display
* Physical microphone mute button
* Optional LED status light

## Functions

* Detect wake word
* Capture user speech
* Convert speech to text
* Send requests to the backend
* Speak the final response
* Display current room state
* Display recent device changes
* Indicate when the microphone is active

---

# 6. Sensors

## 6.1 Temperature and Humidity

Recommended sensors:

* SHT31
* BME280

Collected values:

```json
{
  "temperature_c": 29.0,
  "humidity_percent": 73
}
```

Used for:

* AC temperature decisions
* Fan speed decisions
* Humidifier or dehumidifier decisions
* Matching current conditions with previous preferences

Example learned behavior:

> At approximately 29°C and high humidity, the user usually prefers AC at 25°C with fan speed 1.

---

## 6.2 CO₂ Sensor

Recommended sensors:

* SCD40
* SCD41

Collected value:

```json
{
  "co2_ppm": 1380
}
```

Used for requests such as:

* “The room feels stuffy.”
* “The air feels bad.”
* “Make the room fresher.”

The system can determine that lowering the AC temperature may not solve the problem.

It may recommend opening the window or increasing ventilation.

---

## 6.3 PM2.5 Sensor

Recommended sensors:

* PMS5003
* SEN55

Collected value:

```json
{
  "pm25_ug_m3": 42
}
```

Used for:

* Air purifier control
* Understanding air-quality complaints
* Separating air-quality discomfort from temperature discomfort

Example:

```text
Temperature: 26°C
Humidity: 60%
PM2.5: High

User:
“The room feels unpleasant.”

Likely action:
Increase air purifier speed instead of lowering the AC.
```

---

## 6.4 Ambient-Light Sensor

Recommended sensor:

* BH1750

Collected value:

```json
{
  "ambient_light_lux": 240
}
```

Used for:

* Smart-light brightness
* Curtain control
* Work and reading preferences
* Natural-light compensation

---

## 6.5 mmWave Presence Sensor

Recommended sensors:

* LD2410
* LD2450

Collected state:

```json
{
  "room_present": true
}
```

Used for:

* Knowing whether the room is occupied
* Detecting stationary users
* Supporting context detection
* Providing room status to the dashboard

It should not automatically turn devices on or off in the MVP.

---

## 6.6 Bed Pressure Sensor

Possible hardware:

* Pressure mat
* Force-sensitive resistor mat
* Load cells under the bed legs

Collected state:

```json
{
  "bed_occupied": true,
  "occupied_duration_minutes": 25
}
```

Used for:

* Detecting sleep or relaxation context
* Loading bedtime preferences
* Understanding requests made while the user is in bed
* Distinguishing desk use from bed use

Example:

```text
User:
“Make it more comfortable.”

Context:
- Bed occupied
- Time: 23:30
- Desk empty

Interpretation:
Apply sleep-related preferences.
```

---

## 6.7 Desk or Chair Occupancy Sensor

Possible hardware:

* Pressure pad
* Load cell
* LD2450 zone detection

Collected state:

```json
{
  "desk_occupied": true
}
```

Used for:

* Detecting work context
* Loading work-related preferences
* Understanding phrases such as:

  * “Help me focus.”
  * “Make the room better for working.”
  * “The lighting is not good.”

---

## 6.8 Window Contact Sensor

Possible hardware:

* Magnetic reed switch
* Zigbee window sensor
* ESP32 contact sensor

Collected state:

```json
{
  "window_state": "open"
}
```

Used for:

* Understanding ventilation options
* Avoiding inefficient AC decisions
* Explaining why cooling may be ineffective
* Learning whether the user prefers natural ventilation

Example:

```text
User:
“It is too warm.”

Context:
- Window open
- AC off
- Outdoor temperature lower than indoor temperature

Possible action:
Recommend keeping the window open and starting the fan.
```

---

## 6.9 Curtain Position Sensor

Collected state:

```json
{
  "curtain_position_percent": 40
}
```

Position meaning:

* `0%` = fully closed
* `100%` = fully open

Used for:

* Natural-light control
* Heat reduction
* Privacy preferences
* Sleep and work scenes

---

## 6.10 Noise-Level Sensor

Use a microphone-based sound-level module that reports only sound intensity.

Collected value:

```json
{
  "noise_db": 42
}
```

Used for:

* Learning fan-noise preferences
* Selecting quieter device settings
* Understanding requests such as:

  * “Make the room quieter.”
  * “Keep it cool without making noise.”

Audio recording is not required for noise monitoring.

---

## 6.11 Smart-Plug Power Monitoring

Possible devices:

* Wi-Fi smart plug
* Zigbee smart plug
* ESP32 energy-monitoring relay

Collected state:

```json
{
  "device": "desk_computer",
  "power_watts": 145,
  "state": "on"
}
```

Used for:

* Supporting work-context detection
* Showing power consumption in the dashboard
* Confirming device state
* Determining whether the computer or monitor is active

---

# 7. Controlled Devices

## 7.1 Air Conditioner

Control through:

* IR blaster
* Home Assistant integration
* Manufacturer API

Variables:

```json
{
  "power": true,
  "mode": "cool",
  "temperature_c": 25,
  "fan_mode": "auto"
}
```

Allowed range:

```text
18–30°C
```

---

## 7.2 Fan

Control through:

* IR blaster
* Smart fan controller
* Smart plug for simple on/off control

Variables:

```json
{
  "power": true,
  "speed": 1,
  "oscillation": true
}
```

Allowed speed:

```text
0–3
```

Where:

* `0` = off
* `1` = low
* `2` = medium
* `3` = high

---

## 7.3 Main Smart Light

Variables:

```json
{
  "power": true,
  "brightness_percent": 65,
  "color_temperature_kelvin": 4000
}
```

Used for:

* General room lighting
* Work lighting
* Relaxation scenes

Allowed ranges:

```text
Brightness: 0–100%
Color temperature: 2700–6500 K
```

---

## 7.4 Bedside Smart Light

Variables:

```json
{
  "power": true,
  "brightness_percent": 15,
  "color_temperature_kelvin": 3000
}
```

Used for:

* Reading in bed
* Sleep preparation
* Low-light nighttime interaction

---

## 7.5 Air Purifier

Variables:

```json
{
  "power": true,
  "speed": 2
}
```

Allowed speed:

```text
0–3
```

Used for:

* High PM2.5
* User complaints about dirty air
* Learned air-quality preferences

---

## 7.6 Motorized Curtain

Variables:

```json
{
  "position_percent": 35
}
```

Used for:

* Reducing sunlight
* Reducing room heat
* Improving privacy
* Supporting work, relaxation, and sleep contexts

---

## 7.7 Humidifier or Dehumidifier

Optional device.

Variables:

```json
{
  "power": true,
  "target_humidity_percent": 55
}
```

Used for requests such as:

* “The air feels dry.”
* “It feels sticky.”
* “Reduce the humidity.”

---

## 7.8 Smart Plugs

Possible connected devices:

* Desk computer
* Monitor
* Fan
* Humidifier
* Bedside lamp

Smart plugs provide:

* On/off control
* Current state
* Power usage

Only devices safe for remote switching should be connected.

---

# 8. Recommended Hardware Sets

## 8.1 Core MVP

### Sensors

* Temperature and humidity
* Ambient light
* mmWave presence
* Window contact
* Bed pressure
* Desk occupancy

### Devices

* Air conditioner through IR
* Fan through IR or smart plug
* Main smart light
* Bedside smart light
* Motorized curtain

This version supports:

* Natural-language comfort control
* Sleep and work context
* Preference learning
* Window-aware cooling
* Lighting and curtain control

---

## 8.2 Expanded Version

Add:

### Sensors

* CO₂
* PM2.5
* Noise level
* Smart-plug power monitoring

### Devices

* Air purifier
* Humidifier or dehumidifier
* Computer smart plug

---

# 9. Room State Object

The backend combines sensors and device values into a single snapshot.

```json
{
  "timestamp": "2026-07-22T23:20:00+07:00",
  "environment": {
    "temperature_c": 28.4,
    "humidity_percent": 72,
    "co2_ppm": 1150,
    "pm25_ug_m3": 12,
    "ambient_light_lux": 80,
    "noise_db": 37
  },
  "occupancy": {
    "room_present": true,
    "bed_occupied": true,
    "desk_occupied": false
  },
  "openings": {
    "window_state": "closed",
    "curtain_position_percent": 20
  },
  "power": {
    "computer_power_watts": 0
  },
  "devices": {
    "ac_power": true,
    "ac_temperature_c": 26,
    "fan_speed": 0,
    "main_light_brightness_percent": 20,
    "bedside_light_brightness_percent": 10,
    "air_purifier_speed": 0
  },
  "inferred_context": "sleeping"
}
```

The LLM retrieves this only when needed.

---

# 10. Context Detection

Use deterministic context detection before the LLM request.

## Working

```text
Desk occupied
+ computer power active
+ bed unoccupied
        ↓
Likely context: working
```

## Sleeping

```text
Bed occupied
+ late evening
+ desk unoccupied
        ↓
Likely context: sleeping
```

## Reading in Bed

```text
Bed occupied
+ bedside light active
+ user says they are reading
        ↓
Context: reading_in_bed
```

## Relaxing

```text
Room occupied
+ bed unoccupied
+ desk unoccupied
        ↓
Likely context: relaxing
```

The user can correct the inferred context.

Example:

> “I’m reading, not going to sleep.”

This temporarily changes the active context to:

```json
{
  "context": "reading_in_bed"
}
```

---

# 11. LLM Context Strategy

Do not send all raw sensor history with every request.

Always provide:

* Current user request
* Current inferred activity
* Current time period
* Relevant recent conversation
* Relevant preference summary
* Available tool definitions

Retrieve through tools:

* Current room state
* Current device values
* Window and curtain state
* Recent actions
* Relevant historical preferences
* Specific sensor history when necessary

Recommended flow:

```text
Small initial context
        ↓
LLM determines missing information
        ↓
LLM calls get_room_snapshot()
        ↓
Backend returns current values
        ↓
LLM creates numerical targets
```

---

# 12. How the LLM Knows Available Tools

The backend includes structured tool definitions in each LLM request.

Example:

```json
{
  "type": "function",
  "function": {
    "name": "get_room_snapshot",
    "description": "Get the current environmental, occupancy, window and device state for the studio room.",
    "parameters": {
      "type": "object",
      "properties": {}
    }
  }
}
```

The LLM sees:

* Tool name
* Tool description
* Required parameters
* Allowed parameter values

The LLM does not receive:

* MQTT credentials
* Database passwords
* Device credentials
* Python implementations

---

# 13. Available Tools

## 13.1 Sensor and State Tools

```text
get_room_snapshot()
get_environment_state()
get_occupancy_context()
get_window_and_curtain_state()
get_device_state(device)
get_recent_actions(limit)
```

---

## 13.2 Preference Tools

```text
get_relevant_preferences(context)
save_explicit_preference(...)
record_preference_feedback(...)
delete_preference(preference_id)
confirm_preference(preference_id)
```

---

## 13.3 Device Tools

```text
set_ac(power, mode, temperature_c)
set_fan(power, speed, oscillation)
set_main_light(power, brightness_percent, color_temperature_kelvin)
set_bedside_light(power, brightness_percent, color_temperature_kelvin)
set_air_purifier(power, speed)
set_curtain(position_percent)
set_humidity_device(power, target_humidity_percent)
set_smart_plug(device, state)
```

---

# 14. High-Level Room Control Tool

Use one combined tool for multi-device requests.

```json
{
  "name": "set_room_scene",
  "description": "Apply numerical comfort settings to the studio room.",
  "parameters": {
    "type": "object",
    "properties": {
      "ac_temperature_c": {
        "type": "number",
        "minimum": 18,
        "maximum": 30
      },
      "fan_speed": {
        "type": "integer",
        "minimum": 0,
        "maximum": 3
      },
      "main_light_brightness_percent": {
        "type": "integer",
        "minimum": 0,
        "maximum": 100
      },
      "main_light_color_temperature_kelvin": {
        "type": "integer",
        "minimum": 2700,
        "maximum": 6500
      },
      "bedside_light_brightness_percent": {
        "type": "integer",
        "minimum": 0,
        "maximum": 100
      },
      "bedside_light_color_temperature_kelvin": {
        "type": "integer",
        "minimum": 2700,
        "maximum": 6500
      },
      "air_purifier_speed": {
        "type": "integer",
        "minimum": 0,
        "maximum": 3
      },
      "curtain_position_percent": {
        "type": "integer",
        "minimum": 0,
        "maximum": 100
      },
      "target_humidity_percent": {
        "type": "integer",
        "minimum": 35,
        "maximum": 70
      },
      "reason": {
        "type": "string"
      }
    }
  }
}
```

Fields that are not included remain unchanged.

This directly implements:

```text
Natural request → numerical room settings
```

---

# 15. Tool Registry

The backend maps tool names to real functions.

```python
TOOL_REGISTRY = {
    "get_room_snapshot": get_room_snapshot,
    "get_relevant_preferences": get_relevant_preferences,
    "get_recent_actions": get_recent_actions,
    "set_room_scene": set_room_scene,
    "set_ac": set_ac,
    "set_fan": set_fan,
    "set_main_light": set_main_light,
    "set_bedside_light": set_bedside_light,
    "set_air_purifier": set_air_purifier,
    "set_curtain": set_curtain,
    "record_preference_feedback": record_preference_feedback,
}
```

Tool execution flow:

```text
LLM requests tool
        ↓
Backend parses arguments
        ↓
Validate values
        ↓
Execute MQTT or device command
        ↓
Wait for device-state confirmation
        ↓
Return result to LLM
```

---

# 16. Preference Memory

Preferences should depend on context.

Do not store only one global preferred temperature.

A preference may depend on:

* Activity
* Time of day
* Temperature range
* Humidity range
* Bed or desk occupancy
* Window state
* Current device settings
* User wording

Example:

```json
{
  "user_id": "user_01",
  "context": "sleeping",
  "environment": {
    "temperature_range_c": [27, 30],
    "humidity_range_percent": [65, 80],
    "window_state": "closed"
  },
  "occupancy": {
    "bed_occupied": true,
    "desk_occupied": false
  },
  "requested_intent": "comfortable",
  "preferred_result": {
    "ac_temperature_c": 25,
    "fan_speed": 1,
    "main_light_brightness_percent": 0,
    "bedside_light_brightness_percent": 5,
    "air_purifier_speed": 1,
    "curtain_position_percent": 0
  },
  "source": "learned",
  "confidence": 0.81,
  "observation_count": 5
}
```

---

# 17. Types of Preference Memory

## 17.1 Explicit Preference

The user directly states the preference.

Example:

> “When I work, keep the main light around 70 percent.”

Store immediately:

```json
{
  "context": "working",
  "main_light_brightness_percent": 70,
  "source": "explicit",
  "confidence": 1.0
}
```

Explicit preferences have higher priority than inferred preferences.

---

## 17.2 Learned Preference

The system learns from corrections.

Example:

```text
System sets:
AC 26°C
Fan off

User:
“Make it colder and turn on the fan.”

New setting:
AC 25°C
Fan speed 1
```

Store:

```json
{
  "context": "working",
  "preferred_ac_temperature_c": 25,
  "preferred_fan_speed": 1,
  "source": "user_correction",
  "confidence": 0.5,
  "observation_count": 1
}
```

Confidence increases when similar corrections happen again.

---

## 17.3 Temporary Preference

Example:

> “Tonight, keep the fan off.”

Store with expiration:

```json
{
  "context": "sleeping",
  "fan_speed": 0,
  "source": "temporary",
  "expires_at": "2026-07-23T08:00:00+07:00"
}
```

---

# 18. Preference-Learning Workflow

After applying a device change, the backend opens a short correction window.

```text
System applies settings
        ↓
Store request, context and action
        ↓
Wait for next related user command
        ↓
User accepts settings
        ├── No correction → weak positive evidence
        └── Correction → save corrected values
```

Example correction record:

```json
{
  "initial_request": "It feels uncomfortable.",
  "initial_action": {
    "ac_temperature_c": 26,
    "fan_speed": 0
  },
  "follow_up_request": "Reduce it more and turn on the fan.",
  "corrected_action": {
    "ac_temperature_c": 25,
    "fan_speed": 1
  },
  "context": {
    "activity": "working",
    "temperature_c": 29,
    "humidity_percent": 73,
    "desk_occupied": true,
    "window_state": "closed",
    "time_period": "evening"
  }
}
```

---

# 19. Detailed Conversation Example

## First Interaction

User:

> “It feels uncomfortable in here.”

Initial context:

```json
{
  "current_activity": "working",
  "desk_occupied": true,
  "local_time": "20:10"
}
```

The LLM calls:

```json
{
  "name": "get_room_snapshot",
  "arguments": {}
}
```

Tool result:

```json
{
  "temperature_c": 29,
  "humidity_percent": 73,
  "co2_ppm": 980,
  "pm25_ug_m3": 10,
  "ambient_light_lux": 350,
  "window_state": "closed",
  "ac_temperature_c": 27,
  "fan_speed": 0,
  "main_light_brightness_percent": 60
}
```

The LLM retrieves relevant preferences:

```json
{
  "context": "working",
  "preferred_ac_temperature_c": 26,
  "preferred_fan_speed": 0,
  "preferred_light_brightness_percent": 65,
  "confidence": 0.3
}
```

The LLM calls:

```json
{
  "name": "set_room_scene",
  "arguments": {
    "ac_temperature_c": 26,
    "fan_speed": 0,
    "main_light_brightness_percent": 65,
    "main_light_color_temperature_kelvin": 4000,
    "reason": "The room is warmer and more humid than the user's current work preference."
  }
}
```

Assistant response:

> “I lowered the AC to 26 degrees.”

---

## Follow-Up Correction

User:

> “Reduce it more and turn on the fan.”

The LLM understands:

* “It” refers to the AC target temperature.
* “Reduce it more” means lower the current target.
* “Turn on the fan” means fan speed must become greater than zero.

Tool call:

```json
{
  "name": "set_room_scene",
  "arguments": {
    "ac_temperature_c": 25,
    "fan_speed": 1,
    "reason": "The user corrected the previous comfort settings."
  }
}
```

Assistant response:

> “The AC is now at 25 degrees, and the fan is on low.”

The backend stores the correction as preference evidence.

---

## Similar Interaction Later

Several days later:

```json
{
  "activity": "working",
  "temperature_c": 28.7,
  "humidity_percent": 71,
  "desk_occupied": true,
  "window_state": "closed",
  "current_ac_temperature_c": 27,
  "current_fan_speed": 0
}
```

User:

> “It feels uncomfortable again.”

The system retrieves the previous preference and applies:

```json
{
  "ac_temperature_c": 25,
  "fan_speed": 1,
  "main_light_brightness_percent": 65,
  "main_light_color_temperature_kelvin": 4000
}
```

Assistant response:

> “I applied your usual work comfort setting: 25 degrees with the fan on low.”

---

# 20. Bed-Aware Example

Current state:

```json
{
  "temperature_c": 28.5,
  "humidity_percent": 74,
  "bed_occupied": true,
  "desk_occupied": false,
  "window_state": "closed",
  "local_time": "23:40",
  "ac_temperature_c": 27,
  "fan_speed": 0,
  "bedside_light_brightness_percent": 25
}
```

User:

> “Make me comfortable.”

The system loads sleeping preferences and applies:

```json
{
  "ac_temperature_c": 25,
  "fan_speed": 1,
  "main_light_brightness_percent": 0,
  "bedside_light_brightness_percent": 5,
  "bedside_light_color_temperature_kelvin": 2800,
  "curtain_position_percent": 0
}
```

Assistant response:

> “I applied your usual bedtime comfort settings.”

---

# 21. Work Context Example

Current state:

```json
{
  "desk_occupied": true,
  "computer_power_watts": 140,
  "bed_occupied": false,
  "ambient_light_lux": 180,
  "temperature_c": 29
}
```

User:

> “Help me focus.”

Possible settings:

```json
{
  "ac_temperature_c": 25,
  "fan_speed": 1,
  "main_light_brightness_percent": 75,
  "main_light_color_temperature_kelvin": 4800,
  "bedside_light_brightness_percent": 0,
  "curtain_position_percent": 60
}
```

---

# 22. Reading-in-Bed Example

User:

> “I want to read for a while.”

Context:

```json
{
  "bed_occupied": true,
  "desk_occupied": false,
  "local_time": "22:30"
}
```

Possible settings:

```json
{
  "ac_temperature_c": 26,
  "fan_speed": 0,
  "main_light_brightness_percent": 0,
  "bedside_light_brightness_percent": 45,
  "bedside_light_color_temperature_kelvin": 3200,
  "curtain_position_percent": 0
}
```

The context becomes `reading_in_bed` instead of `sleeping`.

---

# 23. Window-Aware Example

User:

> “It is too hot.”

Current state:

```json
{
  "indoor_temperature_c": 30,
  "outdoor_temperature_c": 26,
  "window_state": "open",
  "ac_power": false,
  "fan_speed": 0
}
```

Possible action:

```json
{
  "fan_speed": 1,
  "curtain_position_percent": 40
}
```

Assistant response:

> “The window is already open and the outdoor air is cooler, so I turned the fan on low and partly closed the curtain.”

---

# 24. Stuffy-Room Example

User:

> “The air feels stuffy.”

Current state:

```json
{
  "co2_ppm": 1450,
  "pm25_ug_m3": 8,
  "window_state": "closed"
}
```

Assistant response:

> “CO₂ is high while the window is closed. Opening the window would help more than lowering the AC.”

The system should not claim that AC cooling removes CO₂.

---

# 25. Strong-Sunlight Example

User:

> “It is too bright and warm.”

Current state:

```json
{
  "ambient_light_lux": 2200,
  "curtain_position_percent": 100,
  "temperature_c": 29
}
```

Possible settings:

```json
{
  "curtain_position_percent": 35,
  "ac_temperature_c": 26,
  "main_light_brightness_percent": 0
}
```

---

# 26. Quiet-Comfort Example

User:

> “Keep it cool, but make the room quieter.”

Current state:

```json
{
  "ac_temperature_c": 25,
  "fan_speed": 3,
  "air_purifier_speed": 2,
  "noise_db": 50
}
```

Possible settings:

```json
{
  "ac_temperature_c": 24,
  "fan_speed": 1,
  "air_purifier_speed": 1
}
```

The system compensates for reduced fan airflow by slightly lowering the AC target.

---

# 27. Relative Request Handling

| User request                | Current state      | Result                       |
| --------------------------- | ------------------ | ---------------------------- |
| “Make it colder”            | AC 26°C            | AC 25°C                      |
| “A little warmer”           | AC 24°C            | AC 25°C                      |
| “Turn the fan up”           | Fan 1              | Fan 2                        |
| “Make it less bright”       | Light 70%          | Light 55%                    |
| “Make it warmer and darker” | AC 24°C, light 70% | AC 25°C, light 50%           |
| “Open the curtains a bit”   | Curtain 30%        | Curtain 45%                  |
| “Make the air cleaner”      | Purifier 0         | Purifier 1 or 2              |
| “Use my usual work setting” | Any                | Load learned work preference |

Recommended default steps:

```json
{
  "temperature_small_step_c": 1,
  "fan_small_step": 1,
  "brightness_small_step_percent": 15,
  "curtain_small_step_percent": 15,
  "purifier_small_step": 1,
  "color_temperature_small_step_kelvin": 500
}
```

---

# 28. Validation Rules

The LLM proposes values. The backend validates them.

```text
AC temperature: 18–30°C
Fan speed: 0–3
Light brightness: 0–100%
Light color temperature: 2700–6500 K
Curtain position: 0–100%
Air purifier speed: 0–3
Target humidity: 35–70%
```

Additional rules:

* Vague AC requests can change the target by at most 2°C.
* Vague fan requests can change speed by at most one level.
* Vague light requests can change brightness by at most 20%.
* Explicit numerical commands may use the exact requested value.
* Unspecified devices remain unchanged.
* Explicit preferences override learned preferences.
* Recent repeated corrections receive more weight.
* The user can inspect, edit, confirm, or delete all stored preferences.
* Do not learn from unrelated follow-up conversations.
* Do not treat absence of correction as strong approval.

---

# 29. Dashboard

The dashboard is for monitoring, manual control, and preference management.

It does not send automatic alerts.

## 29.1 Current Environment

Display:

* Temperature
* Humidity
* CO₂
* PM2.5
* Ambient light
* Noise level

## 29.2 Current Context

Display:

* Room presence
* Bed occupancy
* Desk occupancy
* Window state
* Curtain position
* Computer power
* Inferred activity
* Context confidence

## 29.3 Device State

Display:

* AC mode and target temperature
* Fan speed
* Main light settings
* Bedside light settings
* Air purifier speed
* Curtain position
* Humidifier or dehumidifier state
* Smart-plug state and power usage

## 29.4 Conversation History

Display:

* User transcript
* Inferred intent
* Retrieved preference
* Tool calls
* Device values before and after
* Assistant response

## 29.5 Learned Preferences

Example:

| Context        |   AC | Fan | Main light | Bedside light | Curtain | Purifier | Confidence |
| -------------- | ---: | --: | ---------: | ------------: | ------: | -------: | ---------: |
| Working        | 25°C |   1 |        75% |            0% |     60% |        1 |        82% |
| Relaxing       | 26°C |   0 |        40% |           20% |     50% |        0 |        65% |
| Sleeping       | 25°C |   1 |         0% |            5% |      0% |        1 |        81% |
| Reading in bed | 26°C |   0 |         0% |           45% |      0% |        0 |        58% |

The user can:

* Edit a preference
* Confirm a learned preference
* Delete a preference
* Correct the inferred context
* Reset all learned preferences

## 29.6 Historical Charts

Display:

* Temperature
* Humidity
* CO₂
* PM2.5
* Ambient light
* Noise level
* AC target temperature
* Fan speed
* Light brightness
* Curtain position
* Air purifier speed

---

# 30. Software Architecture

```text
Sensors and smart devices
          ↓
        ESP32
          ↓
         MQTT
          ↓
    Room State Service
          ↓
  Redis and PostgreSQL
          ↑
          │
User voice → Wake word → ASR
          ↓
 Conversation Orchestrator
          ↓
   Context Detection
          ↓
 Preference Retrieval
          ↓
          LLM
          ↓
 Structured Tool Calls
          ↓
    Value Validation
          ↓
     Device Service
          ↓
         MQTT
          ↓
    Physical Devices
          ↓
    Execution Results
          ↓
          LLM
          ↓
          TTS
```

The web dashboard reads from the same room-state and historical database.

---

# 31. Backend Components

## Room State Service

Stores:

* Latest sensor values
* Latest device states
* Window and curtain state
* Occupancy state
* Current activity context

## Conversation Orchestrator

Handles:

* ASR transcript
* Recent conversation
* Tool definitions
* Preference retrieval
* LLM tool-call loop
* Final assistant response
* TTS request

## Context Service

Handles:

* Bed and desk occupancy
* Time of day
* Computer activity
* User corrections
* Current activity inference

## Preference Service

Handles:

* Explicit preferences
* Learned preferences
* Temporary preferences
* Correction events
* Confidence scores
* Context matching
* Preference deletion and confirmation

## Device Service

Handles:

* MQTT commands
* Allowed ranges
* Device availability
* Device-state confirmation
* Command timeout
* Manual override

---

# 32. Data Storage

## Redis

Store current state:

```text
Latest sensor values
Current device values
Current room presence
Bed and desk occupancy
Window state
Curtain position
Current inferred context
Recent device action
```

## PostgreSQL

Store:

```text
Sensor history
Device actions
Conversation records
Preference records
Correction events
Context history
Tool-call logs
```

Standard PostgreSQL is enough for the MVP.

---

# 33. MQTT Topic Design

```text
flat/studio/sensor/temperature
flat/studio/sensor/humidity
flat/studio/sensor/co2
flat/studio/sensor/pm25
flat/studio/sensor/light
flat/studio/sensor/noise
flat/studio/sensor/presence
flat/studio/sensor/bed_pressure
flat/studio/sensor/desk_occupancy
flat/studio/sensor/window
flat/studio/sensor/computer_power

flat/studio/device/ac/state
flat/studio/device/ac/command
flat/studio/device/fan/state
flat/studio/device/fan/command
flat/studio/device/main_light/state
flat/studio/device/main_light/command
flat/studio/device/bedside_light/state
flat/studio/device/bedside_light/command
flat/studio/device/curtain/state
flat/studio/device/curtain/command
flat/studio/device/air_purifier/state
flat/studio/device/air_purifier/command
flat/studio/device/humidity_control/state
flat/studio/device/humidity_control/command
```

Example sensor payload:

```json
{
  "device_id": "studio-environment-node-01",
  "value": 29.1,
  "unit": "celsius",
  "timestamp": "2026-07-22T20:10:00+07:00"
}
```

---

# 34. Recommended Technology

* **Sensor controller:** ESP32-S3
* **Messaging:** Mosquitto MQTT
* **Backend:** FastAPI
* **Current state:** Redis
* **Database:** PostgreSQL
* **Dashboard:** Next.js
* **ASR:** Whisper
* **TTS:** Piper
* **Wake word:** OpenWakeWord
* **LLM:** Local or cloud model with structured tool calling
* **Device integration:** Home Assistant or custom MQTT bridge

---

# 35. MVP Scenarios

Implement these scenarios first.

## Scenario 1: Vague Comfort Request

> “It feels uncomfortable.”

The system retrieves sensor state and learned preferences, then applies numerical settings.

## Scenario 2: Correction and Learning

> “Reduce it more and turn on the fan.”

The system changes the current values and records the correction.

## Scenario 3: Bed-Aware Preference

> “Make me comfortable.”

The bed pressure sensor indicates that the user is in bed, so the system loads sleep preferences.

## Scenario 4: Work-Aware Preference

> “Help me focus.”

Desk occupancy and computer power indicate working context.

## Scenario 5: Window-Aware Cooling

> “It is too hot.”

The system checks the window state before selecting AC, fan, and curtain settings.

## Scenario 6: Multi-Device Request

> “Make it cooler, darker, and quieter.”

The system generates numerical settings for the AC, fan, lighting, curtain, and purifier.

## Scenario 7: Reading in Bed

> “I want to read for a while.”

The system selects the bedside light and avoids activating the main light.

## Scenario 8: Learned Scene Reuse

> “Use my usual bedtime settings.”

The system retrieves and applies the learned sleep preference.

## Scenario 9: Explicit Preference

> “From now on, while I work, keep the light around 70 percent.”

The system stores an explicit preference.

---

# 36. Development Phases

## Phase 1: Basic Sensors and Devices

* Connect temperature and humidity sensor
* Connect light sensor
* Connect bed pressure sensor
* Connect desk occupancy sensor
* Connect window sensor
* Publish data through MQTT
* Control AC, fan, and smart lights
* Confirm device states

## Phase 2: Room-State Service

* Store latest sensor values
* Store current device values
* Create `get_room_snapshot()`
* Add Redis
* Store history in PostgreSQL

## Phase 3: Dashboard

* Display current room state
* Display occupancy and context
* Display device values
* Add manual device controls
* Add historical charts

## Phase 4: Voice Pipeline

* Add wake-word detection
* Add ASR
* Add TTS
* Connect the voice device to the backend

## Phase 5: LLM Tool Calling

* Define read tools
* Define control tools
* Add tool registry
* Implement the tool-calling loop
* Validate numerical values
* Execute MQTT commands

## Phase 6: Context Detection

* Detect working context
* Detect sleeping context
* Detect reading-in-bed context
* Detect relaxing context
* Allow user correction

## Phase 7: Preference Memory

* Store explicit preferences
* Store interaction records
* Detect follow-up corrections
* Create learned preferences
* Calculate confidence
* Retrieve context-matched preferences
* Add preference controls to the dashboard

## Phase 8: Expanded Devices

* Add CO₂ sensor
* Add PM2.5 sensor
* Add air purifier
* Add motorized curtain
* Add noise-level sensor
* Add humidifier or dehumidifier

## Phase 9: Evaluation

Test:

* Natural-language intent understanding
* Relative requests
* Pronoun resolution such as “it”
* Multi-device commands
* Context detection
* Preference retrieval
* Preference updates after correction
* Device offline behavior
* Missing sensor values
* Invalid numerical tool arguments
* Window-aware decisions
* User preference deletion
* Manual dashboard override

---

# 37. Evaluation Metrics

## Intent Accuracy

Percentage of user requests interpreted correctly.

## Tool Selection Accuracy

Percentage of requests that use the correct read and control tools.

## Device Value Accuracy

Difference between the generated numerical values and the user-approved settings.

## Correction Rate

How often the user must correct the first system action.

The correction rate should decrease as the system learns.

## Preference Retrieval Accuracy

Percentage of requests that retrieve the correct context-specific preference.

## Context Detection Accuracy

Accuracy of working, relaxing, sleeping, and reading-in-bed detection.

## Tool Execution Success

Percentage of tool calls successfully confirmed by the physical device.

---

# 38. Final Architecture

```text
Environmental sensors
Context sensors
Current device states
        ↓
 Room State Service
        ↓
User voice → ASR
        ↓
Conversation context
        ↓
Context detection
        ↓
Preference retrieval
        ↓
       LLM
        ↓
Natural request translated into numbers
        ↓
Backend validation
        ↓
AC · Fan · Lights · Curtain
Air purifier · Humidity control
        ↓
Execution confirmation
        ↓
LLM response
        ↓
       TTS
        ↓
Later correction becomes preference evidence
```

---

# 39. Core Design Principle

FlatMate Comfort should not attempt to replace all home automation with an LLM.

The components have separate responsibilities:

```text
ESP32:
Read sensors and control physical devices.

Room State Service:
Maintain current sensor and device values.

Context Service:
Determine whether the user is working, relaxing, reading, or sleeping.

LLM:
Understand vague natural-language requests and translate them into numerical targets.

Preference Service:
Learn from explicit instructions and user corrections.

Device Service:
Validate and execute device commands.

Dashboard:
Display sensor data, device states, interactions, and learned preferences.
```

The defining feature is:

```text
User language
+ current environment
+ physical context
+ learned personal preference
        ↓
Personalized numerical room settings
```
