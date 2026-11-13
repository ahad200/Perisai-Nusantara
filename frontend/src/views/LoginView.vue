<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import TextInput from "@/components/ui/TextInput.vue";
import AppButton from "@/components/ui/AppButton.vue";
import { useAuthStore } from "@/stores/auth";
import { ApiError } from "@/lib/api";

const auth = useAuthStore();
const router = useRouter();

const mode = ref<"creds" | "mfa">("creds");
const username = ref("");
const password = ref("");
const otp = ref("");
const error = ref<string | null>(null);
const busy = ref(false);

async function submitCreds() {
  error.value = null;
  busy.value = true;
  try {
    const { mfaRequired } = await auth.login(username.value, password.value);
    if (mfaRequired) {
      mode.value = "mfa";
    } else {
      await router.push("/");
    }
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Tidak dapat terhubung ke server";
  } finally {
    busy.value = false;
  }
}

async function submitMfa() {
  error.value = null;
  busy.value = true;
  try {
    await auth.completeMfa(otp.value);
    await router.push("/");
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Verifikasi gagal";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="flex h-5 shrink-0 items-center justify-center border-b border-edge bg-graphite-raised font-mono text-[11px] tracking-[0.2em] text-ink-muted">
      RAHASIA · DATA SIMULASI · LINGKUNGAN PENGEMBANGAN
    </div>
  <div class="flex flex-1 items-center justify-center p-4">
    <div class="w-full max-w-sm">
      <div class="mb-6 border-l-2 border-accent pl-3">
        <h1 class="text-xl font-semibold tracking-[0.12em] text-ink">PERISAI NUSANTARA</h1>
        <p class="font-mono text-xs text-ink-dim">PN-X · MATA ELANG · Konsol SOC</p>
      </div>

      <form
        v-if="mode === 'creds'"
        class="space-y-3 rounded border border-edge bg-graphite-surface p-4"
        @submit.prevent="submitCreds"
      >
        <h2 class="font-mono text-xs font-medium uppercase tracking-[0.12em] text-ink-muted">{{ $t("login.heading") }}</h2>
        <TextInput
          v-model="username"
          :label="$t('login.username')"
          autocomplete="username"
        />
        <TextInput
          v-model="password"
          type="password"
          :label="$t('login.password')"
          autocomplete="current-password"
        />
        <p v-if="error" class="text-xs text-sev-critical">{{ error }}</p>
        <AppButton type="submit" variant="primary" :loading="busy" class="w-full">
          {{ $t("login.submit") }}
        </AppButton>
      </form>

      <form
        v-else
        class="space-y-3 rounded border border-edge bg-graphite-surface p-4"
        @submit.prevent="submitMfa"
      >
        <h2 class="font-mono text-xs font-medium uppercase tracking-[0.12em] text-ink-muted">{{ $t("login.otp") }}</h2>
        <p class="text-xs text-ink-muted">{{ $t("login.mfaPrompt") }}</p>
        <TextInput
          v-model="otp"
          :label="$t('login.otp')"
          mono
          inputmode="numeric"
          autocomplete="one-time-code"
        />
        <p v-if="error" class="text-xs text-sev-critical">{{ error }}</p>
        <AppButton type="submit" variant="primary" :loading="busy" class="w-full">
          {{ $t("login.verify") }}
        </AppButton>
      </form>
      <p class="mt-3 text-xs text-ink-dim">Akses terbatas untuk personel SOC berwenang. Setiap login dicatat di audit (hash chain).</p>
    </div>
  </div>
  </div>
</template>
