<template>
  <tr class="record-card" :class="{ 'warn-missing': hasMissingName }">
    <td>
      <input type="checkbox" :checked="selected" @change="$emit('toggle', record.id)" />
    </td>
    <td>
      <div class="file-info">
        <TagBadge :level="record.level" />
        <div class="file-meta">
          <span class="file-name">{{ record.file }}</span>
          <span class="file-date" v-if="record.duration">
            {{ Math.round(record.duration) }}s
          </span>
        </div>
      </div>
    </td>
    <td v-for="field in fields" :key="field.key" class="field-cell">
      <SummaryChip
        :field="field"
        :value="record.summary?.[field.key] || ''"
        @update:value="onFieldUpdate(field.key, $event)"
      />
    </td>
    <td class="actions-cell">
      <span class="link-like" @click="$emit('detail', record)">详情</span>
      <span class="link-like link-danger" @click="$emit('reprocess', record)">重新处理</span>
    </td>
  </tr>
</template>

<script setup>
import { computed } from 'vue'
import TagBadge from './TagBadge.vue'
import SummaryChip from './SummaryChip.vue'

const props = defineProps({
  record: { type: Object, required: true },
  fields: { type: Array, default: () => [] },
  selected: Boolean,
})
const emit = defineEmits(['toggle', 'detail', 'reprocess', 'update-field'])

const hasMissingName = computed(() => {
  const val = props.record.summary?.name
  return !val || val === '未识别'
})

function onFieldUpdate(key, value) {
  emit('update-field', { id: props.record.id, key, value })
}
</script>

<style scoped>
.file-info { display: flex; align-items: center; gap: 12px; }
.file-meta { display: flex; flex-direction: column; gap: 2px; }
.file-name { font-family: var(--font-ui); font-size: 0.85rem; font-weight: 500; }
.file-date { font-family: var(--font-ui); font-size: 0.75rem; color: var(--text-muted); }
.field-cell { min-width: 80px; }
.actions-cell { white-space: nowrap; display: flex; gap: 8px; }
.link-danger { color: #c0392b; }
.link-danger:hover { color: #e74c3c; }
tr.warn-missing td { background: #fefaf0; }
tr.warn-missing:hover td { background: #fcf5e8; }
</style>
