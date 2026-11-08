<script setup lang="ts">
// Loading memakai skeleton, bukan spinner di tengah layar (PRD C.4).
withDefaults(defineProps<{ rows?: number }>(), { rows: 5 });
</script>

<template>
  <div class="divide-y divide-edge/60 rounded border border-edge">
    <div v-for="n in rows" :key="n" class="flex items-center gap-3 px-3 py-2.5">
      <div class="h-3 w-10 animate-pulse rounded-sm bg-graphite-raised" />
      <div class="h-3 flex-1 animate-pulse rounded-sm bg-graphite-raised" />
      <div class="h-3 w-24 animate-pulse rounded-sm bg-graphite-raised" />
    </div>
  </div>
</template>
