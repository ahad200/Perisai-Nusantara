<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import Panel from "@/components/ui/Panel.vue";
import SkeletonRow from "@/components/ui/SkeletonRow.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import SeverityBadge from "@/components/ui/SeverityBadge.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import AppButton from "@/components/ui/AppButton.vue";
import Modal from "@/components/ui/Modal.vue";
import { apiFetch, ApiError } from "@/lib/api";
import { formatWIB } from "@/lib/time";
import { useAuthStore } from "@/stores/auth";
import { useI18n } from "vue-i18n";

type Sev = "critical" | "high" | "medium" | "low" | "info";
interface Technique { technique: string; name: string | null }
interface Incident {
  id: number;
  incident_code: string;
  title: string;
  summary: string;
  severity: string;
  status: string;
  assignee: string | null;
  asset_id: number | null;
  host: string | null;
  techniques: Technique[];
  alert_count: number;
  first_event_ts: string | null;
  last_event_ts: string | null;
  updated_at: string;
}
interface AlertRow {
  id: number; rule_code: string; severity: string; technique: string | null;
  technique_name: string | null; host: string | null; title: string; status: string;
  event_count: number; last_event_ts: string | null;
}
interface Note { id: number; author: string; kind: string; body: string; created_at: string }
interface IncidentDetail extends Incident { alerts: AlertRow[]; notes: Note[] }
interface IncidentPage { items: Incident[]; total: number }

const { t } = useI18n();
const auth = useAuthStore();
const canManage = computed(() => auth.can("incident:manage"));
const canExecute = computed(() => auth.can("soar:execute"));
const canReport = computed(() => auth.can("report:generate"));
const runMsg = ref<string | null>(null);

const items = ref<Incident[]>([]);
const total = ref(0);
const loading = ref(true);
const error = ref<string | null>(null);
const busy = ref(false);

const severity = ref("");
const status = ref("");
const activeOnly = ref(true);

const SEVERITIES = ["critical", "high", "medium", "low", "info"];
const STATUSES = ["open", "investigating", "contained", "closed"];

function statusTone(s: string): "ok" | "warn" | "danger" | "muted" {
  if (s === "open") return "danger";
  if (s === "investigating") return "warn";
  if (s === "contained") return "ok";
  return "muted"; // closed
}
function statusLabel(s: string): string {
  return {
    open: t("incident.stOpen"), investigating: t("incident.stInvestigating"),
    contained: t("incident.stContained"), closed: t("incident.stClosed"),
  }[s] ?? s;
}

async function load() {
  loading.value = true;
  error.value = null;
  const p = new URLSearchParams();
  if (severity.value) p.set("severity", severity.value);
  if (status.value) p.set("status", status.value);
  if (activeOnly.value) p.set("active", "true");
  try {
    const page = await apiFetch<IncidentPage>(`/incidents?${p.toString()}`);
    items.value = page.items;
    total.value = page.total;
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Gagal memuat";
  } finally {
    loading.value = false;
  }
}

async function runCorrelate() {
  busy.value = true;
  try {
    await apiFetch("/incidents/correlate", { method: "POST" });
    await load();
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Gagal menjalankan korelasi";
  } finally {
    busy.value = false;
  }
}

// --- Detail + case management ---
const detail = ref<IncidentDetail | null>(null);
const detailOpen = ref(false);
const noteBody = ref("");
const statusDraft = ref("");

async function openDetail(id: number) {
  detailOpen.value = true;
  detail.value = null;
  runMsg.value = null;
  detail.value = await apiFetch<IncidentDetail>(`/incidents/${id}`);
  statusDraft.value = detail.value.status;
}

async function refreshDetail() {
  if (detail.value) detail.value = await apiFetch<IncidentDetail>(`/incidents/${detail.value.id}`);
  await load();
}

async function assign() {
  if (!detail.value) return;
  await apiFetch(`/incidents/${detail.value.id}/assign`, { method: "POST", body: {} });
  await refreshDetail();
}
async function changeStatus() {
  if (!detail.value || statusDraft.value === detail.value.status) return;
  await apiFetch(`/incidents/${detail.value.id}/status`, { method: "POST", body: { status: statusDraft.value } });
  await refreshDetail();
}
async function addNote() {
  if (!detail.value || !noteBody.value.trim()) return;
  await apiFetch(`/incidents/${detail.value.id}/notes`, { method: "POST", body: { body: noteBody.value.trim() } });
  noteBody.value = "";
  await refreshDetail();
}

async function runPlaybook(mode: "auto" | "dry_run") {
  if (!detail.value) return;
  runMsg.value = null;
  try {
    const r = await apiFetch<{ id: number; status: string; playbook_code: string }>(
      "/soar/run", { method: "POST", body: { incident_id: detail.value.id, mode } },
    );
    runMsg.value = `${t("incident.runStarted")}: ${r.playbook_code} → ${r.status}`;
  } catch (e) {
    runMsg.value = e instanceof ApiError ? e.message : "Gagal";
  }
}

