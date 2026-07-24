export type RoomContext =
  | "working"
  | "relaxing"
  | "sleeping"
  | "reading_in_bed"
  | "away";

export interface RoomSnapshot {
  version: number;
  timestamp: string;
  environment: {
    temperature_c: number;
    humidity_percent: number;
    co2_ppm: number;
    pm25_ug_m3: number;
    ambient_light_lux: number;
    noise_db: number;
  };
  occupancy: {
    room_present: boolean;
    bed_occupied: boolean;
    desk_occupied: boolean;
  };
  openings: {
    window_state: "open" | "closed";
    curtain_position_percent: number;
  };
  power: {
    computer_power_watts: number;
    smart_plugs: Record<string, { state: "on" | "off"; power_watts: number }>;
  };
  devices: {
    ac: { power: boolean; mode: string; temperature_c: number; fan_mode: string };
    fan: { power: boolean; speed: number; oscillation: boolean };
    main_light: { power: boolean; brightness_percent: number; color_temperature_kelvin: number };
    bedside_light: {
      power: boolean;
      brightness_percent: number;
      color_temperature_kelvin: number;
    };
    air_purifier: { power: boolean; speed: number };
    curtain: { position_percent: number };
    humidity_device: { power: boolean; mode: string; target_humidity_percent: number };
  };
  inferred_context: RoomContext;
  context_confidence: number;
}
