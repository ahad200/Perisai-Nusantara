<script setup lang="ts">
defineProps<{ message: string; hint?: string }>();
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-1 px-4 py-10 text-center">
    <p class="text-sm text-ink-muted">{{ message }}</p>
    <p v-if="hint" class="text-xs text-ink-dim">{{ hint }}</p>
    <div v-if="$slots.action" class="mt-2"><slot name="action" /></div>
  </div>
</template>
