<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import Panel from "@/components/ui/Panel.vue";
import DataTable, { type Column } from "@/components/ui/DataTable.vue";
import SkeletonRow from "@/components/ui/SkeletonRow.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import CritBadge from "@/components/ui/CritBadge.vue";
import TextInput from "@/components/ui/TextInput.vue";
import AppButton from "@/components/ui/AppButton.vue";
import Modal from "@/components/ui/Modal.vue";
import { apiFetch, ApiError } from "@/lib/api";
import { formatWIB } from "@/lib/time";
import { useAuthStore } from "@/stores/auth";
import { useI18n } from "vue-i18n";

interface EventRow {
  id: number;
  ts: string;
  source_type: string;
  host: string | null;
  asset_id: number | null;
  asset_criticality: string | null;
  category: string;
  action: string;
  outcome: string;
  user: string | null;
  src_ip: string | null;
  dst_ip: string | null;
  dst_port: number | null;
  bytes_out: number | null;
  message: string;
  scenario: string | null;
}
interface EventPage {
  items: EventRow[];
  total: number;
  limit: number;
  offset: number;
}
interface EventDetail extends EventRow {
  raw: Record<string, unknown>;
}

const { t } = useI18n();
const auth = useAuthStore();

const items = ref<EventRow[]>([]);
const total = ref(0);
const loading = ref(true);
const error = ref<string | null>(null);
const source = ref("");
const scenario = ref("");
const q = ref("");
const LIMIT = 100;
let offset = 0;

const SOURCES = ["auth", "firewall", "proxy", "edr"];
const SCENARIOS = ["baseline", "bruteforce", "beaconing", "ransomware"];

const columns = (): Column[] => [
  { key: "ts", label: t("event.ts"), mono: true, width: "200px" },
  { key: "source_type", label: t("event.source"), mono: true, width: "90px" },
  { key: "host", label: t("event.host"), mono: true },
  { key: "category", label: t("event.category") },
  { key: "action", label: t("event.action"), mono: true },
  { key: "outcome", label: t("event.outcome"), width: "100px" },
  { key: "scenario", label: t("event.scenario"), width: "110px" },
];

function params(off: number): string {
  const p = new URLSearchParams();
  if (source.value) p.set("source_type", source.value);
  if (scenario.value) p.set("scenario", scenario.value);
  if (q.value.trim()) p.set("q", q.value.trim());
  p.set("limit", String(LIMIT));
  p.set("offset", String(off));
  return p.toString();
}

async function load(reset = true) {
  if (reset) {
    offset = 0;
    loading.value = true;
  }
  error.value = null;
  try {
    const page = await apiFetch<EventPage>(`/events?${params(offset)}`);
    items.value = reset ? page.items : [...items.value, ...page.items];
    total.value = page.total;
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Gagal memuat";
  } finally {
    loading.value = false;
  }
}

function loadMore() {
  offset += LIMIT;
  load(false);
}

function outcomeTone(o: string): "ok" | "danger" | "muted" {
  if (o === "success") return "ok";
  if (o === "failure") return "danger";
  return "muted";
}

// --- Detail ---
const detail = ref<EventDetail | null>(null);
const detailOpen = ref(false);
async function openDetail(row: EventRow) {
  detailOpen.value = true;
  detail.value = null;
  try {
    detail.value = await apiFetch<EventDetail>(`/events/${row.id}`);
  } catch {
    detailOpen.value = false;
  }
}

// --- Simulator trigger (sim:run) ---
const simOpen = ref(false);
const simRunning = ref<string | null>(null);
const simMsg = ref<string | null>(null);
// Target opsional (hostname). Kosong = target bawaan skenario. Lebih dari satu = serentak.
interface SimTarget { hostname: string; criticality: string; segment: string }
const simTargets = ref<SimTarget[]>([]);
const simSelected = ref<string[]>([]);
const TARGETABLE = new Set(["bruteforce", "beaconing", "ransomware"]);
async function loadSimTargets() {
  if (simTargets.value.length) return;
  try {
    simTargets.value = await apiFetch<SimTarget[]>("/assets");
  } catch {
    simTargets.value = [];
  }
}
watch(simOpen, (open) => { if (open) loadSimTargets(); });

const SIM_OPTIONS = [
  { key: "baseline", labelKey: "sim.baseline" },
  { key: "bruteforce", labelKey: "sim.bruteforce" },
  { key: "beaconing", labelKey: "sim.beaconing" },
  { key: "ransomware", labelKey: "sim.ransomware" },
  { key: "all", labelKey: "sim.all" },
];
async function runSim(key: string) {
  simRunning.value = key;
  simMsg.value = null;
  try {
    const res = await apiFetch<{ results: { count: number; target: string | null }[] }>("/dev/simulate", {
      method: "POST",
      body: { scenario: key, days: 14, targets: TARGETABLE.has(key) ? simSelected.value : [] },
    });
    const totalEv = res.results.reduce((a, r) => a + r.count, 0);
    const hosts = res.results.map((r) => r.target).filter(Boolean).join(", ");
    simMsg.value = `${t("sim.done")}: ${totalEv} ${t("sim.events")}${hosts ? ` → ${hosts}` : ""}`;
    await load(true);
  } catch (e) {
    simMsg.value = e instanceof ApiError ? e.message : "Gagal";
  } finally {
    simRunning.value = null;
  }
}

let debounce: ReturnType<typeof setTimeout> | undefined;
watch(q, () => {
  clearTimeout(debounce);
  debounce = setTimeout(() => load(true), 300);
});
watch([source, scenario], () => load(true));

