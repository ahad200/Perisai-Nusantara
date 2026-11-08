<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import AppClock from "@/components/ui/AppClock.vue";
import AppButton from "@/components/ui/AppButton.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import { useAuthStore } from "@/stores/auth";
import { setLocale } from "@/i18n";
import { theme, toggleTheme } from "@/lib/theme";

const auth = useAuthStore();
const router = useRouter();
const { locale } = useI18n();

function switchLocale() {
  setLocale(locale.value === "id" ? "en" : "id");
}

function signOut() {
  auth.logout();
  router.push("/login");
}
</script>

<template>
  <header
    class="flex h-12 shrink-0 items-center justify-between border-b border-edge bg-graphite-surface px-4"
  >
    <AppClock />
    <div class="flex items-center gap-3">
      <AppButton size="sm" variant="ghost" @click="switchLocale">
        {{ locale === "id" ? "EN" : "ID" }}
      </AppButton>
      <AppButton size="sm" variant="ghost" @click="toggleTheme">
        {{ theme === "dark" ? "Terang" : "Gelap" }}
      </AppButton>
      <div v-if="auth.user" class="flex items-center gap-2">
        <span class="text-sm text-ink">{{ auth.user.username }}</span>
        <StatusBadge tone="muted" class="font-mono">{{ auth.user.role }}</StatusBadge>
      </div>
      <AppButton size="sm" variant="default" @click="signOut">
        {{ $t("common.signOut") }}
      </AppButton>
    </div>
  </header>
</template>
