<script setup lang="ts">
// Command bar: strip klasifikasi + postur live & hitungan antrian (dapat diklik)
// di kiri, jam WIB/UTC + kontrol sesi di kanan. Data dari useOpsStatus (polling
// 60 dtk, tanpa animasi). Warna hanya untuk postur/antrian yang butuh perhatian.
import { computed, onBeforeUnmount, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import AppClock from "@/components/ui/AppClock.vue";
import AppButton from "@/components/ui/AppButton.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import { useAuthStore } from "@/stores/auth";
import { setLocale } from "@/i18n";
import { theme, toggleTheme } from "@/lib/theme";
import { useOpsStatus } from "@/lib/opsStatus";

const auth = useAuthStore();
const router = useRouter();
const { locale } = useI18n();
const ops = useOpsStatus();

onMounted(ops.start);
onBeforeUnmount(ops.stop);

const counters = computed(() => {
  const s = ops.snapshot.value;
  if (!s) return [];
  return [
    { to: "/incidents", n: s.active_incidents, label: "insiden aktif", attn: s.active_incidents > 0 && s.posture === "critical" ? "text-sev-critical" : "" },
    { to: "/soar", n: s.pending_approvals, label: "approval tertunda", attn: s.pending_approvals > 0 ? "text-sev-medium" : "" },
    { to: "/alerts", n: s.open_alerts, label: "alert terbuka", attn: "" },
  ];
});

const syncLabel = computed(() =>
  ops.lastSync.value
    ? new Intl.DateTimeFormat("id-ID", { timeZone: "Asia/Jakarta", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(ops.lastSync.value)
    : "—",
);

function switchLocale() {
  setLocale(locale.value === "id" ? "en" : "id");
}

function signOut() {
  auth.logout();
  router.push("/login");
}
</script>

<template>
  <header class="shrink-0 border-b border-edge bg-graphite-surface">
    <!-- Strip klasifikasi: netral (warna disimpan untuk severity). -->
    <div class="flex h-5 items-center justify-center border-b border-edge bg-graphite-raised font-mono text-[11px] tracking-[0.2em] text-ink-muted">
      PROTOTIPE · DATA SIMULASI · BUKAN SISTEM RESMI
    </div>

    <div class="flex h-12 items-center justify-between gap-4 px-4">
      <div class="flex min-w-0 items-center gap-4">
        <RouterLink v-if="ops.posture.value" to="/" class="shrink-0" title="Postur keseluruhan — buka Situasi">
          <StatusBadge :tone="ops.posture.value.tone" class="font-mono tracking-wider">
            POSTUR · {{ ops.posture.value.label }}
          </StatusBadge>
        </RouterLink>
        <nav class="hidden items-center gap-4 md:flex" aria-label="Antrian">
          <RouterLink
            v-for="c in counters"
            :key="c.to"
            :to="c.to"
            class="flex items-baseline gap-1.5 rounded-sm text-xs text-ink-dim hover:text-ink"
          >
            <span class="font-mono text-sm tnum" :class="c.attn || 'text-ink'">{{ c.n }}</span>
            {{ c.label }}
          </RouterLink>
        </nav>
        <span class="hidden font-mono text-[11px] text-ink-dim lg:inline" :title="'Sinkron terakhir (WIB), tiap 60 detik'">
          sinkron {{ syncLabel }}
        </span>
      </div>

      <div class="flex shrink-0 items-center gap-3">
        <AppClock />
        <span class="h-5 w-px bg-edge" aria-hidden="true" />
        <AppButton size="sm" variant="ghost" @click="switchLocale">
          {{ locale === "id" ? "EN" : "ID" }}
        </AppButton>
        <AppButton size="sm" variant="ghost" @click="toggleTheme">
          {{ theme === "dark" ? "Terang" : "Gelap" }}
        </AppButton>
        <div v-if="auth.user" class="flex items-center gap-2">
          <span class="text-sm text-ink">{{ auth.user.username }}</span>
          <StatusBadge tone="muted" class="font-mono uppercase">{{ auth.user.role }}</StatusBadge>
        </div>
        <AppButton size="sm" variant="default" @click="signOut">
          {{ $t("common.signOut") }}
        </AppButton>
      </div>
    </div>
  </header>
</template>
