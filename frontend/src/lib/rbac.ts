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
  | "audit:verify";

const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  commander: ["user:read", "audit:read", "audit:verify"],
  platform_admin: ["user:read", "user:create", "user:manage", "audit:read", "audit:verify"],
  auditor: ["user:read", "audit:read", "audit:verify"],
  analyst_t1: ["user:read"],
  analyst_t2: ["user:read"],
  analyst_t3: ["user:read"],
  ti_officer: ["user:read"],
  responder: ["user:read"],
  purple_team: ["user:read"],
};

export function permissionsFor(role: string | null | undefined): Permission[] {
  if (!role) return [];
  return ROLE_PERMISSIONS[role as Role] ?? [];
}

export function hasPermission(role: string | null | undefined, perm: Permission): boolean {
  return permissionsFor(role).includes(perm);
}
