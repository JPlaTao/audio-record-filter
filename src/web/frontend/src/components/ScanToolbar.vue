<template>
  <div class="scan-toolbar">
    <button class="btn" :disabled="scanning" @click="$emit('scan')">
      <template v-if="scanning">&#10231; 扫描中...</template>
      <template v-else>&#128269; 扫描新录音</template>
    </button>
    <button
      class="btn btn-accent"
      :disabled="processing || pendingCount === 0"
      @click="$emit('process')"
    >
      &#9654; 处理选中 <template v-if="processing">({{ progressPercent }}%)</template>
    </button>
    <button class="btn btn-ghost" :disabled="!fileCount" @click="$emit('selectAllPending')">
      &#9745; 全选未处理
    </button>
    <button class="btn btn-ghost" :disabled="!selectedCount" @click="$emit('clearSelection')">
      &#10005; 清空选择
    </button>
    <span class="scan-count" v-if="fileCount">
      共 {{ fileCount }} 条，待处理 {{ pendingCount }} 条
      <template v-if="selectedCount">，已选 {{ selectedCount }}</template>
    </span>
    <slot name="extra" />
  </div>
</template>

<script setup>
defineProps({
  scanning: Boolean,
  processing: Boolean,
  progressPercent: { type: Number, default: 0 },
  fileCount: { type: Number, default: 0 },
  pendingCount: { type: Number, default: 0 },
  selectedCount: { type: Number, default: 0 },
})
defineEmits(['scan', 'process', 'selectAllPending', 'clearSelection'])
</script>

<style scoped>
.scan-toolbar { display: flex; gap: var(--space-sm); align-items: center; flex-wrap: wrap; }
.scan-count { margin-left: auto; font-family: var(--font-ui); font-size: 0.82rem; color: var(--text-muted); }
</style>
