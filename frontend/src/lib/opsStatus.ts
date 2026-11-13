// Status operasional ringkas untuk command bar & sidebar (postur, hitungan antrian,
// kesehatan API). Satu sumber bersama (singleton) + polling 60 detik — tanpa
// animasi/kedipan; perubahan tampil sebagai angka & label (PRD C.1 no.4).
import { computed, ref } from "vue";
import { apiFetch } from "@/lib/api";

export type Posture = "critical" | "elevated" | "guarded" | "normal";

interface SituasiLite {
  generated_at: string;
  posture: Posture;
  active_incidents: number;
  pending_approvals: number;
  open_alerts: number;
}

const POLL_MS = 60_000;

const snapshot = ref<SituasiLite | null>(null);
const apiOk = ref<boolean | null>(null);
const apiVersion = ref<string | null>(null);
const lastSync = ref<Date | null>(null);
let timer: number | undefined;
let users = 0;

async function refresh(): Promise<void> {
  try {
    const h = await apiFetch<{ status: string; version: string }>("/health", { auth: false });
    apiOk.value = h.status === "ok";
    apiVersion.value = h.version;
  } catch {
    apiOk.value = false;
  }
  try {
    snapshot.value = await apiFetch<SituasiLite>("/dashboard/situasi");
    lastSync.value = new Date();
  } catch {
    // Biarkan snapshot lama; command bar menampilkan waktu sinkron terakhir.
  }
}

export const POSTURE_META: Record<Posture, { label: string; tone: "ok" | "warn" | "danger" | "muted" }> = {
  critical: { label: "KRITIS", tone: "danger" },
  elevated: { label: "WASPADA", tone: "warn" },
  guarded: { label: "SIAGA", tone: "warn" },
  normal: { label: "NORMAL", tone: "ok" },
};

export function useOpsStatus() {
  return {
    snapshot,
    apiOk,
    apiVersion,
    lastSync,
    refresh,
    posture: computed(() => (snapshot.value ? POSTURE_META[snapshot.value.posture] : null)),
    /** Mulai polling (dipanggil komponen layout saat mount). Aman dipanggil berkali-kali. */
    start() {
      users += 1;
      if (users === 1) {
        refresh();
        timer = window.setInterval(refresh, POLL_MS);
      }
    },
    stop() {
      users = Math.max(0, users - 1);
      if (users === 0 && timer) {
        clearInterval(timer);
        timer = undefined;
      }
    },
  };
}
