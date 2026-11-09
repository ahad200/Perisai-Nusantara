<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
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
interface Approval {
  id: number; action: string; severity: string; criticality: string;
  required_tier: string; status: string; on_timeout: string;
  deadline: string | null; incident_id: number | null; run_id: number;
}
interface ActionExec {
  id: number; step_index: number; action: string; params: Record<string, unknown>;
  disruptive: boolean; reversible: boolean; decision_mode: string; decision_reason: string;
  status: string; rolled_back: boolean; approval_id: number | null;
}
interface Run {
  id: number; playbook_code: string; incident_id: number | null; mode: string;
  status: string; severity: string; criticality: string; host: string | null;
  summary: Record<string, unknown>; created_at: string;
}
interface RunDetail extends Run { actions: ActionExec[] }
interface Playbook {
  id: number; code: string; name: string; trigger_technique: string | null;
  status: string; owner: string; description: string;
  steps: { action: string; disruptive: boolean; pre_approved: boolean }[];
}
interface BreakGlass { id: number; activated_by: string; reason: string; expires_at: string }

const { t } = useI18n();
const auth = useAuthStore();
const canApprove = computed(() => auth.can("soar:approve"));
const canExecute = computed(() => auth.can("soar:execute"));
const canManage = computed(() => auth.can("soar:manage"));

const loading = ref(true);
const error = ref<string | null>(null);
const busy = ref(false);
const approvals = ref<Approval[]>([]);
const runs = ref<Run[]>([]);
const playbooks = ref<Playbook[]>([]);
const breakGlass = ref<BreakGlass | null>(null);

function actionTone(s: string): "ok" | "warn" | "danger" | "muted" {
  if (s === "executed") return "ok";
  if (s === "awaiting_approval") return "warn";
  if (s === "denied" || s === "failed") return "danger";
  return "muted";
}
function runTone(s: string): "ok" | "warn" | "danger" | "muted" {
  if (s === "completed") return "ok";
  if (s === "awaiting_approval") return "warn";
  if (s === "failed") return "danger";
  return "muted";
}

async function load() {
  loading.value = true;
  error.value = null;
  try {
    [approvals.value, runs.value, playbooks.value, breakGlass.value] = await Promise.all([
      apiFetch<Approval[]>("/soar/approvals?status=pending"),
      apiFetch<Run[]>("/soar/runs"),
      apiFetch<Playbook[]>("/soar/playbooks"),
      apiFetch<BreakGlass | null>("/soar/break-glass"),
    ]);
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Gagal memuat";
  } finally {
    loading.value = false;
  }
}

async function resolve(id: number, decision: "approve" | "deny") {
  busy.value = true;
  try {
    await apiFetch(`/soar/approvals/${id}/resolve`, { method: "POST", body: { decision } });
    await load();
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Gagal";
  } finally {
    busy.value = false;
  }
}

async function processTimeouts() {
  busy.value = true;
  try { await apiFetch("/soar/approvals/process-timeouts", { method: "POST" }); await load(); }
  finally { busy.value = false; }
}

async function seedPlaybooks() {
  busy.value = true;
  try { await apiFetch("/soar/playbooks/seed", { method: "POST" }); await load(); }
  finally { busy.value = false; }
}

// --- Run detail + rollback ---
const detail = ref<RunDetail | null>(null);
const detailOpen = ref(false);
async function openRun(id: number) {
  detailOpen.value = true;
  detail.value = null;
  detail.value = await apiFetch<RunDetail>(`/soar/runs/${id}`);
}
async function rollback() {
  if (!detail.value) return;
  await apiFetch(`/soar/runs/${detail.value.id}/rollback`, { method: "POST" });
  await openRun(detail.value.id);
  await load();
}

// --- Break-glass ---
const bgReason = ref("");
async function activateBreakGlass() {
  if (!bgReason.value.trim()) return;
  await apiFetch("/soar/break-glass", { method: "POST", body: { reason: bgReason.value.trim(), minutes: 30 } });
  bgReason.value = "";
  await load();
}

onMounted(load);
</script>

