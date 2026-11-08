<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, ref, watch } from "vue";
import Panel from "@/components/ui/Panel.vue";
import SkeletonRow from "@/components/ui/SkeletonRow.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import SeverityBadge from "@/components/ui/SeverityBadge.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import CritBadge from "@/components/ui/CritBadge.vue";
import AppButton from "@/components/ui/AppButton.vue";
import Modal from "@/components/ui/Modal.vue";
import { apiFetch, ApiError } from "@/lib/api";
import { formatWIB } from "@/lib/time";
import { useAuthStore } from "@/stores/auth";
import { useI18n } from "vue-i18n";

type Sev = "critical" | "high" | "medium" | "low" | "info";
interface Alert {
  id: number;
  rule_code: string;
  severity: string;
  technique: string | null;
  technique_name: string | null;
  asset_id: number | null;
  asset_criticality: string | null;
  host: string | null;
  title: string;
  explanation: string;
  event_count: number;
  status: string;
  assignee: string | null;
  last_event_ts: string | null;
  anomaly_score: number | null;
}
interface EventRow {
  id: number; ts: string; source_type: string; action: string; host: string | null; outcome: string;
}
interface Feature {
  name: string; label: string; value: number; baseline_mean: number; z: number;
}
interface AlertDetail extends Alert {
  event_ids: number[];
  events: EventRow[];
  features: { score: number; dst_ip?: string; model?: string; top?: string[]; features: Feature[] } | null;
}
interface AlertPage { items: Alert[]; total: number; }

const { t } = useI18n();
const auth = useAuthStore();
const canTriage = computed(() => auth.can("alert:triage"));

const items = ref<Alert[]>([]);
const total = ref(0);
const loading = ref(true);
const error = ref<string | null>(null);
const busy = ref(false);
const cursor = ref(0);

const severity = ref("");
const status = ref("");
const mineOnly = ref(false);

const SEVERITIES = ["critical", "high", "medium", "low", "info"];
const STATUSES = ["new", "assigned", "escalated", "closed_fp", "closed_resolved"];

function statusTone(s: string): "ok" | "warn" | "danger" | "muted" {
  if (s === "assigned") return "ok";
  if (s === "escalated") return "warn";
  if (s === "closed_resolved") return "ok";
  return "muted";
}

async function load() {
  loading.value = true;
  error.value = null;
  const p = new URLSearchParams();
  if (severity.value) p.set("severity", severity.value);
  if (status.value) p.set("status", status.value);
  if (mineOnly.value && auth.user) p.set("assignee", auth.user.username);
  try {
    const page = await apiFetch<AlertPage>(`/alerts?${p.toString()}`);
    items.value = page.items;
    total.value = page.total;
    if (cursor.value >= items.value.length) cursor.value = Math.max(0, items.value.length - 1);
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Gagal memuat";
  } finally {
    loading.value = false;
  }
}

async function runDetection() {
  busy.value = true;
  try {
    await apiFetch("/detection/run", { method: "POST" });
    await load();
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Gagal menjalankan deteksi";
  } finally {
    busy.value = false;
  }
}
async function seedRules() {
  busy.value = true;
  try {
    await apiFetch("/detection/rules/seed", { method: "POST" });
  } finally {
    busy.value = false;
  }
}

// --- Triage actions ---
async function act(id: number, path: string, body?: unknown) {
  if (!canTriage.value) return;
  await apiFetch(`/alerts/${id}/${path}`, { method: "POST", body: body ?? {} });
  await load();
  if (detailOpen.value) await openDetail(id);
}
const assign = (id: number) => act(id, "assign", {});
const escalate = (id: number) => act(id, "escalate");
const closeFp = (id: number) => act(id, "close", { reason: "fp" });

// --- Detail ---
const detail = ref<AlertDetail | null>(null);
const detailOpen = ref(false);
async function openDetail(id: number) {
  detailOpen.value = true;
  detail.value = await apiFetch<AlertDetail>(`/alerts/${id}`);
}

// --- Keyboard navigation (j/k/a/e/x/Enter) ---
function moveCursor(delta: number) {
  if (items.value.length === 0) return;
  cursor.value = Math.min(items.value.length - 1, Math.max(0, cursor.value + delta));
  nextTick(() => {
    document.querySelector(`[data-alert-row="${cursor.value}"]`)?.scrollIntoView({ block: "nearest" });
  });
}
function onKey(e: KeyboardEvent) {
  const tag = (e.target as HTMLElement)?.tagName;
  if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
  if (detailOpen.value) return;
  const cur = items.value[cursor.value];
  switch (e.key) {
    case "j": moveCursor(1); break;
    case "k": moveCursor(-1); break;
    case "a": if (cur) assign(cur.id); break;
    case "e": if (cur) escalate(cur.id); break;
    case "x": if (cur) closeFp(cur.id); break;
    case "Enter": if (cur) openDetail(cur.id); break;
    default: return;
  }
  e.preventDefault();
}

