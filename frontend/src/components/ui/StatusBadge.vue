<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{ tone?: "ok" | "warn" | "danger" | "muted" }>(),
  { tone: "muted" },
);

const classes = computed(
  () =>
    ({
      ok: "text-sev-low border-sev-low/40",
      warn: "text-sev-medium border-sev-medium/40",
      danger: "text-sev-critical border-sev-critical/40",
      muted: "text-ink-muted border-edge",
    })[props.tone],
);
</script>

<template>
  <span
    :class="classes"
    class="inline-flex items-center rounded-sm border bg-graphite-raised px-1.5 py-0.5 text-xs"
  >
    <slot />
  </span>
</template>
