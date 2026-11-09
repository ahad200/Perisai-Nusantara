<script setup lang="ts">
import { computed } from "vue";
import { useAuthStore } from "@/stores/auth";
import type { Permission } from "@/lib/rbac";

interface NavItem {
  to: string;
  labelKey: string;
  permission?: Permission;
  dev?: boolean;
}

const auth = useAuthStore();

const ALL: NavItem[] = [
  { to: "/", labelKey: "nav.situasi" },
  { to: "/aset", labelKey: "nav.aset", permission: "asset:read" },
  { to: "/event", labelKey: "nav.event", permission: "event:read" },
  { to: "/alerts", labelKey: "nav.alerts", permission: "alert:read" },
  { to: "/incidents", labelKey: "nav.incidents", permission: "incident:read" },
  { to: "/soar", labelKey: "nav.soar", permission: "soar:read" },
  { to: "/intel", labelKey: "nav.intel", permission: "intel:read" },
  { to: "/pengguna", labelKey: "nav.pengguna", permission: "user:read" },
  { to: "/audit", labelKey: "nav.audit", permission: "audit:read" },
  { to: "/dev/components", labelKey: "nav.components", dev: true },
];

// Menu menyesuaikan role (RBAC). Item dev tampil hanya di mode dev.
const items = computed(() =>
  ALL.filter((it) => {
    if (it.dev && !import.meta.env.DEV) return false;
    return it.permission ? auth.can(it.permission) : true;
  }),
);
</script>

<template>
  <aside class="flex w-56 shrink-0 flex-col border-r border-edge bg-graphite-surface">
    <div class="border-b border-edge px-4 py-3">
      <div class="text-sm font-semibold tracking-wide text-ink">PERISAI NUSANTARA</div>
      <div class="font-mono text-xs text-ink-dim">PN-X · MATA ELANG</div>
    </div>
    <nav class="flex-1 overflow-y-auto p-2">
      <RouterLink
        v-for="it in items"
        :key="it.to"
        :to="it.to"
        class="mb-0.5 block rounded px-2.5 py-1.5 text-sm text-ink-muted hover:bg-graphite-raised hover:text-ink"
        exact-active-class="bg-graphite-raised !text-ink border-l-2 border-accent"
      >
        {{ $t(it.labelKey) }}
      </RouterLink>
    </nav>
  </aside>
</template>
