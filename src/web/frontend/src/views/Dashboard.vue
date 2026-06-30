<template>
  <div class="dashboard">
    <section class="panel scan-section">
      <ScanToolbar
        :scanning="scanning"
        :processing="processing"
        :progress-percent="progressPercent"
        :file-count="fileList.length"
        :pending-count="pendingFiles.length"
        :selected-count="selectedFiles.length"
        @scan="onScan"
        @process="onProcess"
        @select-all-pending="selectAllPending"
        @clear-selection="clearSelection"
      />

      <ProgressBar :percent="progressPercent" v-if="processing" />

      <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>

      <table class="scan-table" v-if="fileList.length">
        <thead>
          <tr>
            <th style="width:30px"></th>
            <th>文件名</th>
            <th style="width:70px">状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in fileList" :key="f.name" class="scan-row">
            <td><input type="checkbox" :value="f.name" v-model="selectedFiles" /></td>
            <td class="file-name">{{ f.name }}</td>
            <td>
              <span class="status-pill" :class="f.status">{{ statusLabel(f.status) }}</span>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="!scanning" class="empty-state">
        <p class="empty-icon">&#128194;</p>
        <p>还没有档案，点击"扫描新录音"开始整理</p>
      </div>
    </section>

    <section class="panel records-section" v-if="records.length">
      <div class="records-header">
        <h2 class="section-title">
          档案列表
          <span class="count-badge">{{ records.length }}</span>
        </h2>
        <SearchInput v-model="searchQuery" />
      </div>

      <table>
        <thead>
          <tr>
            <th style="width:30px">
              <input type="checkbox" :checked="allSelected" @change="toggleAllRecords" />
            </th>
            <th>文件</th>
            <th v-for="field in fields" :key="field.key">{{ field.label }}</th>
            <th style="width:80px">操作</th>
          </tr>
        </thead>
        <tbody>
          <RecordCard
            v-for="rec in filteredRecords"
            :key="rec.id"
            :record="rec"
            :fields="fields"
            :selected="selectedIds.includes(rec.id)"
            @toggle="toggleRecord"
            @detail="showDetail"
            @reprocess="reprocessRecord"
            @update-field="onFieldUpdate"
          />
        </tbody>
      </table>

      <ExportBar :selected-count="selectedIds.length" @export="onExport" />
    </section>

    <div v-if="hasMissingNameWarning" class="missing-warning">
      &#9888;&#65039; 部分录音姓名未识别，请在表中填写
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchFields, fetchRecords, scanInput, processStream, exportZip, updateRecord } from '../api.js'
import { useRecords } from '../composables/useRecords.js'
import ScanToolbar from '../components/ScanToolbar.vue'
import ProgressBar from '../components/ProgressBar.vue'
import SearchInput from '../components/SearchInput.vue'
import RecordCard from '../components/RecordCard.vue'
import ExportBar from '../components/ExportBar.vue'

const router = useRouter()
const { records, searchQuery, selectedIds, fields, filteredRecords, setRecords, setFields, addOrUpdateRecord } = useRecords()

const fileList = ref([])
const selectedFiles = ref([])
const scanning = ref(false)
const processing = ref(false)
const progressPercent = ref(0)
const errorMsg = ref('')
const lastScanTime = ref('')

const pendingFiles = computed(() => fileList.value.filter(f => f.status === 'pending'))
const hasMissingNameWarning = computed(() =>
  records.value.some(r => !r.summary?.name || r.summary.name === '未识别')
)
const allSelected = computed(() =>
  filteredRecords.value.length > 0 && selectedIds.value.length === filteredRecords.value.length
)

onMounted(() => {
  fetchFields().then(setFields).catch(() => {})
  fetchRecords().then(setRecords).catch(() => {})
})

function statusLabel(s) {
  return { pending: '新录音', processing: '处理中', completed: '已完成', error: '失败' }[s] || s
}

async function onScan() {
  errorMsg.value = ''; scanning.value = true
  try {
    const data = await scanInput()
    fileList.value = data.files
    lastScanTime.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    selectedFiles.value = []
  } catch (e) { errorMsg.value = '扫描失败: ' + e.message }
  finally { scanning.value = false }
}

function selectAllPending() {
  selectedFiles.value = fileList.value.filter(f => f.status === 'pending').map(f => f.name)
}
function clearSelection() { selectedFiles.value = [] }

