<script setup lang="ts">
import { onBeforeUnmount, onMounted } from "vue";

const open = defineModel<boolean>("open", { required: true });
withDefaults(defineProps<{ title?: string; size?: "md" | "lg" }>(), { size: "md" });

function onKey(e: KeyboardEvent) {
  if (e.key === "Escape") open.value = false;
}
onMounted(() => window.addEventListener("keydown", onKey));
onBeforeUnmount(() => window.removeEventListener("keydown", onKey));
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      @click.self="open = false"
    >
      <div
        role="dialog"
        aria-modal="true"
        class="flex max-h-[90vh] w-full flex-col rounded border border-edge bg-graphite-surface shadow-xl"
        :class="size === 'lg' ? 'max-w-3xl' : 'max-w-md'"
      >
        <header
          v-if="title || $slots.header"
          class="border-b border-edge px-3 py-2 text-sm font-medium text-ink"
        >
          <slot name="header">{{ title }}</slot>
        </header>
        <div class="overflow-auto p-3 text-sm text-ink"><slot /></div>
        <footer
          v-if="$slots.footer"
          class="flex justify-end gap-2 border-t border-edge px-3 py-2"
        >
          <slot name="footer" />
        </footer>
      </div>
    </div>
  </Teleport>
</template>
