<script setup lang="ts">
import { ref } from "vue";
import Panel from "@/components/ui/Panel.vue";
import AppButton from "@/components/ui/AppButton.vue";
import SeverityBadge from "@/components/ui/SeverityBadge.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import CritBadge from "@/components/ui/CritBadge.vue";
import TextInput from "@/components/ui/TextInput.vue";
import Modal from "@/components/ui/Modal.vue";
import DataTable, { type Column } from "@/components/ui/DataTable.vue";
import SkeletonRow from "@/components/ui/SkeletonRow.vue";
import EmptyState from "@/components/ui/EmptyState.vue";

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
