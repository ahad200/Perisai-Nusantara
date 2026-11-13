<script setup lang="ts">
// Lambang PN-X (elang + perisai). Varian mengikuti tema agar badan elang tetap
// terbaca: logo-dark (badan terang) di tema gelap, logo-light (asli) di tema terang.
// Dipakai hanya di identitas produk (login, brand sidebar) — bukan hiasan (C.5).
import { computed } from "vue";
import { theme } from "@/lib/theme";

const props = withDefaults(defineProps<{ size?: number }>(), { size: 28 });
const src = computed(
  () => `${import.meta.env.BASE_URL}brand/logo-${theme.value === "dark" ? "dark" : "light"}.png`,
);
</script>

<template>
  <img :src="src" :width="props.size" :height="props.size" alt="Lambang Perisai Nusantara" class="shrink-0 select-none" draggable="false" />
</template>
