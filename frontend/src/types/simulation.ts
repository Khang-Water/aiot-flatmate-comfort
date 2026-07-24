import type { RoomSnapshot } from "./room";

export interface SimulationStatus {
  running: boolean;
  phase: "foundation" | "simulation";
  seed: number;
  speed: 1 | 2 | 5 | 10;
  simulated_time: string;
  active_scenario_id: string | null;
  scenario_elapsed_minutes: number;
}

export interface ScenarioSummary {
  id: string;
  name_vi: string;
  description_vi: string;
  duration_minutes: number;
}

export interface ScenarioList {
  active_scenario_id: string | null;
  scenarios: ScenarioSummary[];
}

export interface StateChangedEvent {
  changed_paths: string[];
  snapshot_version: number;
  snapshot: RoomSnapshot;
  command_id?: string;
}

export interface HistoryPoint {
  timestamp: string;
  value: number;
  unit: string;
}

export interface HistoryResponse {
  metric: string;
  points: HistoryPoint[];
}
