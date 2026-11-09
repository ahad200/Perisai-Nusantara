import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import type { Permission } from "@/lib/rbac";

declare module "vue-router" {
  interface RouteMeta {
    public?: boolean;
    permission?: Permission;
  }
}

const routes: RouteRecordRaw[] = [
  { path: "/login", name: "login", component: () => import("@/views/LoginView.vue"), meta: { public: true } },
  { path: "/", name: "situasi", component: () => import("@/views/SituasiView.vue") },
  {
    path: "/aset",
    name: "aset",
    component: () => import("@/views/AsetView.vue"),
    meta: { permission: "asset:read" },
  },
  {
    path: "/event",
    name: "event",
    component: () => import("@/views/EventView.vue"),
    meta: { permission: "event:read" },
  },
  {
    path: "/intel",
    name: "intel",
    component: () => import("@/views/IntelView.vue"),
    meta: { permission: "intel:read" },
  },
  {
    path: "/alerts",
    name: "alerts",
    component: () => import("@/views/AlertQueueView.vue"),
    meta: { permission: "alert:read" },
  },
  {
    path: "/incidents",
    name: "incidents",
    component: () => import("@/views/IncidentView.vue"),
    meta: { permission: "incident:read" },
  },
  {
    path: "/soar",
    name: "soar",
    component: () => import("@/views/SoarView.vue"),
    meta: { permission: "soar:read" },
  },
  {
    path: "/pengguna",
    name: "pengguna",
    component: () => import("@/views/PenggunaView.vue"),
    meta: { permission: "user:read" },
  },
  {
    path: "/audit",
    name: "audit",
    component: () => import("@/views/AuditView.vue"),
    meta: { permission: "audit:read" },
  },
  { path: "/dev/components", name: "components", component: () => import("@/views/DevComponentsView.vue") },
  { path: "/:pathMatch(.*)*", name: "notfound", component: () => import("@/views/NotFoundView.vue") },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (to.meta.public) {
    // Sudah login tapi ke /login → arahkan ke beranda.
    return auth.isAuthenticated ? { path: "/" } : true;
  }
  if (!auth.isAuthenticated) {
    return { path: "/login" };
  }
  if (to.meta.permission && !auth.can(to.meta.permission)) {
    return { path: "/" };
  }
  return true;
});
