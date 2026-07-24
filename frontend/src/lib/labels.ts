import type { RoomSnapshot } from "@/types/room";

export const contextLabels: Record<RoomSnapshot["inferred_context"], string> = {
  working: "Bàn làm việc",
  relaxing: "Phòng khách",
  sleeping: "Phòng ngủ · đang ngủ",
  reading_in_bed: "Phòng ngủ · đọc sách",
  away: "Ngoài căn hộ",
};

export function booleanLabel(value: boolean): string {
  return value ? "Bật" : "Tắt";
}
