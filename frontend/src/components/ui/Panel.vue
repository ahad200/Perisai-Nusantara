<script setup lang="ts">
defineProps<{ title?: string }>();
</script>

<template>
  <section class="rounded border border-edge bg-graphite-surface">
    <header
      v-if="title || $slots.header"
      class="flex items-center justify-between border-b border-edge px-3 py-2"
    >
      <h2 class="font-mono text-xs font-medium uppercase tracking-[0.12em] text-ink-muted">
        <slot name="header">{{ title }}</slot>
      </h2>
      <div v-if="$slots.actions"><slot name="actions" /></div>
    </header>
    <div class="p-3">
      <slot />
    </div>
  </section>
</template>
