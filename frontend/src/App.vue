<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import AppLayout from "@/components/layout/AppLayout.vue";

const route = useRoute();
// Rute publik (login) tampil polos; sisanya dibungkus layout aplikasi.
const useShell = computed(() => !route.meta.public);
</script>

<template>
  <AppLayout v-if="useShell">
    <RouterView />
  </AppLayout>
  <RouterView v-else />
</template>
