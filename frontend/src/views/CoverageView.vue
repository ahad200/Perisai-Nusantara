<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import Panel from "@/components/ui/Panel.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import SkeletonRow from "@/components/ui/SkeletonRow.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import AppButton from "@/components/ui/AppButton.vue";
import { apiFetch, ApiError } from "@/lib/api";

interface Tech { id: string; name: string; level: "none" | "covered" | "validated"; alert_count: number }
interface Tactic { id: string; name: string; name_id: string; techniques: Tech[] }
interface Coverage {
  tactics: Tactic[];
  total_techniques: number;
  counts: { none: number; covered: number; validated: number };
  gaps: { tactic: string; id: string; name: string }[];
  coverage_pct: number;
  covered_pct: number;
}

const loading = ref(true);
const error = ref<string | null>(null);
const data = ref<Coverage | null>(null);

// Tingkat deteksi: intensitas aksen (bukan palet severity — coverage bukan severity).
const CELL: Record<string, string> = {
  validated: "border-accent bg-accent/20 text-ink",
  covered: "border-accent/40 bg-graphite-raised text-ink-muted",
  none: "border-dashed border-edge bg-transparent text-ink-dim",
};
const LEVEL_LABEL: Record<string, string> = {
  validated: "Tervalidasi", covered: "Terdeteksi", none: "Gap",
};

const maxRows = computed(() =>
  Math.max(0, ...(data.value?.tactics ?? []).map((t) => t.techniques.length)),
);

async function load() {
  loading.value = true;
  error.value = null;
  try {
    data.value = await apiFetch<Coverage>("/dashboard/coverage");
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Gagal memuat coverage";
  } finally {
    loading.value = false;
  }
}
onMounted(load);
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-lg font-semibold text-ink">Coverage ATT&CK</h1>
        <p class="text-xs text-ink-dim">Cakupan deteksi terhadap teknik prioritas (threat model F0), bukan seluruh matriks.</p>
      </div>
      <AppButton size="sm" variant="ghost" @click="load">Muat ulang</AppButton>
    </div>

    <div v-if="loading" class="space-y-2"><SkeletonRow v-for="i in 4" :key="i" /></div>
    <EmptyState v-else-if="error" :message="error"><template #action><AppButton size="sm" @click="load">{{ $t("common.retry") }}</AppButton></template></EmptyState>

    <template v-else-if="data">
      <!-- Ringkasan: setiap angka punya pembanding (target/total) -->
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Panel>
          <div class="text-2xl font-semibold text-ink">{{ data.coverage_pct }}%</div>
          <div class="text-xs text-ink-dim">tervalidasi · target ≥ 50%</div>
          <StatusBadge class="mt-1" :tone="data.coverage_pct >= 50 ? 'ok' : 'warn'">
            {{ data.coverage_pct >= 50 ? 'memenuhi' : 'di bawah target' }}
          </StatusBadge>
        </Panel>
        <Panel>
          <div class="text-2xl font-semibold text-ink">{{ data.counts.validated }}</div>
          <div class="text-xs text-ink-dim">dari {{ data.total_techniques }} teknik prioritas</div>
        </Panel>
        <Panel>
          <div class="text-2xl font-semibold text-ink">{{ data.covered_pct }}%</div>
          <div class="text-xs text-ink-dim">punya aturan deteksi</div>
        </Panel>
        <Panel>
          <div class="text-2xl font-semibold" :class="data.gaps.length ? 'text-sev-medium' : 'text-ink'">{{ data.gaps.length }}</div>
          <div class="text-xs text-ink-dim">gap (tanpa deteksi)</div>
        </Panel>
      </div>

      <!-- Legenda -->
      <div class="flex flex-wrap gap-3 text-xs text-ink-muted">
        <span v-for="lvl in ['validated','covered','none']" :key="lvl" class="flex items-center gap-1.5">
          <span class="inline-block h-3 w-3 rounded-sm border" :class="CELL[lvl]" />
          {{ LEVEL_LABEL[lvl] }}
        </span>
      </div>

      <!-- Matriks taktik × teknik -->
      <Panel>
        <div class="overflow-x-auto">
          <div class="flex gap-2" :style="{ minWidth: data.tactics.length * 150 + 'px' }">
            <div v-for="tac in data.tactics" :key="tac.id" class="flex-1" style="min-width: 140px">
              <div class="mb-1 border-b border-edge pb-1">
                <div class="text-xs font-semibold text-ink">{{ tac.name }}</div>
                <div class="font-mono text-[10px] text-ink-dim">{{ tac.id }}</div>
              </div>
              <div class="space-y-1">
                <div
                  v-for="tech in tac.techniques"
                  :key="tech.id"
                  class="rounded-sm border px-2 py-1.5"
                  :class="CELL[tech.level]"
                  :title="`${tech.id} ${tech.name} — ${LEVEL_LABEL[tech.level]} (${tech.alert_count} alert)`"
                >
                  <div class="font-mono text-[11px]">{{ tech.id }}</div>
                  <div class="truncate text-[11px] leading-tight">{{ tech.name }}</div>
                  <div v-if="tech.alert_count" class="text-[10px] text-ink-dim">{{ tech.alert_count }} alert</div>
                </div>
                <div v-for="n in (maxRows - tac.techniques.length)" :key="'pad'+n" class="h-[3.1rem]" />
              </div>
            </div>
          </div>
        </div>
      </Panel>

      <Panel v-if="data.gaps.length" title="Gap deteksi — prioritas penutupan">
        <table class="w-full text-sm">
          <thead class="text-left text-xs text-ink-dim">
            <tr><th class="py-1">Taktik</th><th class="py-1">Teknik</th><th class="py-1">Nama</th></tr>
          </thead>
          <tbody>
            <tr v-for="g in data.gaps" :key="g.id" class="border-t border-edge/50">
              <td class="py-1 text-ink-muted">{{ g.tactic }}</td>
              <td class="py-1 font-mono text-ink">{{ g.id }}</td>
              <td class="py-1 text-ink-muted">{{ g.name }}</td>
            </tr>
          </tbody>
        </table>
      </Panel>
    </template>
  </div>
</template>