function onProcess() {
  errorMsg.value = ''; processing.value = true; progressPercent.value = 0
  const files = [...selectedFiles.value]
  const total = files.length || pendingFiles.value.length
  let done = 0, completed = false

  const es = processStream(files.length ? files : pendingFiles.value.map(f => f.name))

  fileList.value.forEach(f => {
    if ((files.length === 0 || files.includes(f.name)) && f.status === 'pending') f.status = 'processing'
  })

  es.addEventListener('progress', e => {
    const { file } = JSON.parse(e.data)
    const f = fileList.value.find(x => x.name === file)
    if (f) f.status = 'processing'
  })

  es.addEventListener('done', e => {
    const { file, record_id } = JSON.parse(e.data)
    done++; progressPercent.value = Math.round((done / total) * 100)
    const f = fileList.value.find(x => x.name === file)
    if (f) f.status = 'completed'
    fetch(`/api/records/${record_id}`).then(r => r.json()).then(rec => addOrUpdateRecord(rec)).catch(() => {})
  })

  es.addEventListener('error', e => {
    if (!e.data) return
    done++; progressPercent.value = Math.round((done / total) * 100)
    const { file } = JSON.parse(e.data)
    const f = fileList.value.find(x => x.name === file)
    if (f) f.status = 'error'
  })

  es.addEventListener('complete', () => { completed = true; es.close(); processing.value = false; progressPercent.value = 100 })
  es.onerror = () => {
    es.close(); processing.value = false
    if (!completed) {
      fileList.value.forEach(f => { if (f.status === 'processing') f.status = 'pending' })
      errorMsg.value = '处理连接断开，请确认服务器正常运行后重试'
    }
  }
}

function toggleRecord(id) {
  const idx = selectedIds.value.indexOf(id)
  idx >= 0 ? selectedIds.value.splice(idx, 1) : selectedIds.value.push(id)
}
function toggleAllRecords() {
  allSelected.value ? selectedIds.value = [] : selectedIds.value = filteredRecords.value.map(r => r.id)
}

function showDetail(rec) { router.push(`/record/${rec.id}`) }

async function reprocessRecord(rec) {
  if (!confirm(`确定要重新处理「${rec.file}」吗？`)) return
  errorMsg.value = ''
  await onScan()
  selectedFiles.value = [rec.file]
  fileList.value.forEach(f => { if (f.name === rec.file) f.status = 'pending' })
  const idx = records.value.findIndex(r => r.id === rec.id)
  if (idx >= 0) records.value.splice(idx, 1)
  onProcess()
}

async function onFieldUpdate({ id, key, value }) {
  const rec = records.value.find(r => r.id === id)
  if (!rec) return
  rec.summary[key] = value
  try { await updateRecord(id, rec.summary) } catch (e) { errorMsg.value = '保存失败' }
}

async function onExport() {
  if (!selectedIds.value.length) return
  try { await exportZip(selectedIds.value) } catch (e) { alert('导出失败') }
}
</script>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: var(--space-lg); }
.scan-section { padding-bottom: var(--space-md); }
.last-scan { font-family: var(--font-ui); font-size: 0.78rem; color: var(--text-muted); }
.error-msg {
  background: #fef0ed; border: 1px solid #f5c6bc; color: var(--accent);
  padding: 8px 12px; border-radius: var(--radius-md); font-size: 0.85rem; margin-top: var(--space-sm);
}
.scan-table { margin-top: var(--space-md); }
.scan-row .file-name { font-family: var(--font-ui); font-size: 0.85rem; }
.status-pill {
  display: inline-block; padding: 2px 10px; border-radius: 10px;
  font-family: var(--font-ui); font-size: 0.75rem; font-weight: 600;
}
.status-pill.pending { background: var(--bg-surface-alt); color: var(--text-muted); border: 1px solid var(--border); }
.status-pill.processing { background: var(--accent-light); color: var(--accent); }
.status-pill.completed { background: var(--level-beginner-bg); color: var(--level-beginner); }
.status-pill.error { background: var(--level-advanced-bg); color: var(--level-advanced); }
.empty-state { text-align: center; padding: 40px 0; color: var(--text-muted); }
.empty-icon { font-size: 2.5rem; margin-bottom: 8px; }
.records-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-md); }
.section-title { font-family: var(--font-display); font-size: 1.2rem; display: flex; align-items: center; gap: 8px; }
.count-badge {
  font-family: var(--font-ui); font-size: 0.75rem; background: var(--bg-surface-alt);
  color: var(--text-secondary); padding: 1px 8px; border-radius: 10px;
}
.missing-warning { margin-top: 8px; font-size: 0.82rem; color: #b8944a; }
</style>
