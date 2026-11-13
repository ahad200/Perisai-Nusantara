<script setup lang="ts">
import { ref } from "vue";
import Panel from "@/components/ui/Panel.vue";
import AppButton from "@/components/ui/AppButton.vue";
import SeverityBadge from "@/components/ui/SeverityBadge.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import CritBadge from "@/components/ui/CritBadge.vue";
import TlpBadge from "@/components/ui/TlpBadge.vue";
import TextInput from "@/components/ui/TextInput.vue";
import Modal from "@/components/ui/Modal.vue";
import DataTable, { type Column } from "@/components/ui/DataTable.vue";
import SkeletonRow from "@/components/ui/SkeletonRow.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import OodaFlow from "@/components/ui/OodaFlow.vue";
import SegmentMap from "@/components/ui/SegmentMap.vue";
import type { Ooda, Segment } from "@/lib/types";

const sampleText = ref("10.14.22.7");
const otp = ref("");
const modalOpen = ref(false);

// Data simulasi realistis (bukan dummy generik) — PRD C.6.
const columns: Column[] = [
  { key: "severity", label: "Severity", width: "120px" },
  { key: "host", label: "Aset", mono: true },
  { key: "ip", label: "IP", mono: true },
  { key: "technique", label: "ATT&CK", mono: true },
];
const rows = [
  { severity: "critical", host: "cmd-core-01", ip: "10.14.22.7", technique: "T1486" },
  { severity: "high", host: "mail-gw-02", ip: "10.14.9.31", technique: "T1071" },
  { severity: "medium", host: "ws-anlst-114", ip: "10.20.3.88", technique: "T1110" },
  { severity: "low", host: "print-srv-05", ip: "10.20.7.12", technique: "T1046" },
] as const;

// OODA: insiden ransomware di aset K1 — aksi disruptif ditahan menunggu Commander.
const oodaSample: Ooda = {
  incident_id: 42, incident_code: "INC-20261113-0042", incident_status: "investigating",
  severity: "critical", criticality: "K1", current_phase: "decide",
  phases: [
    { key: "observe", state: "recorded", waiting_reason: null, items: [
      { ts: "2026-11-13T01:12:04Z", kind: "alert", ref: "ALERT-311", text: "SIG-T1110-01 · Brute force SSH ke cmd-core-01 (48 event)", status: "new", severity: "high" },
      { ts: "2026-11-13T01:27:40Z", kind: "alert", ref: "ALERT-318", text: "SIG-T1486-01 · Rename massal ekstensi .lockbit (212 event)", status: "new", severity: "critical" },
    ] },
    { key: "orient", state: "waiting", waiting_reason: "1 hipotesis atribusi belum divalidasi intel", items: [
      { ts: null, kind: "technique", ref: "T1110", text: "T1110 · Brute Force", status: null, severity: null },
      { ts: null, kind: "technique", ref: "T1486", text: "T1486 · Data Encrypted for Impact", status: null, severity: null },
      { ts: null, kind: "criticality", ref: "ASSET-1", text: "Kritikalitas aset cmd-core-01: K1", status: "K1", severity: null },
      { ts: "2026-11-13T01:31:02Z", kind: "attribution", ref: "HYP-7", text: "Hipotesis ELANG-3: kelompok ransomware-as-a-service (confidence low)", status: "proposed", severity: null },
    ] },
    { key: "decide", state: "waiting", waiting_reason: "1 approval menunggu keputusan", items: [
      { ts: "2026-11-13T01:33:10Z", kind: "decision", ref: "RUN-9/0", text: "PB-RANSOM · isolate_host: approval — Critical × K1: aksi disruptif wajib approval Commander", status: "approval", severity: null },
      { ts: "2026-11-13T01:33:10Z", kind: "approval", ref: "APR-15", text: "Approval isolate_host (critical×K1) → commander: pending", status: "pending", severity: null },
    ] },
    { key: "act", state: "waiting", waiting_reason: "1 aksi ditahan menunggu approval", items: [] },
  ],
};

const segmentSample: Segment[] = [
  { segment: "komando", assets: 1, K1: 1, K2: 0, K3: 0, active_incidents: 1, max_severity: "critical", max_criticality: "K1", hosts: [
    { asset_id: 1, hostname: "cmd-core-01", ip: "10.10.1.10", criticality: "K1", active_incidents: 1, max_severity: "critical", incident_id: 42 },
  ] },
  { segment: "aplikasi", assets: 2, K1: 0, K2: 2, K3: 0, active_incidents: 0, max_severity: null, max_criticality: "K2", hosts: [
    { asset_id: 3, hostname: "app-logistik-01", ip: "10.10.2.20", criticality: "K2", active_incidents: 0, max_severity: null, incident_id: null },
    { asset_id: 5, hostname: "db-pendukung-01", ip: "10.10.2.22", criticality: "K2", active_incidents: 0, max_severity: null, incident_id: null },
  ] },
  { segment: "pengguna", assets: 2, K1: 0, K2: 0, K3: 2, active_incidents: 1, max_severity: "high", max_criticality: "K3", hosts: [
    { asset_id: 8, hostname: "ws-staff-03", ip: "10.10.3.33", criticality: "K3", active_incidents: 1, max_severity: "high", incident_id: 40 },
    { asset_id: 9, hostname: "ws-staff-04", ip: "10.10.3.34", criticality: "K3", active_incidents: 0, max_severity: null, incident_id: null },
  ] },
];
</script>

