// Cermin ringan dari RBAC backend (app/core/rbac.py) — HANYA untuk menyusun menu
// & menyembunyikan aksi di UI. Penegakan sebenarnya tetap di backend.
export type Role =
  | "commander"
  | "analyst_t1"
  | "analyst_t2"
  | "analyst_t3"
  | "ti_officer"
  | "responder"
  | "purple_team"
  | "auditor"
  | "platform_admin";

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
  | "intel:manage";

// Izin dasar SOC yang dimiliki semua role (lihat _SOC_BASE di backend).
const SOC_BASE: Permission[] = ["user:read", "asset:read", "event:read", "intel:read"];

const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  commander: [...SOC_BASE, "audit:read", "audit:verify"],
  platform_admin: [...SOC_BASE, "user:create", "user:manage", "audit:read", "audit:verify", "asset:manage", "sim:run", "intel:manage"],
  auditor: [...SOC_BASE, "audit:read", "audit:verify"],
  analyst_t1: [...SOC_BASE],
  analyst_t2: [...SOC_BASE],
  analyst_t3: [...SOC_BASE],
  ti_officer: [...SOC_BASE, "intel:manage"],
  responder: [...SOC_BASE],
  purple_team: [...SOC_BASE, "sim:run"],
};

export function permissionsFor(role: string | null | undefined): Permission[] {
  if (!role) return [];
  return ROLE_PERMISSIONS[role as Role] ?? [];
}

export function hasPermission(role: string | null | undefined, perm: Permission): boolean {
  return permissionsFor(role).includes(perm);
}
