// Tipe respons API yang dipakai bersama oleh beberapa komponen/halaman.

// --- Alur investigasi OODA: GET /incidents/{id}/ooda ---
export type OodaPhaseKey = "observe" | "orient" | "decide" | "act";
export type OodaItemKind =
  | "alert" | "technique" | "criticality" | "attribution"
  | "decision" | "approval" | "action" | "status";

export interface OodaItem {
  ts: string | null;
  kind: OodaItemKind;
  ref: string;
  text: string;
  status: string | null;
  severity: string | null;
}

export interface OodaPhase {
  key: OodaPhaseKey;
  state: "empty" | "recorded" | "waiting";
  waiting_reason: string | null;
  items: OodaItem[];
}

export interface Ooda {
  incident_id: number;
  incident_code: string;
  incident_status: string;
  severity: string;
  criticality: string;
  current_phase: OodaPhaseKey | "closed";
  phases: OodaPhase[];
}

// --- Peta segmen (Situasi): GET /dashboard/situasi → segments[] ---
export interface SegmentHost {
  asset_id: number;
  hostname: string;
  ip: string;
  criticality: "K1" | "K2" | "K3";
  active_incidents: number;
  max_severity: string | null;
  incident_id: number | null;
}

export interface Segment {
  segment: string;
  assets: number;
  K1: number;
  K2: number;
  K3: number;
  active_incidents: number;
  max_severity: string | null;
  max_criticality: "K1" | "K2" | "K3";
  hosts: SegmentHost[];
}
