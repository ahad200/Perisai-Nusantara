import { defineStore } from "pinia";
import { apiFetch, setAuthToken } from "@/lib/api";
import { permissionsFor, type Permission } from "@/lib/rbac";

export interface CurrentUser {
  id: number;
  username: string;
  full_name: string;
  role: string;
  is_active: boolean;
  mfa_enabled: boolean;
  created_at: string;
}

interface LoginResponse {
  mfa_required: boolean;
  access_token: string | null;
  token_type: string | null;
  mfa_token: string | null;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
}

const TOKEN_KEY = "pnx_token";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: (localStorage.getItem(TOKEN_KEY) as string | null) ?? null,
    user: null as CurrentUser | null,
    mfaToken: null as string | null,
  }),
  getters: {
    isAuthenticated: (s): boolean => !!s.token,
    role: (s): string | null => s.user?.role ?? null,
    permissions(): Permission[] {
      return permissionsFor(this.user?.role);
    },
    can() {
      return (perm: Permission): boolean => this.permissions.includes(perm);
    },
  },
  actions: {
    _setToken(token: string | null) {
      this.token = token;
      setAuthToken(token);
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    },

    /** Panggil sekali saat app start untuk memulihkan sesi. */
    async init() {
      if (!this.token) return;
      setAuthToken(this.token);
      try {
        await this.fetchMe();
      } catch {
        this.logout();
      }
    },

    /** Login langkah pertama. Mengembalikan apakah MFA masih diperlukan. */
    async login(username: string, password: string, otp?: string): Promise<{ mfaRequired: boolean }> {
      const res = await apiFetch<LoginResponse>("/auth/login", {
        method: "POST",
        auth: false,
        body: { username, password, otp_code: otp ?? null },
      });
      if (res.mfa_required) {
        this.mfaToken = res.mfa_token;
        return { mfaRequired: true };
      }
      this._setToken(res.access_token);
      await this.fetchMe();
      return { mfaRequired: false };
    },

    /** Selesaikan MFA dengan kode OTP. */
    async completeMfa(otp: string): Promise<void> {
      if (!this.mfaToken) throw new Error("Tidak ada sesi MFA aktif");
      const res = await apiFetch<TokenResponse>("/auth/mfa", {
        method: "POST",
        auth: false,
        body: { mfa_token: this.mfaToken, otp_code: otp },
      });
      this._setToken(res.access_token);
      this.mfaToken = null;
      await this.fetchMe();
    },

    async fetchMe(): Promise<void> {
      this.user = await apiFetch<CurrentUser>("/auth/me");
    },

    logout() {
      this._setToken(null);
      this.user = null;
      this.mfaToken = null;
    },
  },
});