<template>
  <div class="space-y-5">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h1 class="text-lg font-semibold text-ink">{{ $t("soar.title") }}</h1>
      <div class="flex gap-2">
        <AppButton v-if="canManage" size="sm" variant="default" :loading="busy" @click="seedPlaybooks">
          {{ $t("soar.seedPlaybooks") }}
        </AppButton>
        <AppButton v-if="canApprove" size="sm" variant="default" :loading="busy" @click="processTimeouts">
          {{ $t("soar.processTimeouts") }}
        </AppButton>
      </div>
    </div>

    <!-- Break-glass banner -->
    <div
      v-if="breakGlass"
      class="rounded border border-amber-500/50 bg-amber-500/10 px-3 py-2 text-sm text-amber-300"
    >
      ⚠ {{ $t("soar.breakGlassActive") }} — {{ breakGlass.reason }}
      ({{ breakGlass.activated_by }}, s/d {{ formatWIB(breakGlass.expires_at) }})
    </div>

    <SkeletonRow v-if="loading" :rows="6" />
    <Panel v-else-if="error">
      <EmptyState :message="error">
        <template #action><AppButton size="sm" @click="load">{{ $t("common.retry") }}</AppButton></template>
      </EmptyState>
    </Panel>

    <template v-else>
      <!-- Approvals -->
      <section class="space-y-2">
        <h2 class="text-sm font-semibold uppercase tracking-wide text-ink-muted">{{ $t("soar.approvals") }}</h2>
        <EmptyState v-if="approvals.length === 0" :message="$t('soar.noApprovals')" />
        <div v-else class="overflow-x-auto rounded border border-edge">
          <table class="w-full border-collapse text-sm">
            <thead>
              <tr class="border-b border-edge bg-graphite-raised text-left text-xs uppercase tracking-wide text-ink-muted">
                <th class="px-3 py-2">{{ $t("soar.severity") }}</th>
                <th class="px-3 py-2">{{ $t("soar.criticality") }}</th>
                <th class="px-3 py-2">{{ $t("soar.action") }}</th>
                <th class="px-3 py-2">{{ $t("soar.tier") }}</th>
                <th class="px-3 py-2">{{ $t("soar.deadline") }}</th>
                <th class="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="a in approvals" :key="a.id" class="border-b border-edge/60 last:border-0">
                <td class="px-3 py-1.5"><SeverityBadge :severity="(a.severity as Sev)" /></td>
                <td class="px-3 py-1.5"><CritBadge :level="a.criticality" /></td>
                <td class="px-3 py-1.5 font-mono text-ink">{{ a.action }}</td>
                <td class="px-3 py-1.5 font-mono text-xs text-ink-muted">{{ a.required_tier }}</td>
                <td class="px-3 py-1.5 font-mono text-xs text-ink-dim">{{ a.deadline ? formatWIB(a.deadline) : "—" }}</td>
                <td class="px-3 py-1.5 text-right">
                  <div v-if="canApprove" class="flex justify-end gap-1.5">
                    <AppButton size="sm" variant="primary" @click="resolve(a.id, 'approve')">{{ $t("soar.approve") }}</AppButton>
                    <AppButton size="sm" variant="danger" @click="resolve(a.id, 'deny')">{{ $t("soar.deny") }}</AppButton>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Runs -->
      <section class="space-y-2">
        <h2 class="text-sm font-semibold uppercase tracking-wide text-ink-muted">{{ $t("soar.runs") }}</h2>
        <EmptyState v-if="runs.length === 0" :message="$t('soar.noRuns')" />
        <div v-else class="overflow-x-auto rounded border border-edge">
          <table class="w-full border-collapse text-sm">
            <thead>
              <tr class="border-b border-edge bg-graphite-raised text-left text-xs uppercase tracking-wide text-ink-muted">
                <th class="px-3 py-2">{{ $t("soar.status") }}</th>
                <th class="px-3 py-2">Playbook</th>
                <th class="px-3 py-2">{{ $t("soar.severity") }}</th>
                <th class="px-3 py-2">{{ $t("soar.criticality") }}</th>
                <th class="px-3 py-2">{{ $t("soar.mode") }}</th>
                <th class="px-3 py-2">{{ $t("soar.host") }}</th>
                <th class="px-3 py-2">Waktu</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in runs" :key="r.id"
                  class="cursor-pointer border-b border-edge/60 last:border-0 hover:bg-graphite-raised/50"
                  @click="openRun(r.id)">
                <td class="px-3 py-1.5"><StatusBadge :tone="runTone(r.status)">{{ r.status }}</StatusBadge></td>
                <td class="px-3 py-1.5 font-mono text-xs text-ink">{{ r.playbook_code }}</td>
                <td class="px-3 py-1.5"><SeverityBadge :severity="(r.severity as Sev)" /></td>
                <td class="px-3 py-1.5"><CritBadge :level="r.criticality" /></td>
                <td class="px-3 py-1.5 font-mono text-xs text-ink-muted">{{ r.mode }}</td>
                <td class="px-3 py-1.5 font-mono text-ink">{{ r.host ?? "—" }}</td>
                <td class="px-3 py-1.5 font-mono text-xs text-ink-dim">{{ formatWIB(r.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Playbook catalog + break-glass -->
      <section class="grid gap-4 md:grid-cols-2">
        <div class="space-y-2">
          <h2 class="text-sm font-semibold uppercase tracking-wide text-ink-muted">{{ $t("soar.playbooks") }}</h2>
          <div class="space-y-1.5">
            <div v-for="pb in playbooks" :key="pb.id" class="rounded border border-edge bg-graphite-base p-2">
              <div class="flex items-center justify-between">
                <span class="font-mono text-xs text-ink">{{ pb.code }}</span>
                <span class="font-mono text-[11px] text-ink-dim">{{ $t("soar.trigger") }}: {{ pb.trigger_technique ?? "—" }}</span>
              </div>
              <div class="text-sm text-ink-muted">{{ pb.name }}</div>
              <div class="mt-1 flex flex-wrap gap-1">
                <span v-for="(s, i) in pb.steps" :key="i"
                      class="rounded border border-edge px-1.5 py-0.5 font-mono text-[11px]"
                      :class="s.disruptive ? 'text-ink' : 'text-ink-muted'">
                  {{ s.action }}<span v-if="s.pre_approved" class="text-ink-dim"> ✓CAB</span>
                </span>
              </div>
            </div>
          </div>
        </div>

        <div v-if="canManage" class="space-y-2">
          <h2 class="text-sm font-semibold uppercase tracking-wide text-ink-muted">{{ $t("soar.breakGlass") }}</h2>
          <div class="space-y-2 rounded border border-edge bg-graphite-base p-3">
            <input v-model="bgReason" :placeholder="$t('soar.breakGlassReason')"
                   class="w-full rounded border border-edge bg-graphite-base px-2 py-1.5 text-sm text-ink focus:border-accent" />
            <AppButton size="sm" variant="danger" @click="activateBreakGlass">{{ $t("soar.activate") }} (30 {{ $t("soar.minutes") }})</AppButton>
          </div>
        </div>
      </section>
    </template>

    <!-- Run detail -->
    <Modal v-model:open="detailOpen" :title="t('soar.runDetail')">
      <div v-if="detail" class="space-y-3">
        <div class="flex flex-wrap items-center gap-2">
          <StatusBadge :tone="runTone(detail.status)">{{ detail.status }}</StatusBadge>
          <span class="font-mono text-xs text-ink">{{ detail.playbook_code }}</span>
          <SeverityBadge :severity="(detail.severity as Sev)" />
          <CritBadge :level="detail.criticality" />
          <span class="font-mono text-xs text-ink-muted">{{ detail.mode }}</span>
        </div>

        <div class="text-xs text-ink-muted">{{ t("soar.steps") }}</div>
        <ol class="space-y-2">
          <li v-for="a in detail.actions" :key="a.id" class="rounded border border-edge bg-graphite-base p-2">
            <div class="flex items-center justify-between">
              <span class="font-mono text-sm text-ink">{{ a.step_index + 1 }}. {{ a.action }}</span>
              <StatusBadge :tone="actionTone(a.status)">{{ a.status }}</StatusBadge>
            </div>
            <div class="mt-0.5 flex flex-wrap gap-2 font-mono text-[11px] text-ink-dim">
              <span>{{ a.decision_mode === 'auto' ? t('soar.auto') : t('soar.approval') }}</span>
              <span v-if="a.disruptive">· {{ t('soar.disruptive') }}</span>
              <span v-if="a.reversible">· {{ t('soar.reversible') }}</span>
              <span v-if="a.rolled_back">· rolled back</span>
            </div>
            <div class="mt-1 text-xs text-ink-muted">{{ a.decision_reason }}</div>
          </li>
        </ol>
      </div>
      <SkeletonRow v-else :rows="4" />

      <template v-if="canExecute && detail" #footer>
        <AppButton size="sm" variant="danger" @click="rollback">{{ t("soar.rollback") }}</AppButton>
      </template>
    </Modal>
  </div>
</template>
