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
const ANALYST_TRIAGE: Permission[] = ["alert:triage", "detect:run"];

const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  commander: [...SOC_BASE, "audit:read", "audit:verify", "alert:triage", "incident:manage", "soar:approve", "soar:manage", "report:generate", "report:approve", "report:manage", "agent:run"],
  platform_admin: [...SOC_BASE, "user:create", "user:manage", "audit:read", "audit:verify", "asset:manage", "sim:run", "intel:manage", "alert:triage", "detect:run", "detect:manage", "incident:manage", "soar:execute", "soar:approve", "soar:manage", "report:generate", "report:approve", "report:manage", "agent:run", "attribution:validate"],
  auditor: [...SOC_BASE, "audit:read", "audit:verify"],
  analyst_t1: [...SOC_BASE, ...ANALYST_TRIAGE],
  analyst_t2: [...SOC_BASE, ...ANALYST_TRIAGE, "incident:manage", "soar:approve", "report:generate", "agent:run"],
  analyst_t3: [...SOC_BASE, ...ANALYST_TRIAGE, "detect:manage", "incident:manage", "soar:execute", "soar:approve", "report:generate", "agent:run"],
  ti_officer: [...SOC_BASE, "intel:manage", "agent:run", "attribution:validate"],
  responder: [...SOC_BASE, "incident:manage", "soar:execute", "report:generate", "agent:run"],
  purple_team: [...SOC_BASE, "sim:run", "detect:run"],
};

export function permissionsFor(role: string | null | undefined): Permission[] {
  if (!role) return [];
  return ROLE_PERMISSIONS[role as Role] ?? [];
}

export function hasPermission(role: string | null | undefined, perm: Permission): boolean {
  return permissionsFor(role).includes(perm);
}
