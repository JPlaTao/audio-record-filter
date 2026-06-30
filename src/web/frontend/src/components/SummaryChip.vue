<template>
  <select v-if="field.type === 'enum'" :value="value" @change="onChange" class="chip-select">
    <option v-for="opt in field.options" :key="opt" :value="opt">{{ opt }}</option>
  </select>
  <input v-else type="text" :value="value" @input="onInput" class="chip-input" :placeholder="field.label" />
</template>

<script setup>
const props = defineProps({
  field: { type: Object, required: true },
  value: { type: String, default: '' },
})
const emit = defineEmits(['update:value'])
function onChange(e) { emit('update:value', e.target.value) }
function onInput(e) { emit('update:value', e.target.value) }
</script>

<style scoped>
.chip-select, .chip-input {
  font-family: var(--font-ui); font-size: 0.82rem;
  padding: 2px 6px; border: 1px solid var(--border);
  border-radius: var(--radius-sm); background: var(--bg-surface);
  color: var(--text-primary); width: 100%; min-width: 60px;
  transition: border-color var(--transition-fast);
}
.chip-select:focus, .chip-input:focus { outline: none; border-color: var(--accent); }
</style>
