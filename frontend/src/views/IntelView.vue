<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import Panel from "@/components/ui/Panel.vue";
import DataTable, { type Column } from "@/components/ui/DataTable.vue";
import SkeletonRow from "@/components/ui/SkeletonRow.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import TlpBadge from "@/components/ui/TlpBadge.vue";
import TextInput from "@/components/ui/TextInput.vue";
import AppButton from "@/components/ui/AppButton.vue";
import Modal from "@/components/ui/Modal.vue";
import { apiFetch, ApiError } from "@/lib/api";
import { formatWIB } from "@/lib/time";
import { useAuthStore } from "@/stores/auth";
import { useI18n } from "vue-i18n";

interface IoC {
  id: number;
  type: string;
  value: string;
  source: string;
  tlp: string;
  confidence: number;
  status: string;
  effective_status: string;
  blockable: boolean;
  first_seen: string;
  last_seen: string;
  expires_at: string | null;
  description: string;
  tags: string[];
  stix_id: string | null;
}
interface Enrichment {
  kind: string;
  source: string;
  data: Record<string, unknown>;
  mirror_updated_at: string;
  mirror_age_days: number;
}
interface IoCDetail extends IoC {
  enrichment: Enrichment[];
}
interface IoCPage {
  items: IoC[];
  total: number;
  limit: number;
  offset: number;
}

const { t } = useI18n();
const auth = useAuthStore();
const canManage = auth.can("intel:manage");

const rows = ref<IoC[]>([]);
const total = ref(0);
const loading = ref(true);
const error = ref<string | null>(null);
const type = ref("");
const status = ref("");
const q = ref("");

const TYPES = ["ip", "ipv6", "domain", "url", "email", "md5", "sha1", "sha256", "other"];
const STATUSES = ["active", "expired", "whitelisted", "false_positive"];

const columns = (): Column[] => [
  { key: "type", label: t("intel.type"), mono: true, width: "80px" },
  { key: "value", label: t("intel.value"), mono: true },
  { key: "tlp", label: t("intel.tlp"), width: "110px" },
  { key: "confidence", label: t("intel.confidence"), align: "right", width: "90px" },
  { key: "effective_status", label: t("intel.status"), width: "130px" },
  { key: "expires_at", label: t("intel.expires"), mono: true, width: "190px" },
];

function statusTone(s: string): "ok" | "warn" | "danger" | "muted" {
  if (s === "active") return "ok";
  if (s === "whitelisted") return "warn";
  if (s === "false_positive") return "danger";
  return "muted";
}

async function load() {
  loading.value = true;
  error.value = null;
  const p = new URLSearchParams();
  if (type.value) p.set("type", type.value);
  if (status.value) p.set("status", status.value);
  if (q.value.trim()) p.set("q", q.value.trim());
  try {
    const page = await apiFetch<IoCPage>(`/intel/iocs?${p.toString()}`);
    rows.value = page.items;
    total.value = page.total;
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Gagal memuat";
  } finally {
    loading.value = false;
  }
}

// --- Detail ---
const detail = ref<IoCDetail | null>(null);
const detailOpen = ref(false);
async function openDetail(row: IoC) {
  detailOpen.value = true;
  detail.value = null;
  try {
    detail.value = await apiFetch<IoCDetail>(`/intel/iocs/${row.id}`);
  } catch {
    detailOpen.value = false;
  }
}
async function setStatus(newStatus: string) {
  if (!detail.value) return;
  await apiFetch(`/intel/iocs/${detail.value.id}/status`, { method: "POST", body: { status: newStatus } });
  await openDetail(detail.value);
  await load();
}

// --- Import / seed ---
const importOpen = ref(false);
const bundleText = ref("");
const importMsg = ref<string | null>(null);
const busy = ref(false);

