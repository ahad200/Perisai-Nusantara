<script setup lang="ts" generic="T extends Record<string, unknown>">
export interface Column {
  key: string;
  label: string;
  mono?: boolean;
  align?: "left" | "right";
  width?: string;
}

defineProps<{ columns: Column[]; rows: T[]; rowKey?: keyof T; clickable?: boolean }>();
const emit = defineEmits<{ (e: "row-click", row: T): void }>();
</script>

<template>
  <div class="overflow-x-auto rounded border border-edge">
    <table class="w-full border-collapse text-sm">
      <thead>
        <tr class="border-b border-edge bg-graphite-raised text-left">
          <th
            v-for="col in columns"
            :key="col.key"
            :style="col.width ? { width: col.width } : undefined"
            :class="[
              'px-3 py-2 text-xs font-medium uppercase tracking-wide text-ink-muted',
              col.align === 'right' ? 'text-right' : 'text-left',
            ]"
          >
            {{ col.label }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(row, i) in rows"
          :key="rowKey ? String(row[rowKey]) : i"
          :class="[
            'border-b border-edge/60 last:border-0 hover:bg-graphite-raised/50',
            clickable ? 'cursor-pointer' : '',
          ]"
          @click="clickable && emit('row-click', row)"
        >
          <td
            v-for="col in columns"
            :key="col.key"
            :class="[
              'h-[34px] px-3 py-1.5 align-middle',
              col.align === 'right' ? 'text-right' : 'text-left',
              col.mono ? 'font-mono tnum text-ink-muted' : 'text-ink',
            ]"
          >
            <slot :name="`cell:${col.key}`" :row="row" :value="row[col.key]">
              {{ row[col.key] }}
            </slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
