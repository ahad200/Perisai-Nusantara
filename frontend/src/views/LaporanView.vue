<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import Panel from "@/components/ui/Panel.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import SkeletonRow from "@/components/ui/SkeletonRow.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import AppButton from "@/components/ui/AppButton.vue";
import { apiFetch, ApiError } from "@/lib/api";
import { formatWIB } from "@/lib/time";
import { useAuthStore } from "@/stores/auth";

interface Report {
  id: number; code: string; kind: string; title: string; status: string;
  summary: string; generated_by: string; approved_by: string | null; created_at: string;
}
interface Schedule {
  id: number; name: string; kind: string; cadence: string; enabled: boolean;
  recipient_role: string; next_run_at: string; last_run_at: string | null;
}

const auth = useAuthStore();
const canGenerate = computed(() => auth.can("report:generate"));
const canApprove = computed(() => auth.can("report:approve"));
const canManage = computed(() => auth.can("report:manage"));

const loading = ref(true);
const error = ref<string | null>(null);
const busy = ref(false);
const msg = ref<string | null>(null);
const reports = ref<Report[]>([]);
const schedules = ref<Schedule[]>([]);
const newKind = ref("daily");
const schKind = ref("daily");
const schCadence = ref("daily");

const KINDS = [
  { v: "daily", l: "SOC Harian" },
  { v: "weekly", l: "SOC Mingguan" },
  { v: "monthly", l: "SOC Bulanan" },
  { v: "executive", l: "Eksekutif" },
  { v: "compliance", l: "Kepatuhan" },
];

async function load() {
  loading.value = true;
  error.value = null;
  try {
    reports.value = await apiFetch<Report[]>("/reports");
    schedules.value = await apiFetch<Schedule[]>("/reports/schedules");
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Gagal memuat laporan";
  } finally {
    loading.value = false;
  }
}

async function generate() {
  busy.value = true; msg.value = null;
  try {
    const r = await apiFetch<Report>("/reports", { method: "POST", body: { kind: newKind.value } });
    msg.value = `Laporan ${r.code} dibuat sebagai DRAF. Tinjau lalu setujui sebelum kirim eksternal.`;
    await load();
  } catch (e) {
    msg.value = e instanceof ApiError ? e.message : "Gagal membuat laporan";
  } finally {
    busy.value = false;
  }
}

async function approve(r: Report) {
  busy.value = true; msg.value = null;
  try {
    await apiFetch(`/reports/${r.id}/approve`, { method: "POST" });
    msg.value = `Laporan ${r.code} disetujui.`;
    await load();
  } catch (e) {
    msg.value = e instanceof ApiError ? e.message : "Gagal menyetujui";
  } finally {
    busy.value = false;
  }
}