async function generateReport() {
  if (!detail.value) return;
  runMsg.value = null;
  try {
    const r = await apiFetch<{ code: string }>(
      "/reports", { method: "POST", body: { kind: "incident", incident_id: detail.value.id } },
    );
    runMsg.value = `Laporan insiden ${r.code} dibuat (draf) — tinjau di halaman Laporan.`;
  } catch (e) {
    runMsg.value = e instanceof ApiError ? e.message : "Gagal";
  }
}

function noteTone(kind: string): "ok" | "warn" | "danger" | "muted" {
  if (kind === "status") return "warn";
  if (kind === "assign") return "ok";
  if (kind === "system") return "muted";
  return "muted";
}

onMounted(load);
watch([severity, status, activeOnly], load);
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h1 class="text-lg font-semibold text-ink">{{ $t("incident.title") }}</h1>
      <AppButton v-if="canManage" size="sm" variant="primary" :loading="busy" @click="runCorrelate">
        {{ $t("incident.correlate") }}
      </AppButton>
    </div>

    <div class="flex flex-wrap items-center gap-3">
      <select v-model="severity" class="h-9 rounded border border-edge bg-graphite-base px-2.5 text-sm text-ink focus:border-accent">
        <option value="">{{ t("incident.allSeverity") }}</option>
        <option v-for="s in SEVERITIES" :key="s" :value="s">{{ s }}</option>
      </select>
      <select v-model="status" class="h-9 rounded border border-edge bg-graphite-base px-2.5 text-sm text-ink focus:border-accent">
        <option value="">{{ t("incident.allStatus") }}</option>
        <option v-for="s in STATUSES" :key="s" :value="s">{{ statusLabel(s) }}</option>
      </select>
      <label class="flex items-center gap-1.5 text-sm text-ink-muted">
        <input v-model="activeOnly" type="checkbox" class="accent-[var(--accent)]" />
        {{ t("incident.activeOnly") }}
      </label>
    </div>

    <SkeletonRow v-if="loading" :rows="8" />
    <Panel v-else-if="error">
      <EmptyState :message="error">
        <template #action><AppButton size="sm" @click="load">{{ $t("common.retry") }}</AppButton></template>
      </EmptyState>
    </Panel>
    <EmptyState v-else-if="items.length === 0" :message="$t('incident.empty')" />

    <div v-else class="overflow-x-auto rounded border border-edge">
      <table class="w-full border-collapse text-sm">
        <thead>
          <tr class="border-b border-edge bg-graphite-raised text-left text-xs uppercase tracking-wide text-ink-muted">
            <th class="px-3 py-2">{{ t("incident.severity") }}</th>
            <th class="px-3 py-2">{{ t("incident.code") }}</th>
            <th class="px-3 py-2">{{ t("incident.host") }}</th>
            <th class="px-3 py-2">{{ t("incident.techniques") }}</th>
            <th class="px-3 py-2 text-right">{{ t("incident.alerts") }}</th>
            <th class="px-3 py-2">{{ t("incident.status") }}</th>
            <th class="px-3 py-2">{{ t("incident.assignee") }}</th>
            <th class="px-3 py-2">{{ t("incident.updated") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="inc in items"
            :key="inc.id"
            class="cursor-pointer border-b border-edge/60 last:border-0 hover:bg-graphite-raised/50"
            @click="openDetail(inc.id)"
          >
            <td class="px-3 py-1.5"><SeverityBadge :severity="(inc.severity as Sev)" /></td>
            <td class="px-3 py-1.5 font-mono text-xs text-ink">{{ inc.incident_code }}</td>
            <td class="px-3 py-1.5 font-mono text-ink">{{ inc.host ?? "—" }}</td>
            <td class="px-3 py-1.5">
              <span class="flex flex-wrap gap-1">
                <span
                  v-for="tech in inc.techniques"
                  :key="tech.technique"
                  class="rounded border border-edge bg-graphite-base px-1.5 py-0.5 font-mono text-[11px] text-ink-muted"
                  :title="tech.name ?? ''"
                >{{ tech.technique }}</span>
                <span v-if="inc.techniques.length === 0" class="text-ink-dim">—</span>
              </span>
            </td>
            <td class="px-3 py-1.5 text-right font-mono tnum text-ink-muted">{{ inc.alert_count }}</td>
            <td class="px-3 py-1.5"><StatusBadge :tone="statusTone(inc.status)">{{ statusLabel(inc.status) }}</StatusBadge></td>
            <td class="px-3 py-1.5 text-ink-muted">{{ inc.assignee ?? "—" }}</td>
            <td class="px-3 py-1.5 font-mono text-xs text-ink-dim">{{ formatWIB(inc.updated_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="items.length" class="text-xs text-ink-dim">{{ total }} {{ t("incident.title").toLowerCase() }}</div>

    <!-- Detail insiden + case management -->
    <Modal v-model:open="detailOpen" :title="t('incident.detail')">
      <div v-if="detail" class="space-y-3">
        <div class="flex flex-wrap items-center gap-2">
          <SeverityBadge :severity="(detail.severity as Sev)" />
          <span class="font-mono text-xs text-ink">{{ detail.incident_code }}</span>
          <StatusBadge :tone="statusTone(detail.status)">{{ statusLabel(detail.status) }}</StatusBadge>
        </div>
        <div class="font-medium text-ink">{{ detail.title }}</div>

        <dl class="grid grid-cols-[110px_1fr] gap-x-3 gap-y-1 text-sm">
          <dt class="text-ink-muted">{{ t("incident.host") }}</dt>
          <dd class="font-mono text-ink">{{ detail.host ?? "—" }}</dd>
          <dt class="text-ink-muted">{{ t("incident.assignee") }}</dt>
          <dd class="text-ink">{{ detail.assignee ?? "—" }}</dd>
          <dt class="text-ink-muted">{{ t("incident.summary") }}</dt>
          <dd class="text-ink-muted">{{ detail.summary }}</dd>
          <dt class="text-ink-muted">{{ t("incident.techniques") }}</dt>
          <dd class="flex flex-wrap gap-1">
            <span
              v-for="tech in detail.techniques"
              :key="tech.technique"
              class="rounded border border-edge bg-graphite-base px-1.5 py-0.5 font-mono text-[11px] text-ink-muted"
            >{{ tech.technique }}<span v-if="tech.name" class="text-ink-dim"> · {{ tech.name }}</span></span>
            <span v-if="detail.techniques.length === 0" class="text-ink-dim">—</span>
          </dd>
        </dl>

        <!-- Alert terkorelasi -->
        <div>
          <div class="mb-1 text-xs text-ink-muted">{{ t("incident.linkedAlerts") }} ({{ detail.alerts.length }})</div>
          <div class="max-h-44 overflow-auto rounded border border-edge">
            <table class="w-full text-xs">
              <tbody>
                <tr v-for="a in detail.alerts" :key="a.id" class="border-b border-edge/60 last:border-0">
                  <td class="px-2 py-1"><SeverityBadge :severity="(a.severity as Sev)" /></td>
                  <td class="px-2 py-1 font-mono text-ink-muted">{{ a.rule_code }}</td>
                  <td class="px-2 py-1 font-mono text-ink">{{ a.technique ?? "—" }}</td>
                  <td class="px-2 py-1 text-ink-muted">{{ a.title }}</td>
                  <td class="px-2 py-1 text-right font-mono tnum text-ink-dim">{{ a.event_count }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Linimasa kasus -->
        <div>
          <div class="mb-1 text-xs text-ink-muted">{{ t("incident.timeline") }}</div>
          <div v-if="detail.notes.length === 0" class="text-xs text-ink-dim">{{ t("incident.noNotes") }}</div>
          <ul v-else class="space-y-1.5">
            <li v-for="n in detail.notes" :key="n.id" class="flex gap-2 text-xs">
              <StatusBadge :tone="noteTone(n.kind)">{{ n.kind }}</StatusBadge>
              <div class="flex-1">
                <div class="text-ink">{{ n.body }}</div>
                <div class="font-mono text-ink-dim">{{ n.author }} · {{ formatWIB(n.created_at) }}</div>
              </div>
            </li>
          </ul>
        </div>

        <!-- Aksi case management -->
        <div v-if="canManage" class="space-y-2 rounded border border-edge bg-graphite-base p-2">
          <div class="flex flex-wrap items-center gap-2">
            <select v-model="statusDraft" class="h-8 rounded border border-edge bg-graphite-base px-2 text-xs text-ink focus:border-accent">
              <option v-for="s in STATUSES" :key="s" :value="s">{{ statusLabel(s) }}</option>
            </select>
            <AppButton size="sm" variant="default" @click="changeStatus">{{ t("incident.changeStatus") }}</AppButton>
          </div>
          <div class="flex gap-2">
            <textarea
              v-model="noteBody"
              rows="2"
              :placeholder="t('incident.notePlaceholder')"
              class="flex-1 rounded border border-edge bg-graphite-base px-2 py-1 text-xs text-ink focus:border-accent"
            ></textarea>
            <AppButton size="sm" variant="default" @click="addNote">{{ t("incident.addNote") }}</AppButton>
          </div>
        </div>

        <p v-if="runMsg" class="font-mono text-xs text-accent">{{ runMsg }}</p>
      </div>
      <SkeletonRow v-else :rows="5" />

      <template v-if="(canManage || canExecute || canReport) && detail" #footer>
        <AppButton v-if="canManage" size="sm" variant="primary" @click="assign">{{ t("incident.assign") }}</AppButton>
        <AppButton v-if="canExecute" size="sm" variant="default" @click="runPlaybook('auto')">{{ t("incident.runPlaybook") }}</AppButton>
        <AppButton v-if="canExecute" size="sm" variant="ghost" @click="runPlaybook('dry_run')">{{ t("incident.dryRun") }}</AppButton>
        <AppButton v-if="canReport" size="sm" variant="ghost" @click="generateReport">Buat laporan</AppButton>
      </template>
    </Modal>
  </div>
</template>
