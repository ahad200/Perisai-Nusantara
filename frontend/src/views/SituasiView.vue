<script setup lang="ts">
import Panel from "@/components/ui/Panel.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-ink">{{ $t("situasi.title") }}</h1>
      <StatusBadge tone="ok">M2 · fondasi</StatusBadge>
    </div>

    <Panel>
      <p class="text-sm text-ink">
        {{ $t("situasi.welcome") }}
        <span class="font-mono text-accent">{{ auth.user?.username }}</span>
        (<span class="font-mono">{{ auth.user?.role }}</span
        >).
      </p>
      <p class="mt-2 text-sm text-ink-muted">{{ $t("situasi.placeholder") }}</p>
    </Panel>
  </div>
</template>