onMounted(() => { load(); window.addEventListener("keydown", onKey); });
onBeforeUnmount(() => window.removeEventListener("keydown", onKey));
watch([severity, status, mineOnly], () => { cursor.value = 0; load(); });
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h1 class="text-lg font-semibold text-ink">{{ $t("alert.title") }}</h1>
      <div class="flex gap-2">
        <AppButton v-if="auth.can('detect:manage')" size="sm" variant="default" :loading="busy" @click="seedRules">
          {{ $t("alert.seedRules") }}
        </AppButton>
        <AppButton v-if="auth.can('detect:run')" size="sm" variant="primary" :loading="busy" @click="runDetection">
          {{ $t("alert.run") }}
        </AppButton>
      </div>
    </div>

    <p class="font-mono text-xs text-ink-dim">{{ $t("alert.shortcuts") }}</p>

    <div class="flex flex-wrap items-center gap-3">
      <select v-model="severity" class="h-9 rounded border border-edge bg-graphite-base px-2.5 text-sm text-ink focus:border-accent">
        <option value="">{{ t("alert.allSeverity") }}</option>
        <option v-for="s in SEVERITIES" :key="s" :value="s">{{ s }}</option>
      </select>
      <select v-model="status" class="h-9 rounded border border-edge bg-graphite-base px-2.5 text-sm text-ink focus:border-accent">
        <option value="">{{ t("alert.allStatus") }}</option>
        <option v-for="s in STATUSES" :key="s" :value="s">{{ s }}</option>
      </select>
      <label class="flex items-center gap-1.5 text-sm text-ink-muted">
        <input v-model="mineOnly" type="checkbox" class="accent-[var(--accent)]" />
        {{ t("alert.mineOnly") }}
      </label>
    </div>

    <SkeletonRow v-if="loading" :rows="10" />
    <Panel v-else-if="error">
      <EmptyState :message="error">
        <template #action><AppButton size="sm" @click="load">{{ $t("common.retry") }}</AppButton></template>
      </EmptyState>
    </Panel>
    <EmptyState v-else-if="items.length === 0" :message="$t('alert.empty')" />

    <div v-else class="overflow-x-auto rounded border border-edge">
      <table class="w-full border-collapse text-sm">
        <thead>
          <tr class="border-b border-edge bg-graphite-raised text-left text-xs uppercase tracking-wide text-ink-muted">
            <th class="px-3 py-2">{{ t("alert.severity") }}</th>
            <th class="px-3 py-2">{{ t("alert.time") }}</th>
            <th class="px-3 py-2">{{ t("alert.asset") }}</th>
            <th class="px-3 py-2">{{ t("alert.rule") }}</th>
            <th class="px-3 py-2">{{ t("alert.technique") }}</th>
            <th class="px-3 py-2 text-right">{{ t("alert.events") }}</th>
            <th class="px-3 py-2">{{ t("alert.status") }}</th>
            <th class="px-3 py-2">{{ t("alert.assignee") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(a, i) in items"
            :key="a.id"
            :data-alert-row="i"
            :class="[
              'cursor-pointer border-b border-edge/60 last:border-0',
              i === cursor ? 'bg-graphite-raised ring-1 ring-inset ring-accent/60' : 'hover:bg-graphite-raised/50',
            ]"
            @click="cursor = i"
            @dblclick="openDetail(a.id)"
          >
            <td class="px-3 py-1.5"><SeverityBadge :severity="(a.severity as Sev)" /></td>
            <td class="px-3 py-1.5 font-mono text-xs text-ink-muted">{{ a.last_event_ts ? formatWIB(a.last_event_ts) : "—" }}</td>
            <td class="px-3 py-1.5">
              <span class="inline-flex items-center gap-1.5">
                <CritBadge :level="a.asset_criticality" />
                <span class="font-mono text-ink">{{ a.host ?? "—" }}</span>
              </span>
            </td>
            <td class="px-3 py-1.5 font-mono text-xs text-ink-muted">{{ a.rule_code }}</td>
            <td class="px-3 py-1.5 font-mono text-xs text-ink">
              {{ a.technique ?? "—" }}<span v-if="a.technique_name" class="text-ink-dim"> · {{ a.technique_name }}</span>
              <span v-if="a.anomaly_score != null" class="text-ink-dim"> · {{ t("alert.anomalyScore").toLowerCase() }} {{ a.anomaly_score.toFixed(2) }}</span>
            </td>
            <td class="px-3 py-1.5 text-right font-mono tnum text-ink-muted">{{ a.event_count }}</td>
            <td class="px-3 py-1.5"><StatusBadge :tone="statusTone(a.status)">{{ a.status }}</StatusBadge></td>
            <td class="px-3 py-1.5 text-ink-muted">{{ a.assignee ?? "—" }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="items.length" class="text-xs text-ink-dim">{{ total }} alert</div>

    <!-- Detail alert -->
    <Modal v-model:open="detailOpen" :title="t('alert.detail')">
      <div v-if="detail" class="space-y-3">
        <div class="flex items-center gap-2">
          <SeverityBadge :severity="(detail.severity as Sev)" />
          <span class="font-mono text-xs text-ink-muted">{{ detail.rule_code }}</span>
          <span class="font-mono text-xs text-ink">{{ detail.technique ?? "" }} {{ detail.technique_name ?? "" }}</span>
        </div>
        <div class="font-medium text-ink">{{ detail.title }}</div>
        <dl class="grid grid-cols-[110px_1fr] gap-x-3 gap-y-1 text-sm">
          <dt class="text-ink-muted">{{ t("alert.asset") }}</dt>
          <dd class="font-mono text-ink"><CritBadge :level="detail.asset_criticality" /> {{ detail.host ?? "—" }}</dd>
          <dt class="text-ink-muted">{{ t("alert.status") }}</dt>
          <dd><StatusBadge :tone="statusTone(detail.status)">{{ detail.status }}</StatusBadge></dd>
          <dt class="text-ink-muted">{{ t("alert.assignee") }}</dt>
          <dd class="text-ink">{{ detail.assignee ?? "—" }}</dd>
          <dt class="text-ink-muted">{{ t("alert.explanation") }}</dt>
          <dd class="text-ink-muted">{{ detail.explanation }}</dd>
        </dl>

        <!-- Penjelasan ELANG-1 (anomali) -->
        <div v-if="detail.features" class="rounded border border-edge bg-graphite-base p-2">
          <div class="mb-1 flex items-center justify-between">
            <span class="font-mono text-xs uppercase text-ink">{{ t("alert.anomaly") }}</span>
            <span class="font-mono text-xs text-ink-muted">
              {{ t("alert.anomalyScore") }}: <span class="text-ink">{{ detail.features.score.toFixed(3) }}</span>
            </span>
          </div>
          <div class="mb-1 text-xs text-ink-muted">{{ t("alert.features") }}</div>
          <table class="w-full text-xs">
            <thead>
              <tr class="text-left text-ink-dim">
                <th class="py-0.5 pr-2 font-medium"></th>
                <th class="py-0.5 pr-2 text-right font-medium">{{ t("alert.featureValue") }}</th>
                <th class="py-0.5 pr-2 text-right font-medium">{{ t("alert.baseline") }}</th>
                <th class="py-0.5 text-right font-medium">{{ t("alert.deviation") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(f, i) in detail.features.features"
                :key="f.name"
                :class="['border-t border-edge/50', i < 3 ? 'text-ink' : 'text-ink-muted']"
              >
                <td class="py-0.5 pr-2">{{ f.label }}</td>
                <td class="py-0.5 pr-2 text-right font-mono tnum">{{ f.value }}</td>
                <td class="py-0.5 pr-2 text-right font-mono tnum text-ink-dim">{{ f.baseline_mean }}</td>
                <td class="py-0.5 text-right font-mono tnum">{{ f.z > 0 ? "+" : "" }}{{ f.z }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div>
          <div class="mb-1 text-xs text-ink-muted">{{ t("alert.linkedEvents") }} ({{ detail.event_ids.length }})</div>
          <div class="max-h-52 overflow-auto rounded border border-edge">
            <table class="w-full text-xs">
              <tbody>
                <tr v-for="ev in detail.events" :key="ev.id" class="border-b border-edge/60 last:border-0">
                  <td class="px-2 py-1 font-mono text-ink-dim">{{ formatWIB(ev.ts) }}</td>
                  <td class="px-2 py-1 font-mono text-ink-muted">{{ ev.source_type }}</td>
                  <td class="px-2 py-1 font-mono text-ink">{{ ev.action }}</td>
                  <td class="px-2 py-1 font-mono text-ink-muted">{{ ev.host }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <SkeletonRow v-else :rows="4" />

      <template v-if="canTriage && detail" #footer>
        <AppButton size="sm" variant="default" @click="assign(detail.id)">{{ t("alert.assign") }}</AppButton>
        <AppButton size="sm" variant="ghost" @click="escalate(detail.id)">{{ t("alert.escalate") }}</AppButton>
        <AppButton size="sm" variant="danger" @click="closeFp(detail.id)">{{ t("alert.closeFp") }}</AppButton>
      </template>
    </Modal>
  </div>
</template>
