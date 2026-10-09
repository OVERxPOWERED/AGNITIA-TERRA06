import { api } from "@/lib/api/client";
import type { PlantSummary } from "@/lib/api/types";
import type { Values } from "@/lib/plant";

export interface ProfileCheck {
  clean: Values;
  errors: Record<string, string>;
  summary: PlantSummary | null;
}

/** Ask the API to validate a profile. Nothing is stored server-side. */
export const checkProfile = (values: Values, locationId?: string | null) =>
  api<ProfileCheck>(`/profile/check${locationId ? `?location_id=${encodeURIComponent(locationId)}` : ""}`, { method: "POST", body: JSON.stringify({ values }) });