onMounted(() => load(true));
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h1 class="text-lg font-semibold text-ink">{{ $t("event.title") }}</h1>
      <AppButton v-if="auth.can('sim:run')" size="sm" variant="primary" @click="simOpen = true">
        {{ $t("sim.run") }}
      </AppButton>
    </div>

    <div class="flex flex-wrap items-end gap-3">
      <div class="w-72">
        <TextInput v-model="q" :placeholder="t('event.search')" />
      </div>
      <select
        v-model="source"
        class="h-9 rounded border border-edge bg-graphite-base px-2.5 text-sm text-ink focus:border-accent"
      >
        <option value="">{{ t("event.allSources") }}</option>
        <option v-for="s in SOURCES" :key="s" :value="s">{{ s }}</option>
      </select>
      <select
        v-model="scenario"
        class="h-9 rounded border border-edge bg-graphite-base px-2.5 text-sm text-ink focus:border-accent"
      >
        <option value="">{{ t("event.allScenarios") }}</option>
        <option v-for="s in SCENARIOS" :key="s" :value="s">{{ s }}</option>
      </select>
    </div>

    <SkeletonRow v-if="loading" :rows="10" />

    <Panel v-else-if="error">
      <EmptyState :message="error">
        <template #action>
          <AppButton size="sm" @click="load(true)">{{ $t("common.retry") }}</AppButton>
        </template>
      </EmptyState>
    </Panel>

    <EmptyState v-else-if="items.length === 0" :message="$t('common.empty')" />

    <template v-else>
      <DataTable :columns="columns()" :rows="items" row-key="id" clickable @row-click="openDetail">
        <template #[`cell:ts`]="{ value }">{{ formatWIB(value as string) }}</template>
        <template #[`cell:host`]="{ row }">
          <span class="inline-flex items-center gap-1.5">
            <CritBadge :level="row.asset_criticality" />
            <span class="font-mono text-ink">{{ row.host ?? "—" }}</span>
          </span>
        </template>
        <template #[`cell:outcome`]="{ value }">
          <StatusBadge :tone="outcomeTone(value as string)">{{ value }}</StatusBadge>
        </template>
        <template #[`cell:scenario`]="{ value }">
          <span class="font-mono text-xs text-ink-muted">{{ value ?? "—" }}</span>
        </template>
      </DataTable>

      <div class="flex items-center justify-between text-xs text-ink-dim">
        <span>{{ t("event.showing") }} {{ items.length }} {{ t("event.of") }} {{ total }}</span>
        <AppButton v-if="items.length < total" size="sm" :loading="loading" @click="loadMore">
          {{ t("event.more") }}
        </AppButton>
      </div>
    </template>

    <!-- Detail event -->
    <Modal v-model:open="detailOpen" :title="t('event.detail')">
      <div v-if="detail" class="space-y-3">
        <dl class="grid grid-cols-[110px_1fr] gap-x-3 gap-y-1 text-sm">
          <dt class="text-ink-muted">{{ t("event.ts") }}</dt>
          <dd class="font-mono text-ink">{{ formatWIB(detail.ts) }}</dd>
          <dt class="text-ink-muted">{{ t("event.source") }}</dt>
          <dd class="font-mono text-ink">{{ detail.source_type }}</dd>
          <dt class="text-ink-muted">{{ t("event.host") }}</dt>
          <dd class="font-mono text-ink">
            <CritBadge :level="detail.asset_criticality" /> {{ detail.host ?? "—" }}
          </dd>
          <dt class="text-ink-muted">{{ t("event.action") }}</dt>
          <dd class="font-mono text-ink">{{ detail.category }} / {{ detail.action }}</dd>
          <dt class="text-ink-muted">{{ t("event.outcome") }}</dt>
          <dd><StatusBadge :tone="outcomeTone(detail.outcome)">{{ detail.outcome }}</StatusBadge></dd>
        </dl>
        <p class="text-sm text-ink-muted">{{ detail.message }}</p>
        <div>
          <div class="mb-1 text-xs text-ink-muted">{{ t("event.raw") }}</div>
          <pre class="max-h-60 overflow-auto rounded border border-edge bg-graphite-base p-2 font-mono text-xs text-ink-muted">{{ JSON.stringify(detail.raw, null, 2) }}</pre>
        </div>
      </div>
      <SkeletonRow v-else :rows="4" />
    </Modal>

    <!-- Simulator -->
    <Modal v-model:open="simOpen" :title="t('sim.title')">
      <p class="mb-3 text-sm text-ink-muted">{{ t("sim.note") }}</p>
      <fieldset v-if="simTargets.length" class="mb-3">
        <legend class="mb-1 text-xs text-ink-muted">{{ t("sim.targets") }}</legend>
        <div class="grid grid-cols-2 gap-x-3 gap-y-1">
          <label v-for="a in simTargets" :key="a.hostname" class="flex items-center gap-2 text-sm text-ink">
            <input v-model="simSelected" type="checkbox" :value="a.hostname" class="accent-[var(--accent)]" />
            <CritBadge :level="a.criticality" />
            <span class="font-mono">{{ a.hostname }}</span>
          </label>
        </div>
        <p class="mt-1 text-xs text-ink-dim">{{ t("sim.targetsHint") }}</p>
      </fieldset>
      <div class="space-y-2">
        <AppButton
          v-for="opt in SIM_OPTIONS"
          :key="opt.key"
          size="sm"
          class="w-full !justify-start"
          :loading="simRunning === opt.key"
          :disabled="simRunning !== null || (simSelected.length > 0 && !TARGETABLE.has(opt.key))"
          @click="runSim(opt.key)"
        >
          {{ $t(opt.labelKey) }}
        </AppButton>
      </div>
      <p v-if="simMsg" class="mt-3 text-sm text-ink">{{ simMsg }}</p>
    </Modal>
  </div>
</template>
