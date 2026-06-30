<template>
  <div class="progress-track">
    <div class="progress-fill" :style="{ width: percent + '%' }"></div>
  </div>
</template>

<script setup>
defineProps({ percent: { type: Number, default: 0 } })
</script>

<style scoped>
.progress-track {
  height: 3px;
  background: var(--border-light);
  border-radius: 2px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), #d48a7a);
  border-radius: 2px;
  transition: width 0.4s ease;
}
</style>
