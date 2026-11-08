// Memastikan $t tersedia & bertipe di template (globalInjection vue-i18n).
import "vue";

declare module "vue" {
  interface ComponentCustomProperties {
    $t: (key: string, ...args: unknown[]) => string;
  }
}
