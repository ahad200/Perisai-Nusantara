<script setup lang="ts">
import { computed } from "vue";

// TLP (Traffic Light Protocol) — label berbagi informasi standar. Warna TLP
// adalah standar tersendiri (bukan palet severity): dipakai hanya sebagai titik
// kecil, teks label selalu ada (aman buta warna). Tidak memakai token --sev-*.
type Tlp = "WHITE" | "GREEN" | "AMBER" | "RED";

const props = defineProps<{ tlp?: string | null }>();

const DOT: Record<Tlp, string> = {
  WHITE: "#d1d5db",
  GREEN: "#33a532",
  AMBER: "#f5a623",
  RED: "#d64545",
};

const norm = computed<Tlp | null>(() => {
  const v = (props.tlp ?? "").toString().toUpperCase();
  return v === "WHITE" || v === "GREEN" || v === "AMBER" || v === "RED" ? (v as Tlp) : null;
});
</script>

<template>
  <span
    v-if="norm"
    class="inline-flex items-center gap-1.5 rounded-sm border border-edge bg-graphite-raised px-1.5 py-0.5 font-mono text-xs tracking-tight text-ink-muted"
  >
    <span class="h-2 w-2 rounded-sm" :style="{ backgroundColor: DOT[norm] }" aria-hidden="true" />
    TLP:{{ norm }}
  </span>
  <span v-else class="font-mono text-xs text-ink-dim">—</span>
</template>
