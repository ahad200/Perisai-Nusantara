<script setup lang="ts">
import { RouterLink } from "vue-router";
</script>

<template>
  <div class="flex h-full flex-col items-center justify-center gap-2">
    <p class="font-mono text-sm text-ink-dim">404</p>
    <p class="text-sm text-ink-muted">Halaman tidak ditemukan.</p>
    <RouterLink to="/" class="text-sm text-accent hover:underline">Kembali ke Situasi</RouterLink>
  </div>
</template>
