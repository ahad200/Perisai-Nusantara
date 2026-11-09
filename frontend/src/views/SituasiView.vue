<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import Panel from "@/components/ui/Panel.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import SeverityBadge from "@/components/ui/SeverityBadge.vue";
import CritBadge from "@/components/ui/CritBadge.vue";
import SkeletonRow from "@/components/ui/SkeletonRow.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import AppButton from "@/components/ui/AppButton.vue";
import { apiFetch, ApiError } from "@/lib/api";
import { formatWIB } from "@/lib/time";

type Sev = "critical" | "high" | "medium" | "low";
interface Trend { hour: string; alerts: number }
interface Source { source: string; events: number; last_event_at: string | null; lag_hours: number | null; status: string }
interface Segment { segment: string; assets: number; K1: number; K2: number; K3: number; active_incidents: number; max_severity: string | null }
interface Situasi {
  generated_at: string;
  posture: "critical" | "elevated" | "guarded" | "normal";
  active_incidents: number;
  incidents_by_severity: Record<Sev, number>;
  pending_approvals: number;
  open_alerts: number;
  trend_24h: Trend[];
  data_sources: Source[];
  segments: Segment[];
}

const loading = ref(true);
const error = ref<string | null>(null);
const data = ref<Situasi | null>(null);

const POSTURE: Record<string, { label: string; tone: "ok" | "warn" | "danger" | "muted"; note: string }> = {
  critical: { label: "KRITIS", tone: "danger", note: "Ada insiden critical aktif — perlu tindakan segera." },
  elevated: { label: "WASPADA", tone: "warn", note: "Insiden high atau approval tertunda." },
  guarded: { label: "SIAGA", tone: "warn", note: "Ada insiden medium aktif." },
  normal: { label: "NORMAL", tone: "ok", note: "Tidak ada insiden aktif berprioritas tinggi." },
};

const posture = computed(() => (data.value ? POSTURE[data.value.posture] : POSTURE.normal));
const maxTrend = computed(() =>
  Math.max(1, ...(data.value?.trend_24h ?? []).map((t) => t.alerts)),
);
const sevOrder: Sev[] = ["critical", "high", "medium", "low"];

