<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    variant?: "primary" | "default" | "ghost" | "danger";
    size?: "sm" | "md";
    type?: "button" | "submit";
    disabled?: boolean;
    loading?: boolean;
  }>(),
  { variant: "default", size: "md", type: "button", disabled: false, loading: false },
);

const classes = computed(() => {
  const base =
    "inline-flex items-center justify-center gap-1.5 rounded border font-medium " +
    "transition-colors disabled:opacity-50 disabled:cursor-not-allowed select-none";
  const size = props.size === "sm" ? "h-7 px-2.5 text-xs" : "h-9 px-3.5 text-sm";
  const variant = {
    primary: "bg-accent text-accent-ink border-accent hover:brightness-110",
    default: "bg-graphite-raised text-ink border-edge hover:bg-graphite-surface",
    ghost: "bg-transparent text-ink-muted border-transparent hover:bg-graphite-surface",
    danger: "bg-transparent text-sev-critical border-sev-critical/50 hover:bg-sev-critical/10",
  }[props.variant];
  return `${base} ${size} ${variant}`;
});
</script>

<template>
  <button :type="type" :class="classes" :disabled="disabled || loading">
    <span
      v-if="loading"
      class="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent"
      aria-hidden="true"
    />
    <slot />
  </button>
</template>
