<script setup lang="ts">
import { computed } from "vue";

// Kritikalitas aset K1/K2/K3. SENGAJA tidak memakai palet severity (merah/oranye)
// — warna severity hanya untuk severity (PRD Lampiran C). Tingkat dibedakan lewat
// ketebalan & intensitas teks/garis, bukan warna status.
type Crit = "K1" | "K2" | "K3";

const props = defineProps<{ level?: Crit | string | null }>();

const TITLE: Record<Crit, string> = {
  K1: "K1 — Misi-kritis",
  K2: "K2 — Penting",
  K3: "K3 — Umum",
};

const norm = computed<Crit | null>(() => {
  const v = (props.level ?? "").toString().toUpperCase();
  return v === "K1" || v === "K2" || v === "K3" ? (v as Crit) : null;
});

const cls = computed(() => {
  switch (norm.value) {
    case "K1":
      return "border-accent/70 text-ink font-semibold";
    case "K2":
      return "border-edge text-ink-muted";
    case "K3":
      return "border-edge text-ink-dim";
    default:
      return "border-transparent text-ink-dim";
  }
});
</script>

<template>
  <span
    v-if="norm"
    :title="TITLE[norm]"
    :class="[
      'inline-flex items-center rounded-sm border bg-graphite-raised px-1.5 py-0.5',
      'font-mono text-xs tracking-tight',
      cls,
    ]"
  >
    {{ norm }}
  </span>
  <span v-else class="font-mono text-xs text-ink-dim">—</span>
</template>
