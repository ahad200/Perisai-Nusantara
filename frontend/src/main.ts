import { createApp } from "vue";
import { createPinia } from "pinia";

import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./style.css";

import App from "./App.vue";
import { router } from "./router";
import { i18n } from "./i18n";
import { useAuthStore } from "./stores/auth";
import { applyTheme, theme } from "./lib/theme";

async function bootstrap() {
  applyTheme(theme.value); // set kelas tema sebelum render

  const app = createApp(App);
  const pinia = createPinia();
  app.use(pinia);
  app.use(i18n);

  // Pulihkan sesi (ambil /auth/me) sebelum router aktif agar guard punya data role.
  const auth = useAuthStore();
  await auth.init();

  app.use(router);
  app.mount("#app");
}

bootstrap();
