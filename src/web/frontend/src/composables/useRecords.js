import { ref, computed } from 'vue'

export function useRecords() {
  const records = ref([])
  const searchQuery = ref('')
  const selectedIds = ref([])
  const fields = ref([])

  const filteredRecords = computed(() => {
    const q = searchQuery.value.toLowerCase().trim()
    if (!q) return records.value
    return records.value.filter(r =>
      r.file.toLowerCase().includes(q) ||
      (r.summary?.name || '').toLowerCase().includes(q)
    )
  })

  function setRecords(data) { records.value = data }
  function setFields(data) { fields.value = data }

  function addOrUpdateRecord(rec) {
    const idx = records.value.findIndex(r => r.id === rec.id)
    if (idx >= 0) records.value[idx] = rec
    else records.value.push(rec)
  }

  function removeRecord(id) {
    const idx = records.value.findIndex(r => r.id === id)
    if (idx >= 0) records.value.splice(idx, 1)
  }

  return {
    records, searchQuery, selectedIds, fields,
    filteredRecords,
    setRecords, setFields, addOrUpdateRecord, removeRecord,
  }
}
