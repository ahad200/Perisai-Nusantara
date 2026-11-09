<script setup lang="ts">
import { onMounted, ref } from "vue";
import Panel from "@/components/ui/Panel.vue";
import DataTable, { type Column } from "@/components/ui/DataTable.vue";
import SkeletonRow from "@/components/ui/SkeletonRow.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import AppButton from "@/components/ui/AppButton.vue";
import { apiFetch, ApiError } from "@/lib/api";
import type { CurrentUser } from "@/stores/auth";
import type { Role } from "@/lib/rbac";
import { useI18n } from "vue-i18n";

const { t } = useI18n();
const rows = ref<CurrentUser[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

// Urutan tampil untuk legenda 4-role (eksekusi → persetujuan → intel → audit).
const ROLE_ORDER: Role[] = ["operator", "commander", "intel", "auditor"];

function roleLabel(role: string): string {
  const key = `pengguna.roles.${role}.label`;
  const label = t(key);
  return label === key ? role : label; // fallback: tampilkan role mentah bila tak dikenal
}

const columns = (): Column[] => [
  { key: "id", label: t("pengguna.id"), mono: true, align: "right", width: "64px" },
  { key: "username", label: t("pengguna.username"), mono: true },
  { key: "full_name", label: t("pengguna.fullName") },
  { key: "role", label: t("pengguna.role") },
  { key: "mfa_enabled", label: t("pengguna.mfa"), width: "80px" },
  { key: "is_active", label: t("pengguna.active"), width: "80px" },
];

async function load() {
  loading.value = true;
  error.value = null;
  try {
    rows.value = await apiFetch<CurrentUser[]>("/users");
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Gagal memuat";
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="space-y-4">
    <h1 class="text-lg font-semibold text-ink">{{ $t("pengguna.title") }}</h1>

    <!-- Legenda model 4-role (RBAC) -->
    <Panel>
      <div class="space-y-1">
        <h2 class="text-sm font-semibold text-ink">{{ $t("pengguna.legend") }}</h2>
        <p class="text-xs text-ink-muted">{{ $t("pengguna.legendHint") }}</p>
      </div>
      <dl class="mt-3 grid gap-3 sm:grid-cols-2">
        <div
          v-for="role in ROLE_ORDER"
          :key="role"
          class="rounded-md border border-edge bg-graphite-raised p-3"
        >
          <dt>
            <span class="inline-block rounded border border-edge bg-graphite-surface px-2 py-0.5 font-mono text-xs text-ink">
              {{ role }}
            </span>
            <span class="ml-2 text-sm font-medium text-ink">{{ $t(`pengguna.roles.${role}.label`) }}</span>
          </dt>
          <dd class="mt-1 text-xs leading-relaxed text-ink-muted">{{ $t(`pengguna.roles.${role}.desc`) }}</dd>
        </div>
      </dl>
    </Panel>

    <SkeletonRow v-if="loading" />

    <Panel v-else-if="error">
      <EmptyState :message="error">
        <template #action>
          <AppButton size="sm" @click="load">{{ $t("common.retry") }}</AppButton>
        </template>
      </EmptyState>
    </Panel>

    <EmptyState v-else-if="rows.length === 0" :message="$t('common.empty')" />

    <DataTable v-else :columns="columns()" :rows="rows" row-key="id">
      <template #[`cell:role`]="{ value }">
        <span class="inline-flex items-center gap-2">
          <span class="rounded border border-edge bg-graphite-raised px-2 py-0.5 font-mono text-xs text-ink">{{ value }}</span>
          <span class="text-xs text-ink-muted">{{ roleLabel(String(value)) }}</span>
        </span>
      </template>
      <template #[`cell:mfa_enabled`]="{ value }">
        <StatusBadge :tone="value ? 'ok' : 'muted'">{{ value ? "ON" : "OFF" }}</StatusBadge>
      </template>
      <template #[`cell:is_active`]="{ value }">
        <StatusBadge :tone="value ? 'ok' : 'danger'">{{ value ? "AKTIF" : "NONAKTIF" }}</StatusBadge>
      </template>
    </DataTable>
  </div>
</template>
