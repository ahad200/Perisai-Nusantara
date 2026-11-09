<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import Panel from "@/components/ui/Panel.vue";
import DataTable, { type Column } from "@/components/ui/DataTable.vue";
import SkeletonRow from "@/components/ui/SkeletonRow.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import CritBadge from "@/components/ui/CritBadge.vue";
import TextInput from "@/components/ui/TextInput.vue";
import AppButton from "@/components/ui/AppButton.vue";
import { apiFetch, ApiError } from "@/lib/api";
import { useI18n } from "vue-i18n";

interface Asset {
  id: number;
  hostname: string;
  ip: string | null;
  segment: string;
  owner: string;
  criticality: string;
  tags: string[];
}

const { t } = useI18n();
const rows = ref<Asset[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
const crit = ref<string>("");
const q = ref<string>("");

const columns = (): Column[] => [
  { key: "criticality", label: t("aset.criticality"), width: "110px" },
  { key: "hostname", label: t("aset.hostname"), mono: true },
  { key: "ip", label: t("aset.ip"), mono: true, width: "130px" },
  { key: "segment", label: t("aset.segment") },
  { key: "owner", label: t("aset.owner") },
  { key: "tags", label: t("aset.tags") },
];

async function load() {
  loading.value = true;
  error.value = null;
  const params = new URLSearchParams();
  if (crit.value) params.set("criticality", crit.value);
  if (q.value.trim()) params.set("q", q.value.trim());
  try {
    rows.value = await apiFetch<Asset[]>(`/assets?${params.toString()}`);
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Gagal memuat";
  } finally {
    loading.value = false;
  }
}

let debounce: ReturnType<typeof setTimeout> | undefined;
watch(q, () => {
  clearTimeout(debounce);
  debounce = setTimeout(load, 300);
});
watch(crit, load);

onMounted(load);
</script>

<template>
  <div class="space-y-4">
    <h1 class="text-lg font-semibold text-ink">{{ $t("aset.title") }}</h1>

    <div class="flex flex-wrap items-end gap-3">
      <div class="w-72">
        <TextInput v-model="q" :placeholder="t('aset.search')" />
      </div>
      <select
        v-model="crit"
        class="h-9 rounded border border-edge bg-graphite-base px-2.5 text-sm text-ink focus:border-accent"
      >
        <option value="">{{ t("aset.allCrit") }}</option>
        <option value="K1">K1</option>
        <option value="K2">K2</option>
        <option value="K3">K3</option>
      </select>
    </div>

    <SkeletonRow v-if="loading" :rows="8" />

    <Panel v-else-if="error">
      <EmptyState :message="error">
        <template #action>
          <AppButton size="sm" @click="load">{{ $t("common.retry") }}</AppButton>
        </template>
      </EmptyState>
    </Panel>

    <EmptyState v-else-if="rows.length === 0" :message="$t('common.empty')" />

    <template v-else>
      <DataTable :columns="columns()" :rows="rows" row-key="id">
        <template #[`cell:criticality`]="{ value }">
          <CritBadge :level="value as string" />
        </template>
        <template #[`cell:ip`]="{ value }">{{ value ?? "—" }}</template>
        <template #[`cell:tags`]="{ value }">
          <span class="flex flex-wrap gap-1">
            <span
              v-for="tag in (value as string[])"
              :key="tag"
              class="rounded-sm border border-edge bg-graphite-raised px-1.5 py-0.5 font-mono text-xs text-ink-muted"
            >{{ tag }}</span>
          </span>
        </template>
      </DataTable>
      <div class="text-xs text-ink-dim">
        {{ rows.length }} aset{{ crit ? ` · ${crit}` : "" }}{{ q.trim() ? ` · "${q.trim()}"` : "" }}
      </div>
    </template>
  </div>
</template>
