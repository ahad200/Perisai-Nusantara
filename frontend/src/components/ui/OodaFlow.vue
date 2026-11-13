<script setup lang="ts">
// Alur investigasi OODA (Observe → Orient → Decide → Act) untuk satu insiden.
// Murni tampilan atas data tercatat (GET /incidents/{id}/ooda) — tanpa animasi,
// warna hanya untuk severity & status yang butuh perhatian (PRD Lampiran C).
import SeverityBadge from "@/components/ui/SeverityBadge.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import CritBadge from "@/components/ui/CritBadge.vue";
import { formatWIB } from "@/lib/time";
import type { Ooda, OodaItem, OodaPhase } from "@/lib/types";

type Sev = "critical" | "high" | "medium" | "low" | "info";
type Tone = "ok" | "warn" | "danger" | "muted";

defineProps<{ data: Ooda }>();

const PHASE: Record<OodaPhase["key"], { n: number; label: string; hint: string }> = {
  observe: { n: 1, label: "Observe", hint: "alert terdeteksi" },
  orient: { n: 2, label: "Orient", hint: "teknik, kritikalitas, atribusi" },
  decide: { n: 3, label: "Decide", hint: "Matriks Otonomi & approval" },
  act: { n: 4, label: "Act", hint: "eksekusi aksi & status" },
};

const STATE_LABEL: Record<OodaPhase["state"], string> = {
  empty: "Belum ada catatan",
  recorded: "Tercatat",
  waiting: "Menunggu",
};

// Status item → tone. Hanya status yang butuh perhatian diberi warna.
const STATUS_TONE: Record<string, Tone> = {
  pending: "warn", awaiting_approval: "warn", approval: "warn", proposed: "warn",
  approved: "ok", validated: "ok", executed: "ok", auto_timeout: "ok",
  denied: "danger", rejected: "danger", failed: "danger", expired: "danger",
};

function tone(it: OodaItem): Tone {
  return (it.status && STATUS_TONE[it.status]) || "muted";
}
</script>

<template>
  <ol class="space-y-2">
    <li
      v-for="p in data.phases"
      :key="p.key"
      class="rounded border bg-graphite-surface"
      :class="data.current_phase === p.key ? 'border-accent/70' : 'border-edge'"
    >
      <header class="flex flex-wrap items-center gap-2 border-b border-edge/60 px-2 py-1.5">
        <span class="font-mono text-xs text-ink-dim">{{ PHASE[p.key].n }}</span>
        <span class="text-xs font-medium text-ink">{{ PHASE[p.key].label }}</span>
        <span class="text-xs text-ink-dim">· {{ PHASE[p.key].hint }}</span>
        <span class="ml-auto flex items-center gap-1.5">
          <span v-if="data.current_phase === p.key" class="font-mono text-[10px] uppercase text-accent">fase berjalan</span>
          <StatusBadge :tone="p.state === 'waiting' ? 'warn' : 'muted'">
            {{ STATE_LABEL[p.state] }}<span v-if="p.items.length" class="ml-1 font-mono tnum">{{ p.items.length }}</span>
          </StatusBadge>
        </span>
      </header>

      <p v-if="p.waiting_reason" class="px-2 pt-1.5 text-xs text-sev-medium">{{ p.waiting_reason }}</p>

      <ul v-if="p.items.length" class="max-h-40 overflow-auto px-2 py-1.5">
        <li
          v-for="it in p.items"
          :key="it.ref"
          class="grid grid-cols-[132px_1fr_auto] items-baseline gap-2 py-0.5 text-xs"
        >
          <span class="font-mono text-[10px] text-ink-dim">{{ it.ts ? formatWIB(it.ts) : "—" }}</span>
          <span class="min-w-0">
            <SeverityBadge v-if="it.severity" :severity="(it.severity as Sev)" class="mr-1" />
            <span class="text-ink-muted">{{ it.text }}</span>
            <span class="ml-1 font-mono text-[10px] text-ink-dim">{{ it.ref }}</span>
          </span>
          <CritBadge v-if="it.kind === 'criticality'" :level="it.status" />
          <StatusBadge v-else-if="it.status && it.kind !== 'alert' && it.kind !== 'status'" :tone="tone(it)">
            {{ it.status }}
          </StatusBadge>
          <span v-else />
        </li>
      </ul>
      <p v-else class="px-2 py-1.5 text-xs text-ink-dim">—</p>
    </li>
  </ol>
  <p v-if="data.current_phase === 'closed'" class="mt-1 text-xs text-ink-dim">Insiden ditutup — alur selesai.</p>
</template>
