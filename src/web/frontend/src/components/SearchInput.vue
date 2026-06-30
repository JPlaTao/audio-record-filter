<template>
  <div class="search-wrapper">
    <span class="search-icon">&#128269;</span>
    <input
      type="text"
      class="search-input"
      :value="modelValue"
      @input="$emit('update:modelValue', $event.target.value)"
      placeholder="搜索姓名或文件名…"
    />
  </div>
</template>

<script setup>
defineProps({ modelValue: String })
defineEmits(['update:modelValue'])
</script>

<style scoped>
.search-wrapper { position: relative; width: 200px; }
.search-icon {
  position: absolute; left: 10px; top: 50%; transform: translateY(-50%);
  font-size: 0.85rem; opacity: 0.5; pointer-events: none;
}
.search-input {
  width: 100%; padding: 6px 10px 6px 30px;
  border: none; border-bottom: 1.5px solid var(--border);
  background: transparent; font-family: var(--font-ui);
  font-size: 0.85rem; color: var(--text-primary);
  transition: border-color var(--transition-fast);
}
.search-input:focus { outline: none; border-bottom-color: var(--accent); }
.search-input::placeholder { color: var(--text-muted); }
</style>
