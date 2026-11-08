<script setup lang="ts">
import { onMounted, ref } from "vue";
import Panel from "@/components/ui/Panel.vue";
import DataTable, { type Column } from "@/components/ui/DataTable.vue";
import SkeletonRow from "@/components/ui/SkeletonRow.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import AppButton from "@/components/ui/AppButton.vue";
import { apiFetch, ApiError } from "@/lib/api";
import { formatWIB } from "@/lib/time";
import { useAuthStore } from "@/stores/auth";
import { useI18n } from "vue-i18n";

interface AuditEntry {
  id: number;
  ts: string;
  actor_type: string;
  actor_id: string | null;
  action: string;
  object_type: string | null;
  object_id: string | null;
  entry_hash: string;
}
interface VerifyResult {
  ok: boolean;
  count: number;
  broken_at: number | null;
  reason: string | null;
}

const { t } = useI18n();
const auth = useAuthStore();

const rows = ref<AuditEntry[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
const verify = ref<VerifyResult | null>(null);
const verifying = ref(false);

const columns = (): Column[] => [
  { key: "id", label: "#", mono: true, align: "right", width: "56px" },
  { key: "ts", label: t("audit.ts"), mono: true, width: "210px" },
  { key: "action", label: t("audit.action"), mono: true },
  { key: "actor_id", label: t("audit.actor") },
  { key: "object", label: t("audit.object") },
  { key: "entry_hash", label: t("audit.hash"), mono: true },
];

async function load() {
  loading.value = true;
  error.value = null;
  try {
    rows.value = await apiFetch<AuditEntry[]>("/audit?limit=200");
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Gagal memuat";
  } finally {
    loading.value = false;
  }
}

async function runVerify() {
  verifying.value = true;
  try {
    verify.value = await apiFetch<VerifyResult>("/audit/verify");
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Gagal verifikasi";
  } finally {
    verifying.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-ink">{{ $t("audit.title") }}</h1>
      <AppButton
        v-if="auth.can('audit:verify')"
        size="sm"
        variant="primary"
        :loading="verifying"
        @click="runVerify"
      >
        {{ $t("audit.verify") }}
      </AppButton>
    </div>

    <Panel v-if="verify">
      <div class="flex items-center gap-3 text-sm">
        <StatusBadge :tone="verify.ok ? 'ok' : 'danger'">
          {{ verify.ok ? "OK" : "TAMPERED" }}
        </StatusBadge>
        <span v-if="verify.ok" class="text-ink-muted">
          {{ $t("audit.ok") }} — {{ verify.count }} {{ $t("audit.count") }}
        </span>
        <span v-else class="text-sev-critical">
          {{ $t("audit.broken") }} #{{ verify.broken_at }} — {{ verify.reason }}
        </span>
      </div>
    </Panel>

    <SkeletonRow v-if="loading" :rows="8" />

    <Panel v-else-if="error">
      <EmptyState :message="error">
        <template #action>
          <AppButton size="sm" @click="load">{{ $t("common.retry") }}</AppButton>
        </template>
      </EmptyState>
    </Panel>

    <EmptyState v-else-if="rows.length === 0" :message="$t('common.empty')" />

    <DataTable v-else :columns="columns()" :rows="rows" row-key="id">
      <template #[`cell:ts`]="{ value }">{{ formatWIB(value as string) }}</template>
      <template #[`cell:object`]="{ row }">
        <span class="font-mono text-ink-muted">
          {{ row.object_type ?? "—" }}<template v-if="row.object_id">:{{ row.object_id }}</template>
        </span>
      </template>
      <template #[`cell:entry_hash`]="{ value }">
        <span class="font-mono text-ink-dim">{{ (value as string).slice(0, 12) }}…</span>
      </template>
    </DataTable>
  </div>
</template>
