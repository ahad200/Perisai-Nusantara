<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { clockParts } from "@/lib/time";

const wib = ref("");
const utc = ref("");
let timer: number | undefined;

function tick() {
  const p = clockParts();
  wib.value = p.wib;
  utc.value = p.utc;
}

onMounted(() => {
  tick();
  timer = window.setInterval(tick, 1000);
});
onBeforeUnmount(() => timer && clearInterval(timer));
</script>

<template>
  <div class="flex items-center gap-3 font-mono text-xs tnum text-ink-muted">
    <span><span class="text-ink-dim">WIB</span> {{ wib }}</span>
    <span class="text-edge">·</span>
    <span><span class="text-ink-dim">UTC</span> {{ utc }}</span>
  </div>
</template>