async function load() {
  loading.value = true;
  error.value = null;
  try {
    data.value = await apiFetch<Situasi>("/dashboard/situasi");
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Gagal memuat situasi";
  } finally {
    loading.value = false;
  }
}
onMounted(load);
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-ink">{{ $t("situasi.title") }}</h1>
      <div class="flex items-center gap-2">
        <span v-if="data" class="font-mono text-xs text-ink-dim">
          {{ formatWIB(data.generated_at) }}
        </span>
        <AppButton size="sm" variant="ghost" @click="load">Muat ulang</AppButton>
      </div>
    </div>

    <div v-if="loading" class="space-y-2">
      <SkeletonRow v-for="i in 4" :key="i" />
    </div>
    <EmptyState v-else-if="error" :message="error">
      <template #action><AppButton size="sm" @click="load">{{ $t("common.retry") }}</AppButton></template>
    </EmptyState>

    <template v-else-if="data">
      <!-- Jawab: apakah ada yang butuh tindakan saya sekarang? -->
      <Panel>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="flex items-center gap-3">
            <StatusBadge :tone="posture.tone">POSTUR · {{ posture.label }}</StatusBadge>
            <span class="text-sm text-ink-muted">{{ posture.note }}</span>
          </div>
          <div class="flex gap-5">
            <div class="text-center">
              <div class="text-2xl font-semibold text-ink">{{ data.active_incidents }}</div>
              <div class="text-xs text-ink-dim">insiden aktif</div>
            </div>
            <div class="text-center">
              <div class="text-2xl font-semibold" :class="data.pending_approvals ? 'text-sev-medium' : 'text-ink'">
                {{ data.pending_approvals }}
              </div>
              <div class="text-xs text-ink-dim">approval tertunda</div>
            </div>
            <div class="text-center">
              <div class="text-2xl font-semibold text-ink">{{ data.open_alerts }}</div>
              <div class="text-xs text-ink-dim">alert terbuka</div>
            </div>
          </div>
        </div>
      </Panel>

      <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <!-- Insiden aktif per severity -->
        <Panel title="Insiden aktif per severity">
          <div class="space-y-2">
            <div v-for="s in sevOrder" :key="s" class="flex items-center gap-2">
              <div class="w-20"><SeverityBadge :severity="s" /></div>
              <div class="h-2 flex-1 overflow-hidden rounded-sm bg-graphite-raised">
                <div
                  class="h-full rounded-sm"
                  :style="{
                    width: Math.max(2, (data.incidents_by_severity[s] / Math.max(1, data.active_incidents)) * 100) + '%',
                    backgroundColor: `var(--sev-${s})`,
                  }"
                />
              </div>
              <div class="w-6 text-right font-mono text-sm text-ink">{{ data.incidents_by_severity[s] }}</div>
            </div>
          </div>
        </Panel>

        <!-- Tren alert 24 jam -->
        <Panel title="Tren alert · 24 jam">
          <div v-if="data.trend_24h.length" class="flex h-24 items-end gap-0.5">
            <div
              v-for="(t, i) in data.trend_24h"
              :key="i"
              class="flex-1 rounded-sm bg-accent/60 hover:bg-accent"
              :style="{ height: Math.max(2, (t.alerts / maxTrend) * 100) + '%' }"
              :title="`${t.hour} — ${t.alerts} alert`"
            />
          </div>
          <div class="mt-1 flex justify-between font-mono text-[10px] text-ink-dim">
            <span>{{ data.trend_24h[0]?.hour }}</span>
            <span>puncak {{ maxTrend }}/jam</span>
            <span>{{ data.trend_24h[data.trend_24h.length - 1]?.hour }}</span>
          </div>
        </Panel>

        <!-- Kesehatan sumber data -->
        <Panel title="Kesehatan sumber data">
          <table class="w-full text-sm">
            <tbody>
              <tr v-for="s in data.data_sources" :key="s.source" class="border-b border-edge/50 last:border-0">
                <td class="py-1 font-mono text-ink">{{ s.source }}</td>
                <td class="py-1 text-right text-ink-muted">{{ s.events }} ev</td>
                <td class="py-1 text-right text-ink-dim">
                  <span v-if="s.lag_hours !== null">{{ s.lag_hours }} jam</span>
                  <span v-else>—</span>
                </td>
                <td class="py-1 pl-2 text-right">
                  <StatusBadge :tone="s.status === 'ok' ? 'ok' : 'warn'">{{ s.status === 'ok' ? 'OK' : 'TERTINGGAL' }}</StatusBadge>
                </td>
              </tr>
            </tbody>
          </table>
        </Panel>
      </div>

      <!-- Peta segmen jaringan -->
      <Panel title="Peta segmen jaringan">
        <div v-if="data.segments.length" class="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <div
            v-for="seg in data.segments"
            :key="seg.segment"
            class="rounded border bg-graphite-raised p-3"
            :class="seg.active_incidents ? 'border-sev-medium/50' : 'border-edge'"
          >
            <div class="flex items-center justify-between">
              <span class="font-mono text-sm text-ink">{{ seg.segment }}</span>
              <SeverityBadge v-if="seg.max_severity" :severity="(seg.max_severity as Sev)" />
            </div>
            <div class="mt-2 flex items-center gap-2 text-xs text-ink-dim">
              <span>{{ seg.assets }} aset</span>
              <CritBadge v-if="seg.K1" level="K1" />
              <span v-if="seg.K1" class="text-ink-muted">×{{ seg.K1 }}</span>
            </div>
            <div class="mt-1 text-xs" :class="seg.active_incidents ? 'text-sev-medium' : 'text-ink-dim'">
              {{ seg.active_incidents }} insiden aktif
            </div>
          </div>
        </div>
        <EmptyState v-else message="Belum ada aset tersegmen" />
      </Panel>
    </template>
  </div>
</template>