const SAMPLE = JSON.stringify({
  type: "bundle",
  id: "bundle--demo-paste",
  objects: [
    {
      type: "indicator", spec_version: "2.1", id: "indicator--demo-1",
      created: "2026-11-01T00:00:00Z", valid_from: "2026-11-01T00:00:00Z",
      valid_until: "2027-06-01T00:00:00Z", name: "Demo phishing domain", confidence: 80,
      labels: ["malicious-activity"], pattern_type: "stix",
      pattern: "[domain-name:value = 'phish-login.example.org']",
      object_marking_refs: ["marking-definition--f88d31f6-486f-44da-b317-01333bde0b82"],
    },
  ],
}, null, 2);

async function doImport() {
  busy.value = true;
  importMsg.value = null;
  try {
    const bundle = JSON.parse(bundleText.value);
    const res = await apiFetch<{ created: number; updated: number; skipped: number }>(
      "/intel/import/stix", { method: "POST", body: { bundle, source: "Paste manual" } },
    );
    importMsg.value = `${t("intel.imported")}: +${res.created} / ~${res.updated} / skip ${res.skipped}`;
    await load();
  } catch (e) {
    importMsg.value = e instanceof ApiError ? e.message : "JSON tidak valid";
  } finally {
    busy.value = false;
  }
}

async function seedSample() {
  busy.value = true;
  try {
    await apiFetch("/intel/seed", { method: "POST" });
    await load();
  } finally {
    busy.value = false;
  }
}

let debounce: ReturnType<typeof setTimeout> | undefined;
watch(q, () => {
  clearTimeout(debounce);
  debounce = setTimeout(load, 300);
});
watch([type, status], load);