// PDF butuh header Authorization → ambil sebagai blob, buka di tab baru.
async function openPdf(r: Report) {
  msg.value = null;
  try {
    const base = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api";
    const res = await fetch(`${base}/reports/${r.id}/pdf`, {
      headers: auth.token ? { Authorization: `Bearer ${auth.token}` } : {},
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (e) {
    msg.value = e instanceof Error ? `Gagal membuka PDF: ${e.message}` : "Gagal membuka PDF";
  }
}

async function createSchedule() {
  busy.value = true; msg.value = null;
  try {
    await apiFetch("/reports/schedules", {
      method: "POST",
      body: { kind: schKind.value, cadence: schCadence.value },
    });
    msg.value = "Jadwal dibuat.";
    await load();
  } catch (e) {
    msg.value = e instanceof ApiError ? e.message : "Gagal membuat jadwal";
  } finally {
    busy.value = false;
  }
}

async function runDue() {
  busy.value = true; msg.value = null;
  try {
    const r = await apiFetch<{ ran: number; reports: string[] }>("/reports/schedules/run-due", { method: "POST" });
    msg.value = r.ran ? `${r.ran} laporan dihasilkan: ${r.reports.join(", ")}` : "Tidak ada jadwal jatuh tempo.";
    await load();
  } catch (e) {
    msg.value = e instanceof ApiError ? e.message : "Gagal menjalankan jadwal";
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-lg font-semibold text-ink">Laporan</h1>
        <p class="text-xs text-ink-dim">ELANG-6 · template deterministik. Laporan eksternal wajib disetujui manusia.</p>
      </div>
      <AppButton size="sm" variant="ghost" @click="load">Muat ulang</AppButton>
    </div>

    <p v-if="msg" class="rounded border border-edge bg-graphite-raised px-3 py-2 text-sm text-ink-muted">{{ msg }}</p>

    <Panel v-if="canGenerate" title="Buat laporan">
      <div class="flex flex-wrap items-center gap-2">
        <select v-model="newKind" class="rounded border border-edge bg-graphite-raised px-2 py-1.5 text-sm text-ink">
          <option v-for="k in KINDS" :key="k.v" :value="k.v">{{ k.l }}</option>
        </select>
        <AppButton size="sm" variant="primary" :loading="busy" @click="generate">Hasilkan (draf)</AppButton>
        <span class="text-xs text-ink-dim">Laporan insiden dibuat dari halaman Insiden.</span>
      </div>
    </Panel>

    <div v-if="loading" class="space-y-2"><SkeletonRow v-for="i in 5" :key="i" /></div>
    <EmptyState v-else-if="error" :message="error"><template #action><AppButton size="sm" @click="load">{{ $t("common.retry") }}</AppButton></template></EmptyState>

    <template v-else>
      <Panel title="Arsip laporan">
        <table v-if="reports.length" class="w-full text-sm">
          <thead class="text-left text-xs text-ink-dim">
            <tr>
              <th class="py-1">Kode</th><th class="py-1">Judul</th><th class="py-1">Jenis</th>
              <th class="py-1">Status</th><th class="py-1">Dibuat</th><th class="py-1 text-right">Aksi</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in reports" :key="r.id" class="border-t border-edge/50 align-top">
              <td class="py-1.5 font-mono text-ink">{{ r.code }}</td>
              <td class="py-1.5 text-ink-muted">
                <div class="text-ink">{{ r.title }}</div>
                <div class="text-xs text-ink-dim">{{ r.summary }}</div>
              </td>
              <td class="py-1.5 text-ink-muted">{{ r.kind }}</td>
              <td class="py-1.5">
                <StatusBadge :tone="r.status === 'approved' ? 'ok' : 'warn'">
                  {{ r.status === 'approved' ? 'disetujui' : 'draf' }}
                </StatusBadge>
              </td>
              <td class="py-1.5 font-mono text-xs text-ink-dim">{{ formatWIB(r.created_at) }}</td>
              <td class="py-1.5">
                <div class="flex justify-end gap-1.5">
                  <AppButton size="sm" variant="ghost" @click="openPdf(r)">PDF</AppButton>
                  <AppButton
                    v-if="canApprove && r.status !== 'approved'"
                    size="sm" variant="primary" :loading="busy" @click="approve(r)"
                  >Setujui</AppButton>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-else message="Belum ada laporan" hint="Buat laporan untuk mulai." />
      </Panel>

      <Panel title="Jadwal laporan otomatis">
        <template #actions>
          <AppButton v-if="canManage" size="sm" variant="ghost" :loading="busy" @click="runDue">Jalankan yang jatuh tempo</AppButton>
        </template>
        <div v-if="canManage" class="mb-3 flex flex-wrap items-center gap-2 border-b border-edge pb-3">
          <select v-model="schKind" class="rounded border border-edge bg-graphite-raised px-2 py-1.5 text-sm text-ink">
            <option v-for="k in KINDS" :key="k.v" :value="k.v">{{ k.l }}</option>
          </select>
          <select v-model="schCadence" class="rounded border border-edge bg-graphite-raised px-2 py-1.5 text-sm text-ink">
            <option value="daily">Harian</option>
            <option value="weekly">Mingguan</option>
            <option value="monthly">Bulanan</option>
          </select>
          <AppButton size="sm" :loading="busy" @click="createSchedule">Tambah jadwal</AppButton>
        </div>
        <table v-if="schedules.length" class="w-full text-sm">
          <thead class="text-left text-xs text-ink-dim">
            <tr><th class="py-1">Nama</th><th class="py-1">Jenis</th><th class="py-1">Irama</th><th class="py-1">Penerima</th><th class="py-1">Berikutnya</th></tr>
          </thead>
          <tbody>
            <tr v-for="s in schedules" :key="s.id" class="border-t border-edge/50">
              <td class="py-1 text-ink">{{ s.name }}</td>
              <td class="py-1 text-ink-muted">{{ s.kind }}</td>
              <td class="py-1 text-ink-muted">{{ s.cadence }}</td>
              <td class="py-1 font-mono text-ink-dim">{{ s.recipient_role }}</td>
              <td class="py-1 font-mono text-xs text-ink-dim">{{ formatWIB(s.next_run_at) }}</td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-else message="Belum ada jadwal" />
      </Panel>
    </template>
  </div>
</template>
