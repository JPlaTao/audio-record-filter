<template>
  <div class="export-bar" v-if="selectedCount">
    <span class="export-info">已选 {{ selectedCount }} 条</span>
    <button class="btn btn-accent" @click="$emit('export')">&#128230; 打包导出</button>
  </div>
</template>

<script setup>
defineProps({ selectedCount: { type: Number, default: 0 } })
defineEmits(['export'])
</script>

<style scoped>
.export-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 0; margin-top: 12px; border-top: 1px solid var(--border-light);
}
.export-info { font-family: var(--font-ui); font-size: 0.85rem; color: var(--text-secondary); }
</style>
