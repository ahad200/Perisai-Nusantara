import { ref } from "vue";

export type Theme = "dark" | "light";
const KEY = "pnx_theme";

export const theme = ref<Theme>((localStorage.getItem(KEY) as Theme) ?? "dark");

export function applyTheme(t: Theme): void {
  theme.value = t;
  localStorage.setItem(KEY, t);
  const root = document.documentElement;
  root.classList.toggle("dark", t === "dark");
  root.classList.toggle("light", t === "light");
}

export function toggleTheme(): void {
  applyTheme(theme.value === "dark" ? "light" : "dark");
}