onMounted(load);
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h1 class="text-lg font-semibold text-ink">{{ $t("intel.title") }}</h1>
      <div v-if="canManage" class="flex gap-2">
        <AppButton size="sm" variant="default" :loading="busy" @click="seedSample">{{ $t("intel.seed") }}</AppButton>
        <AppButton size="sm" variant="primary" @click="importOpen = true">{{ $t("intel.import") }}</AppButton>
      </div>
    </div>

    <div class="flex flex-wrap items-end gap-3">
      <div class="w-64">
        <TextInput v-model="q" :placeholder="t('intel.search')" />
      </div>
      <select v-model="type" class="h-9 rounded border border-edge bg-graphite-base px-2.5 text-sm text-ink focus:border-accent">
        <option value="">{{ t("intel.allTypes") }}</option>
        <option v-for="x in TYPES" :key="x" :value="x">{{ x }}</option>
      </select>
      <select v-model="status" class="h-9 rounded border border-edge bg-graphite-base px-2.5 text-sm text-ink focus:border-accent">
        <option value="">{{ t("intel.allStatus") }}</option>
        <option v-for="s in STATUSES" :key="s" :value="s">{{ s }}</option>
      </select>
    </div>

    <SkeletonRow v-if="loading" :rows="8" />

    <Panel v-else-if="error">
      <EmptyState :message="error">
        <template #action><AppButton size="sm" @click="load">{{ $t("common.retry") }}</AppButton></template>
      </EmptyState>
    </Panel>

    <EmptyState v-else-if="rows.length === 0" :message="$t('common.empty')" />

    <template v-else>
      <DataTable :columns="columns()" :rows="rows" row-key="id" clickable @row-click="openDetail">
        <template #[`cell:tlp`]="{ value }"><TlpBadge :tlp="value as string" /></template>
        <template #[`cell:effective_status`]="{ value }">
          <StatusBadge :tone="statusTone(value as string)">{{ value }}</StatusBadge>
        </template>
        <template #[`cell:expires_at`]="{ value }">{{ value ? formatWIB(value as string) : "—" }}</template>
      </DataTable>
      <div class="text-xs text-ink-dim">{{ total }} IoC</div>
    </template>

    <!-- Detail IoC -->
    <Modal v-model:open="detailOpen" :title="t('intel.detail')">
      <div v-if="detail" class="space-y-3">
        <dl class="grid grid-cols-[120px_1fr] gap-x-3 gap-y-1 text-sm">
          <dt class="text-ink-muted">{{ t("intel.value") }}</dt>
          <dd class="break-all font-mono text-ink">{{ detail.type }}:{{ detail.value }}</dd>
          <dt class="text-ink-muted">{{ t("intel.tlp") }}</dt>
          <dd><TlpBadge :tlp="detail.tlp" /></dd>
          <dt class="text-ink-muted">{{ t("intel.status") }}</dt>
          <dd><StatusBadge :tone="statusTone(detail.effective_status)">{{ detail.effective_status }}</StatusBadge></dd>
          <dt class="text-ink-muted">{{ t("intel.blockable") }}</dt>
          <dd class="text-ink">{{ detail.blockable ? t("intel.yes") : t("intel.no") }}</dd>
          <dt class="text-ink-muted">{{ t("intel.confidence") }}</dt>
          <dd class="font-mono text-ink">{{ detail.confidence }}</dd>
          <dt class="text-ink-muted">{{ t("intel.source") }}</dt>
          <dd class="text-ink">{{ detail.source }}</dd>
          <dt class="text-ink-muted">{{ t("intel.expires") }}</dt>
          <dd class="font-mono text-ink">{{ detail.expires_at ? formatWIB(detail.expires_at) : "—" }}</dd>
        </dl>

        <div>
          <div class="mb-1 text-xs text-ink-muted">{{ t("intel.enrichment") }}</div>
          <p v-if="detail.enrichment.length === 0" class="text-sm text-ink-dim">{{ t("intel.noEnrichment") }}</p>
          <div v-else class="space-y-2">
            <div v-for="(e, i) in detail.enrichment" :key="i" class="rounded border border-edge bg-graphite-base p-2">
              <div class="mb-1 flex items-center justify-between">
                <span class="font-mono text-xs uppercase text-ink">{{ e.kind }}</span>
                <span class="text-xs text-ink-dim">{{ e.source }} · {{ t("intel.mirrorAge") }} {{ e.mirror_age_days }} {{ t("intel.days") }}</span>
              </div>
              <dl class="grid grid-cols-[110px_1fr] gap-x-2 text-xs">
                <template v-for="(val, k) in e.data" :key="k">
                  <dt class="text-ink-muted">{{ k }}</dt>
                  <dd class="break-all font-mono text-ink-muted">{{ Array.isArray(val) ? val.join(", ") : String(val) }}</dd>
                </template>
              </dl>
            </div>
          </div>
        </div>
      </div>
      <SkeletonRow v-else :rows="4" />

      <template v-if="canManage && detail" #footer>
        <AppButton size="sm" variant="ghost" @click="setStatus('active')">{{ t("intel.reactivate") }}</AppButton>
        <AppButton size="sm" variant="default" @click="setStatus('whitelisted')">{{ t("intel.whitelist") }}</AppButton>
        <AppButton size="sm" variant="danger" @click="setStatus('false_positive')">{{ t("intel.markFp") }}</AppButton>
      </template>
    </Modal>

    <!-- Impor STIX -->
    <Modal v-model:open="importOpen" :title="t('intel.importTitle')">
      <p class="mb-2 text-sm text-ink-muted">{{ t("intel.importNote") }}</p>
      <textarea
        v-model="bundleText"
        rows="10"
        class="w-full rounded border border-edge bg-graphite-base p-2 font-mono text-xs text-ink focus:border-accent"
        placeholder='{ "type": "bundle", "objects": [ … ] }'
      />
      <p v-if="importMsg" class="mt-2 text-sm text-ink">{{ importMsg }}</p>
      <template #footer>
        <AppButton size="sm" variant="ghost" @click="bundleText = SAMPLE">{{ t("intel.loadSample") }}</AppButton>
        <AppButton size="sm" variant="primary" :loading="busy" :disabled="!bundleText.trim()" @click="doImport">
          {{ t("intel.doImport") }}
        </AppButton>
      </template>
    </Modal>
  </div>
</template>
