// Cermin ringan dari RBAC backend (app/core/rbac.py) — HANYA untuk menyusun menu
// & menyembunyikan aksi di UI. Penegakan sebenarnya tetap di backend.
// Model 4-role (konsolidasi dari 9): operator (eksekusi) / commander (persetujuan
// + admin) / intel (validasi atribusi) / auditor (read-only). Cermin backend.
export type Role = "operator" | "commander" | "intel" | "auditor";

export type Permission =
  | "user:read"
  | "user:create"
  | "user:manage"
  | "audit:read"
  | "audit:verify"
  | "asset:read"
  | "asset:manage"
  | "event:read"
  | "sim:run"
  | "intel:read"
  | "intel:manage"
  | "alert:read"
  | "alert:triage"
  | "detect:run"
  | "detect:manage"
  | "incident:read"
  | "incident:manage"
  | "soar:read"
  | "soar:execute"
  | "soar:approve"
  | "soar:manage"
  | "dashboard:read"
  | "report:read"
  | "report:generate"
  | "report:approve"
  | "report:manage"
  | "agent:run"
  | "attribution:read"
  | "attribution:validate";

// Izin dasar SOC yang dimiliki semua role (lihat _SOC_BASE di backend).
const SOC_BASE: Permission[] = ["user:read", "asset:read", "event:read", "intel:read", "alert:read", "incident:read", "soar:read", "dashboard:read", "report:read", "attribution:read"];

const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  // Operator: mengeksekusi (deteksi/insiden/playbook/agen) tapi tidak menyetujui.
  operator: [...SOC_BASE, "sim:run", "alert:triage", "detect:run", "detect:manage", "incident:manage", "soar:execute", "agent:run", "report:generate"],
  // Commander: menyetujui (SOAR/laporan) + admin, tapi tidak mengeksekusi playbook.
  commander: [...SOC_BASE, "audit:read", "audit:verify", "user:create", "user:manage", "asset:manage", "alert:triage", "detect:manage", "incident:manage", "soar:approve", "soar:manage", "report:generate", "report:approve", "report:manage", "agent:run"],
  // Intel: threat intel + satu-satunya yang memvalidasi atribusi.
  intel: [...SOC_BASE, "intel:manage", "agent:run", "attribution:validate"],
  // Auditor: read-only + verifikasi hash chain.
  auditor: [...SOC_BASE, "audit:read", "audit:verify"],
};

// Peta role lama (sebelum konsolidasi 9→4) ke padanan 4-role, untuk TAMPILAN saja.
// Data historis (mis. penugasan alert lama) tak diubah — hanya dirapikan saat render.
const LEGACY_ROLE_MAP: Record<string, Role> = {
  analyst_t1: "operator",
  analyst_t2: "operator",
  analyst_t3: "operator",
  responder: "operator",
  purple_team: "operator",
  ti_officer: "intel",
  platform_admin: "commander",
};

/** Normalisasi nama role/username lama ke label 4-role saat ini (display-only). */
export function normalizeRole(name: string | null | undefined): string {
  if (!name) return "";
  return LEGACY_ROLE_MAP[name] ?? name;
}

export function permissionsFor(role: string | null | undefined): Permission[] {
  if (!role) return [];
  return ROLE_PERMISSIONS[role as Role] ?? [];
}

export function hasPermission(role: string | null | undefined, perm: Permission): boolean {
  return permissionsFor(role).includes(perm);
}
