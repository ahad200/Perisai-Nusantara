<script setup lang="ts">
import { onBeforeUnmount, onMounted } from "vue";

const open = defineModel<boolean>("open", { required: true });
defineProps<{ title?: string }>();

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
        class="w-full max-w-md rounded border border-edge bg-graphite-surface shadow-xl"
      >
        <header
          v-if="title || $slots.header"
          class="border-b border-edge px-3 py-2 text-sm font-medium text-ink"
        >
          <slot name="header">{{ title }}</slot>
        </header>
        <div class="p-3 text-sm text-ink"><slot /></div>
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
