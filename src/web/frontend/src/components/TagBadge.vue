<template>
  <span class="tag-badge" :class="`level-${level}`">
    {{ label }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  level: { type: String, default: 'beginner' },
})

const label = computed(() => {
  const m = { beginner: '初级', intermediate: '中级', advanced: '高级' }
  return m[props.level] || props.level
})
</script>

<style scoped>
.tag-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  font-family: var(--font-display);
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  border: 2px solid;
  line-height: 1;
  flex-shrink: 0;
}
.level-beginner { background: var(--level-beginner-bg); color: var(--level-beginner); border-color: var(--level-beginner); }
.level-intermediate { background: var(--level-intermediate-bg); color: var(--level-intermediate); border-color: var(--level-intermediate); }
.level-advanced { background: var(--level-advanced-bg); color: var(--level-advanced); border-color: var(--level-advanced); }
</style>
