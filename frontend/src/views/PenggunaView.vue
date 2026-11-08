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
import { useI18n } from "vue-i18n";

const { t } = useI18n();
const rows = ref<CurrentUser[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const columns = (): Column[] => [
  { key: "id", label: t("pengguna.id"), mono: true, align: "right", width: "64px" },
  { key: "username", label: t("pengguna.username"), mono: true },
  { key: "full_name", label: t("pengguna.fullName") },
  { key: "role", label: t("pengguna.role"), mono: true },
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
      <template #[`cell:mfa_enabled`]="{ value }">
        <StatusBadge :tone="value ? 'ok' : 'muted'">{{ value ? "ON" : "OFF" }}</StatusBadge>
      </template>
      <template #[`cell:is_active`]="{ value }">
        <StatusBadge :tone="value ? 'ok' : 'danger'">{{ value ? "AKTIF" : "NONAKTIF" }}</StatusBadge>
      </template>
    </DataTable>
  </div>
</template>