<template>
  <div class="space-y-4">
    <div>
      <h1 class="text-lg font-semibold text-ink">{{ $t("components.title") }}</h1>
      <p class="text-xs text-ink-dim">{{ $t("components.note") }}</p>
    </div>

    <Panel title="Buttons">
      <div class="flex flex-wrap items-center gap-2">
        <AppButton variant="primary">Setujui</AppButton>
        <AppButton variant="default">Default</AppButton>
        <AppButton variant="ghost">Ghost</AppButton>
        <AppButton variant="danger">Tolak</AppButton>
        <AppButton variant="primary" loading>Memproses</AppButton>
        <AppButton variant="default" disabled>Disabled</AppButton>
        <AppButton size="sm" variant="default">Kecil</AppButton>
      </div>
    </Panel>

    <Panel title="Severity badges (selalu dengan label — aman buta warna)">
      <div class="flex flex-wrap gap-2">
        <SeverityBadge severity="critical" />
        <SeverityBadge severity="high" />
        <SeverityBadge severity="medium" />
        <SeverityBadge severity="low" />
        <SeverityBadge severity="info" />
      </div>
    </Panel>

    <Panel title="Status badges">
      <div class="flex flex-wrap gap-2">
        <StatusBadge tone="ok">Utuh</StatusBadge>
        <StatusBadge tone="warn">Menunggu</StatusBadge>
        <StatusBadge tone="danger">Gagal</StatusBadge>
        <StatusBadge tone="muted">Netral</StatusBadge>
      </div>
    </Panel>

    <Panel title="Kritikalitas aset (K1/K2/K3 — bukan warna severity)">
      <div class="flex flex-wrap items-center gap-2">
        <CritBadge level="K1" />
        <CritBadge level="K2" />
        <CritBadge level="K3" />
        <CritBadge :level="null" />
      </div>
    </Panel>

    <Panel title="TLP badges (standar berbagi info — bukan severity)">
      <div class="flex flex-wrap items-center gap-2">
        <TlpBadge tlp="WHITE" />
        <TlpBadge tlp="GREEN" />
        <TlpBadge tlp="AMBER" />
        <TlpBadge tlp="RED" />
      </div>
    </Panel>

    <div class="grid gap-4 md:grid-cols-2">
      <Panel title="Inputs">
        <div class="space-y-3">
          <TextInput v-model="sampleText" label="Teks (mono)" mono />
          <TextInput v-model="otp" label="Kode OTP" mono inputmode="numeric" placeholder="000000" />
        </div>
      </Panel>

      <Panel title="Modal">
        <AppButton variant="default" @click="modalOpen = true">Buka modal</AppButton>
        <Modal v-model:open="modalOpen" title="Konfirmasi aksi">
          <p class="text-ink-muted">
            Contoh dialog konfirmasi. Untuk aset K1, UI meminta ketik ulang nama aset (M8).
          </p>
          <template #footer>
            <AppButton size="sm" variant="ghost" @click="modalOpen = false">Batal</AppButton>
            <AppButton size="sm" variant="primary" @click="modalOpen = false">Konfirmasi</AppButton>
          </template>
        </Modal>
      </Panel>
    </div>

    <Panel title="DataTable">
      <DataTable :columns="columns" :rows="[...rows]">
        <template #[`cell:severity`]="{ value }">
          <SeverityBadge :severity="value as 'critical' | 'high' | 'medium' | 'low' | 'info'" />
        </template>
      </DataTable>
    </Panel>

    <Panel title="Alur investigasi OODA (fase berjalan = garis aksen; menunggu = kuning)">
      <OodaFlow :data="oodaSample" />
    </Panel>

    <Panel title="Peta segmen (kolom = segmen urut kritikalitas, baris = host; warna = severity insiden)">
      <SegmentMap :segments="segmentSample" />
    </Panel>

    <div class="grid gap-4 md:grid-cols-2">
      <Panel title="Loading (skeleton)">
        <SkeletonRow :rows="4" />
      </Panel>
      <Panel title="Empty state">
        <EmptyState message="Belum ada alert" hint="Jalankan simulator (M3) untuk menghasilkan event." />
      </Panel>
    </div>
  </div>
</template>
