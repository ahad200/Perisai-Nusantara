<script setup lang="ts">
const model = defineModel<string>({ required: true });

withDefaults(
  defineProps<{
    label?: string;
    type?: string;
    placeholder?: string;
    mono?: boolean;
    autocomplete?: string;
    inputmode?: "text" | "numeric" | "tel" | "email" | "url" | "search" | "decimal" | "none";
  }>(),
  { type: "text", mono: false },
);
</script>

<template>
  <label class="block">
    <span v-if="label" class="mb-1 block text-xs text-ink-muted">{{ label }}</span>
    <input
      v-model="model"
      :type="type"
      :placeholder="placeholder"
      :autocomplete="autocomplete"
      :inputmode="inputmode"
      :class="[
        'w-full rounded border border-edge bg-graphite-base px-2.5 text-sm text-ink',
        'h-9 placeholder:text-ink-dim focus:border-accent',
        mono ? 'font-mono tnum tracking-tight' : '',
      ]"
    />
  </label>
</template>
