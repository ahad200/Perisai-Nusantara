<script setup lang="ts">
import { computed } from "vue";

type Severity = "critical" | "high" | "medium" | "low" | "info";

const props = defineProps<{ severity: Severity }>();

// Warna HANYA pendukung; label teks selalu ada (aman untuk buta warna — C.2).
const LABEL: Record<Severity, string> = {
  critical: "CRITICAL",
  high: "HIGH",
  medium: "MEDIUM",
  low: "LOW",
  info: "INFO",
};

const dotColor = computed(() => `var(--sev-${props.severity})`);
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 rounded-sm border border-edge bg-graphite-raised px-1.5 py-0.5 text-xs font-medium uppercase tracking-wide"
  >
    <span
      class="h-2 w-2 rounded-full"
      :style="{ backgroundColor: dotColor }"
      aria-hidden="true"
    />
    {{ LABEL[severity] }}
  </span>
</template>
