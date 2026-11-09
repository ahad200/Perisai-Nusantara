<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import Panel from "@/components/ui/Panel.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import SeverityBadge from "@/components/ui/SeverityBadge.vue";
import SkeletonRow from "@/components/ui/SkeletonRow.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import AppButton from "@/components/ui/AppButton.vue";
import { apiFetch, ApiError } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";

type Sev = "critical" | "high" | "medium" | "low";
interface Kpi { value: number | null; prev?: number | null; target?: number | null; better: "lower" | "higher"; sample?: number; count?: number; total?: number }
interface Day { date: string; incidents: number; alerts: number }
interface KeyInc { incident_code: string; title: string; severity: string; status: string; host: string | null; alert_count: number; techniques: string[] }
interface Exec {
  generated_at: string; window_days: number;
  kpis: { mttd_minutes: Kpi; mttr_minutes: Kpi; fp_rate_pct: Kpi; coverage_pct: Kpi; incidents: Kpi };
  trend_daily: Day[];
  key_incidents: KeyInc[];
}

const auth = useAuthStore();
const canGenerate = computed(() => auth.can("report:generate"));

const loading = ref(true);
const error = ref<string | null>(null);
const data = ref<Exec | null>(null);
const genMsg = ref<string | null>(null);
const busy = ref(false);

// Batang ditumpuk (alert + insiden), jadi pembaginya total tumpukan per hari —
// bukan nilai terbesar salah satunya — supaya hari tertinggi = 100% tanpa luber.
const maxDay = computed(() =>
  Math.max(1, ...(data.value?.trend_daily ?? []).map((d) => d.incidents + d.alerts)),
);

// Tinggi batang dalam persen; beri lantai kecil agar nilai > 0 tetap terlihat.
function barH(value: number): string {
  if (value <= 0) return "0%";
  return Math.max(3, (value / maxDay.value) * 100) + "%";
}

function fmt(v: number | null | undefined, unit = ""): string {
  return v === null || v === undefined ? "—" : `${v}${unit}`;
}
// Delta vs periode sebelumnya, diwarnai menurut arah "baik".
function delta(k: Kpi): { text: string; tone: "ok" | "warn" | "muted" } {
  if (k.value === null || k.value === undefined || k.prev === null || k.prev === undefined) {
    return { text: "—", tone: "muted" };
  }
  const d = Math.round((k.value - k.prev) * 10) / 10;
  if (d === 0) return { text: "±0", tone: "muted" };
  const improved = k.better === "lower" ? d < 0 : d > 0;
  return { text: `${d > 0 ? "+" : ""}${d}`, tone: improved ? "ok" : "warn" };
}

async function load() {
  loading.value = true;
  error.value = null;
  try {
    data.value = await apiFetch<Exec>("/dashboard/executive?days=30");
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Gagal memuat KPI";
  } finally {
    loading.value = false;
  }
}

