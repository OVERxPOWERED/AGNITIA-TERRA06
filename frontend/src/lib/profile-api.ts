import { api } from "@/lib/api/client";
import type { Values } from "@/lib/plant";

export interface ProfileCheck {
  clean: Values;
  errors: Record<string, string>;
  summary: {
    plant_name: string; location: string; solar_ac_mw: number; wind_mw: number; battery_mw: number; battery_mwh: number;
    demand_peak_mw: number; solar_scale: number; wind_scale: number; entered: string[]; customised: boolean;
  } | null;
}

/** Ask the API to validate a profile. Nothing is stored server-side. */
export const checkProfile = (values: Values, locationId?: string | null) =>
  api<ProfileCheck>(`/profile/check${locationId ? `?location_id=${encodeURIComponent(locationId)}` : ""}`, { method: "POST", body: JSON.stringify({ values }) });
