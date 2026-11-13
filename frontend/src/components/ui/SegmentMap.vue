<script setup lang="ts">
// Peta segmen jaringan: satu kolom per segmen (urut kritikalitas tertinggi dari
// backend), satu baris per host. Warna hanya dipakai untuk severity insiden aktif
// (PRD Lampiran C.1); kritikalitas lewat CritBadge (bukan warna severity).
import SeverityBadge from "@/components/ui/SeverityBadge.vue";
import CritBadge from "@/components/ui/CritBadge.vue";
import type { Segment, SegmentHost } from "@/lib/types";

type Sev = "critical" | "high" | "medium" | "low" | "info";

defineProps<{ segments: Segment[] }>();
const emit = defineEmits<{ (e: "open-incident", host: SegmentHost): void }>();

function open(h: SegmentHost) {
  if (h.incident_id) emit("open-incident", h);
}
</script>

<template>
  <div class="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
    <section
      v-for="seg in segments"
      :key="seg.segment"
      class="min-w-0 rounded border border-edge bg-graphite-raised"
    >
      <header class="border-b border-edge px-2 py-1.5">
        <div class="flex items-center justify-between gap-2">
          <span class="font-mono text-sm text-ink">{{ seg.segment }}</span>
          <SeverityBadge v-if="seg.max_severity" :severity="(seg.max_severity as Sev)" />
        </div>
        <div class="mt-0.5 flex flex-wrap gap-x-2 font-mono text-[11px] text-ink-dim">
          <span>{{ seg.assets }} aset</span>
          <span v-if="seg.K1" class="text-ink">K1×{{ seg.K1 }}</span>
          <span v-if="seg.K2">K2×{{ seg.K2 }}</span>
          <span v-if="seg.K3">K3×{{ seg.K3 }}</span>
          <span :class="seg.active_incidents ? 'text-sev-medium' : ''">· {{ seg.active_incidents }} insiden aktif</span>
        </div>
      </header>

      <ul class="max-h-56 overflow-auto py-0.5">
        <li v-for="h in seg.hosts" :key="h.asset_id">
          <component
            :is="h.incident_id ? 'button' : 'div'"
            :type="h.incident_id ? 'button' : undefined"
            class="grid w-full grid-cols-[3px_1fr_auto_auto] items-center gap-2 py-1 pr-2 text-left"
            :class="h.incident_id ? 'cursor-pointer hover:bg-graphite-surface focus:bg-graphite-surface focus:outline-none' : ''"
            :title="h.incident_id ? `Buka insiden aktif di ${h.hostname}` : undefined"
            @click="open(h)"
          >
            <span
              class="h-full min-h-[20px] w-[3px]"
              :style="h.max_severity ? { backgroundColor: `var(--sev-${h.max_severity})` } : {}"
            />
            <span class="min-w-0">
              <span class="block truncate font-mono text-xs text-ink">{{ h.hostname }}</span>
              <span class="block font-mono text-[10px] text-ink-dim">{{ h.ip }}</span>
            </span>
            <CritBadge :level="h.criticality" />
            <SeverityBadge v-if="h.max_severity" :severity="(h.max_severity as Sev)" />
            <span v-else class="w-0" />
          </component>
        </li>
      </ul>
    </section>
  </div>
</template>