async function generate() {
  busy.value = true;
  genMsg.value = null;
  try {
    const r = await apiFetch<{ code: string }>("/reports", { method: "POST", body: { kind: "executive" } });
    genMsg.value = `Laporan ${r.code} dibuat (draf) — buka halaman Laporan untuk tinjau & setujui.`;
  } catch (e) {
    genMsg.value = e instanceof ApiError ? e.message : "Gagal membuat laporan";
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-lg font-semibold text-ink">Ringkasan Eksekutif</h1>
        <p v-if="data" class="text-xs text-ink-dim">Jendela {{ data.window_days }} hari · dibanding periode sebelumnya</p>
      </div>
      <div class="flex items-center gap-2">
        <AppButton v-if="canGenerate" size="sm" variant="primary" :loading="busy" @click="generate">Buat laporan PDF</AppButton>
        <AppButton size="sm" variant="ghost" @click="load">Muat ulang</AppButton>
      </div>
    </div>

    <p v-if="genMsg" class="rounded border border-edge bg-graphite-raised px-3 py-2 text-sm text-ink-muted">
      {{ genMsg }}
      <RouterLink to="/laporan" class="text-accent underline">Ke Laporan →</RouterLink>
    </p>

    <div v-if="loading" class="space-y-2"><SkeletonRow v-for="i in 4" :key="i" /></div>
    <EmptyState v-else-if="error" :message="error"><template #action><AppButton size="sm" @click="load">{{ $t("common.retry") }}</AppButton></template></EmptyState>

    <template v-else-if="data">
      <div class="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Panel>
          <div class="text-xs text-ink-dim">MTTD</div>
          <div class="text-2xl font-semibold text-ink">{{ fmt(data.kpis.mttd_minutes.value, " m") }}</div>
          <StatusBadge :tone="delta(data.kpis.mttd_minutes).tone">{{ delta(data.kpis.mttd_minutes).text }} vs lalu</StatusBadge>
        </Panel>
        <Panel>
          <div class="text-xs text-ink-dim">MTTR</div>
          <div class="text-2xl font-semibold text-ink">{{ fmt(data.kpis.mttr_minutes.value, " m") }}</div>
          <StatusBadge :tone="delta(data.kpis.mttr_minutes).tone">{{ delta(data.kpis.mttr_minutes).text }} vs lalu</StatusBadge>
        </Panel>
        <Panel>
          <div class="text-xs text-ink-dim">FP rate</div>
          <div class="text-2xl font-semibold text-ink">{{ fmt(data.kpis.fp_rate_pct.value, "%") }}</div>
          <StatusBadge :tone="delta(data.kpis.fp_rate_pct).tone">{{ delta(data.kpis.fp_rate_pct).text }} vs lalu</StatusBadge>
        </Panel>
        <Panel>
          <div class="text-xs text-ink-dim">Coverage ATT&CK</div>
          <div class="text-2xl font-semibold text-ink">{{ fmt(data.kpis.coverage_pct.value, "%") }}</div>
          <StatusBadge :tone="(data.kpis.coverage_pct.value ?? 0) >= (data.kpis.coverage_pct.target ?? 50) ? 'ok' : 'warn'">
            target {{ data.kpis.coverage_pct.target }}%
          </StatusBadge>
        </Panel>
        <Panel>
          <div class="text-xs text-ink-dim">Insiden</div>
          <div class="text-2xl font-semibold text-ink">{{ fmt(data.kpis.incidents.value) }}</div>
          <StatusBadge :tone="delta(data.kpis.incidents).tone">{{ delta(data.kpis.incidents).text }} vs lalu</StatusBadge>
        </Panel>
      </div>

      <Panel title="Tren harian · insiden & alert">
        <div v-if="data.trend_daily.length" class="flex h-28 items-end gap-0.5 overflow-hidden">
          <div v-for="(d, i) in data.trend_daily" :key="i" class="flex h-full min-h-0 flex-1 flex-col justify-end gap-0.5" :title="`${d.date} — ${d.incidents} insiden, ${d.alerts} alert`">
            <div class="rounded-sm bg-accent/60" :style="{ height: barH(d.alerts) }" />
            <div class="rounded-sm bg-sev-medium/70" :style="{ height: barH(d.incidents) }" />
          </div>
        </div>
        <div class="mt-1 flex justify-between font-mono text-[10px] text-ink-dim">
          <span>{{ data.trend_daily[0]?.date }}</span>
          <span>alert (aksen) · insiden (kuning)</span>
          <span>{{ data.trend_daily[data.trend_daily.length - 1]?.date }}</span>
        </div>
      </Panel>

      <Panel title="Insiden penting">
        <table v-if="data.key_incidents.length" class="w-full text-sm">
          <thead class="text-left text-xs text-ink-dim">
            <tr><th class="py-1">Kode</th><th class="py-1">Severity</th><th class="py-1">Status</th><th class="py-1">Host</th><th class="py-1">Teknik</th><th class="py-1 text-right">Alert</th></tr>
          </thead>
          <tbody>
            <tr v-for="k in data.key_incidents" :key="k.incident_code" class="border-t border-edge/50">
              <td class="py-1 font-mono text-ink">{{ k.incident_code }}</td>
              <td class="py-1"><SeverityBadge :severity="(k.severity as Sev)" /></td>
              <td class="py-1 text-ink-muted">{{ k.status }}</td>
              <td class="py-1 font-mono text-ink-muted">{{ k.host || "—" }}</td>
              <td class="py-1 font-mono text-xs text-ink-dim">{{ k.techniques.join(", ") || "—" }}</td>
              <td class="py-1 text-right text-ink">{{ k.alert_count }}</td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-else message="Tidak ada insiden pada periode" />
      </Panel>
    </template>
  </div>
</template>
