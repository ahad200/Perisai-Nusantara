<script setup lang="ts">
// Navigasi dikelompokkan per fungsi kerja (Operasi / Data / Analisis / Administrasi)
// dengan hitungan antrian di item yang relevan, dan status sistem di kaki sidebar.
// Tanpa ikon dekoratif (C.5): hierarki lewat tipografi & garis.
import { computed } from "vue";
import { useAuthStore } from "@/stores/auth";
import type { Permission } from "@/lib/rbac";
import { useOpsStatus } from "@/lib/opsStatus";

type CountKey = "open_alerts" | "active_incidents" | "pending_approvals";

interface NavItem {
  to: string;
  labelKey: string;
  permission?: Permission;
  dev?: boolean;
  count?: CountKey;
}
interface NavGroup { label: string; items: NavItem[] }

const auth = useAuthStore();
const ops = useOpsStatus();

const GROUPS: NavGroup[] = [
  { label: "Operasi", items: [
    { to: "/", labelKey: "nav.situasi" },
    { to: "/alerts", labelKey: "nav.alerts", permission: "alert:read", count: "open_alerts" },
    { to: "/incidents", labelKey: "nav.incidents", permission: "incident:read", count: "active_incidents" },
    { to: "/soar", labelKey: "nav.soar", permission: "soar:read", count: "pending_approvals" },
  ] },
  { label: "Data", items: [
    { to: "/aset", labelKey: "nav.aset", permission: "asset:read" },
    { to: "/event", labelKey: "nav.event", permission: "event:read" },
    { to: "/intel", labelKey: "nav.intel", permission: "intel:read" },
  ] },
  { label: "Analisis", items: [
    { to: "/coverage", labelKey: "nav.coverage", permission: "dashboard:read" },
    { to: "/eksekutif", labelKey: "nav.eksekutif", permission: "dashboard:read" },
    { to: "/laporan", labelKey: "nav.laporan", permission: "report:read" },
  ] },
  { label: "Administrasi", items: [
    { to: "/pengguna", labelKey: "nav.pengguna", permission: "user:read" },
    { to: "/audit", labelKey: "nav.audit", permission: "audit:read" },
  ] },
  { label: "Dev", items: [
    { to: "/dev/components", labelKey: "nav.components", dev: true },
  ] },
];

// Menu menyesuaikan role (RBAC). Item dev tampil hanya di mode dev. Grup kosong disembunyikan.
const groups = computed(() =>
  GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((it) => {
      if (it.dev && !import.meta.env.DEV) return false;
      return it.permission ? auth.can(it.permission) : true;
    }),
  })).filter((g) => g.items.length),
);

function countOf(it: NavItem): number | null {
  const s = ops.snapshot.value;
  return it.count && s ? s[it.count] : null;
}
</script>

<template>
  <aside class="flex w-56 shrink-0 flex-col border-r border-edge bg-graphite-surface">
    <div class="border-b border-edge px-4 py-3">
      <div class="text-sm font-semibold tracking-[0.12em] text-ink">PERISAI NUSANTARA</div>
      <div class="mt-0.5 font-mono text-[11px] text-ink-dim">PN-X · MATA ELANG · SOC</div>
    </div>

    <nav class="flex-1 overflow-y-auto py-2" aria-label="Navigasi utama">
      <div v-for="(g, gi) in groups" :key="g.label" class="mb-2" :class="gi > 0 ? 'border-t border-edge pt-1' : ''">
        <div class="flex items-center gap-2 px-4 pb-1 pt-2 font-mono text-xs font-semibold uppercase tracking-[0.16em] text-ink">
          <span class="h-3 w-0.5 bg-accent" aria-hidden="true" />
          {{ g.label }}
        </div>
        <RouterLink
          v-for="it in g.items"
          :key="it.to"
          :to="it.to"
          class="flex items-center justify-between border-l-2 border-transparent py-1.5 pl-[14px] pr-3 text-sm text-ink-muted hover:bg-graphite-raised hover:text-ink"
          exact-active-class="!border-accent bg-graphite-raised !text-ink"
        >
          <span>{{ $t(it.labelKey) }}</span>
          <span
            v-if="countOf(it)"
            class="font-mono text-xs tnum"
            :class="it.count === 'pending_approvals' ? 'text-sev-medium' : 'text-ink-dim'"
          >{{ countOf(it) }}</span>
        </RouterLink>
      </div>
    </nav>

    <!-- Status sistem: kesehatan API + versi. -->
    <div class="border-t border-edge px-4 py-2 font-mono text-[11px] text-ink-dim">
      <div class="flex items-center justify-between">
        <span>API</span>
        <span :class="ops.apiOk.value === false ? 'text-sev-critical' : 'text-ink-muted'">
          {{ ops.apiOk.value === null ? "…" : ops.apiOk.value ? "TERHUBUNG" : "TERPUTUS" }}
        </span>
      </div>
      <div v-if="ops.apiVersion.value" class="flex items-center justify-between">
        <span>Versi</span><span>{{ ops.apiVersion.value }}</span>
      </div>
    </div>
  </aside>
</template>
