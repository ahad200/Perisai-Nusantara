import { createI18n } from "vue-i18n";

const id = {
  app: { title: "Perisai Nusantara", subtitle: "Konsol SOC" },
  common: {
    signOut: "Keluar",
    role: "Role",
    loading: "Memuat…",
    retry: "Coba lagi",
    empty: "Tidak ada data",
    theme: "Tema",
    language: "Bahasa",
  },
  nav: {
    situasi: "Situasi",
    pengguna: "Pengguna",
    audit: "Audit",
    components: "Komponen (dev)",
  },
  login: {
    heading: "Masuk",
    username: "Nama pengguna",
    password: "Kata sandi",
    otp: "Kode OTP (6 digit)",
    submit: "Masuk",
    verify: "Verifikasi",
    mfaPrompt: "Masukkan kode dari aplikasi authenticator",
    failed: "Login gagal",
  },
  situasi: {
    title: "Common Operating Picture",
    placeholder:
      "Dashboard situasi lengkap hadir di M9. Fondasi (auth, layout, komponen) siap di M2.",
    welcome: "Masuk sebagai",
  },
  pengguna: {
    title: "Pengguna",
    id: "ID",
    username: "Nama pengguna",
    fullName: "Nama lengkap",
    role: "Role",
    mfa: "MFA",
    active: "Aktif",
  },
  audit: {
    title: "Audit",
    verify: "Verifikasi integritas",
    ok: "Rantai audit utuh",
    broken: "Rantai audit RUSAK di entri",
    count: "entri",
    ts: "Waktu",
    action: "Aksi",
    actor: "Aktor",
    object: "Objek",
    hash: "Hash",
  },
  components: {
    title: "Galeri Komponen",
    note: "Semua komponen dasar + state-nya (C.6). Bangun ini sebelum halaman.",
  },
};

const en: typeof id = {
  app: { title: "Perisai Nusantara", subtitle: "SOC Console" },
  common: {
    signOut: "Sign out",
    role: "Role",
    loading: "Loading…",
    retry: "Retry",
    empty: "No data",
    theme: "Theme",
    language: "Language",
  },
  nav: {
    situasi: "Situation",
    pengguna: "Users",
    audit: "Audit",
    components: "Components (dev)",
  },
  login: {
    heading: "Sign in",
    username: "Username",
    password: "Password",
    otp: "OTP code (6 digits)",
    submit: "Sign in",
    verify: "Verify",
    mfaPrompt: "Enter the code from your authenticator app",
    failed: "Login failed",
  },
  situasi: {
    title: "Common Operating Picture",
    placeholder:
      "Full situation dashboard lands in M9. Foundation (auth, layout, components) is ready in M2.",
    welcome: "Signed in as",
  },
  pengguna: {
    title: "Users",
    id: "ID",
    username: "Username",
    fullName: "Full name",
    role: "Role",
    mfa: "MFA",
    active: "Active",
  },
  audit: {
    title: "Audit",
    verify: "Verify integrity",
    ok: "Audit chain intact",
    broken: "Audit chain BROKEN at entry",
    count: "entries",
    ts: "Time",
    action: "Action",
    actor: "Actor",
    object: "Object",
    hash: "Hash",
  },
  components: {
    title: "Component Gallery",
    note: "All base components + their states (C.6). Build this before pages.",
  },
};

export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: localStorage.getItem("pnx_locale") ?? "id",
  fallbackLocale: "en",
  messages: { id, en },
});

export function setLocale(locale: "id" | "en"): void {
  i18n.global.locale.value = locale;
  localStorage.setItem("pnx_locale", locale);
  document.documentElement.setAttribute("lang", locale);
}
