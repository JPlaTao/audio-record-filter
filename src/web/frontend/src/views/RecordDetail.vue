<template>
  <div class="detail-page" v-if="record">
    <nav class="breadcrumb">
      <router-link to="/" class="breadcrumb-link">首页</router-link>
      <span class="breadcrumb-sep">/</span>
      <span class="breadcrumb-current">{{ record.file }}</span>
    </nav>

    <div class="detail-header">
      <div class="detail-title">
        <TagBadge :level="record.level" />
        <div>
          <h1>{{ record.file }}</h1>
          <span class="detail-meta">
            {{ Math.round(record.duration || 0) }}s &middot;
            {{ { beginner: '初级', intermediate: '中级', advanced: '高级' }[record.level] || record.level }}
            ({{ Math.round(record.score * 100) }}%)
          </span>
        </div>
      </div>
      <button class="btn" @click="$router.push('/')">&larr; 返回列表</button>
    </div>

    <div class="detail-grid">
      <div class="detail-transcript panel">
        <h3>文字稿</h3>
        <pre class="transcript-body">{{ record.transcript || '(暂无文字稿)' }}</pre>
      </div>

      <div class="detail-analysis">
        <div class="panel analysis-card" v-if="record.details?.llm_reasoning">
          <h3>&#129302; LLM 深度分析</h3>
          <div class="analysis-llm">
            <p>{{ record.details.llm_reasoning }}</p>
            <p class="analysis-score" v-if="record.details.llm_level">
              LLM 评分: {{ { beginner: '初级', intermediate: '中级', advanced: '高级' }[record.details.llm_level] || record.details.llm_level }}
              ({{ Math.round((record.details.llm_score || 0) * 100) }}%)
            </p>
          </div>
        </div>

        <div class="panel analysis-card" v-if="record.details?.quality">
          <h3>&#128202; 通话质量分析</h3>
          <div class="quality-grid">
            <div class="quality-item" v-for="sig in record.details.quality.signals" :key="sig.key">
              <span class="quality-label">{{ sig.label }}</span>
              <span class="quality-value">{{ sig.value }}</span>
              <span class="quality-assess" :class="assessClass(sig.assessment)">{{ sig.assessment }}</span>
            </div>
          </div>
          <div class="quality-overall">
            综合质量分: <strong>{{ record.details.quality.overall_score }}</strong>
          </div>
        </div>

        <div class="panel analysis-card" v-if="record.details">
          <h3>&#128203; 规则分析</h3>
          <p class="rule-summary">完成 {{ record.details.completed_steps }}/{{ record.details.total_steps }} 个步骤</p>
          <div class="step-list">
            <span v-for="s in record.details.step_results" :key="s.step_name"
              class="step-pill" :class="{ 'step-done': s.matched, 'step-miss': !s.matched }"
            >{{ s.matched ? '&#9989;' : '&#11093;' }}{{ s.step_name }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="loading-state" v-else-if="loading"><p>加载中&hellip;</p></div>
  <div class="error-state" v-else>
    <p>&#10060; 记录未找到</p>
    <router-link to="/" class="btn">返回首页</router-link>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { fetchRecord } from '../api.js'
import TagBadge from '../components/TagBadge.vue'

const route = useRoute()
const record = ref(null)
const loading = ref(true)

onMounted(async () => {
  try { record.value = await fetchRecord(route.params.id) }
  catch (e) { record.value = null }
  finally { loading.value = false }
})

function assessClass(a) {
  return { '优秀': 'assess-great', '良好': 'assess-good', '一般': 'assess-ok', '差': 'assess-bad' }[a] || ''
}
</script>

<style scoped>
.detail-page { display: flex; flex-direction: column; gap: var(--space-lg); }
.breadcrumb { font-family: var(--font-ui); font-size: 0.82rem; color: var(--text-muted); }
.breadcrumb-link { color: var(--accent); text-decoration: none; }
.breadcrumb-link:hover { text-decoration: underline; }
.breadcrumb-sep { margin: 0 8px; }
.breadcrumb-current { color: var(--text-secondary); }
.detail-header { display: flex; justify-content: space-between; align-items: flex-start; }
.detail-title { display: flex; align-items: center; gap: var(--space-md); }
.detail-title h1 { font-family: var(--font-ui); font-size: 1.2rem; font-weight: 600; margin-bottom: 2px; }
.detail-meta { font-family: var(--font-ui); font-size: 0.82rem; color: var(--text-muted); }
.detail-grid { display: grid; grid-template-columns: 1fr 380px; gap: var(--space-lg); align-items: start; }
@media (max-width: 900px) { .detail-grid { grid-template-columns: 1fr; } }
.transcript-body {
  font-family: var(--font-ui); font-size: 0.85rem; line-height: 1.7;
  white-space: pre-wrap; max-height: 70vh; overflow-y: auto;
  background: var(--bg-surface-alt); padding: var(--space-md);
  border-radius: var(--radius-md); margin-top: var(--space-sm);
}
.detail-analysis { display: flex; flex-direction: column; gap: var(--space-md); }
.analysis-card h3 {
  font-family: var(--font-ui); font-size: 0.82rem; font-weight: 600;
  color: var(--text-secondary); margin-bottom: var(--space-sm);
}
.analysis-llm {
  background: #fdf6f0; padding: 12px; border-radius: var(--radius-md);
  border-left: 3px solid var(--accent);
}
.analysis-llm p { font-size: 0.85rem; line-height: 1.6; }
.analysis-score { margin-top: 8px; font-weight: 600; color: var(--accent); }
.quality-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.quality-item {
  display: flex; flex-direction: column; gap: 2px; padding: 8px;
  background: var(--bg-surface-alt); border-radius: var(--radius-sm);
}
.quality-label { font-family: var(--font-ui); font-size: 0.72rem; color: var(--text-muted); }
.quality-value { font-family: var(--font-ui); font-size: 1rem; font-weight: 600; }
.quality-assess { font-family: var(--font-ui); font-size: 0.72rem; }
.assess-great { color: var(--level-beginner); }
.assess-good { color: var(--level-intermediate); }
.assess-ok { color: #8a7a60; }
.assess-bad { color: var(--level-advanced); }
.quality-overall { margin-top: 8px; text-align: right; font-family: var(--font-ui); font-size: 0.82rem; color: var(--text-muted); }
.rule-summary { font-family: var(--font-ui); font-size: 0.85rem; margin-bottom: var(--space-sm); }
.step-list { display: flex; flex-wrap: wrap; gap: 4px; }
.step-pill { font-family: var(--font-ui); font-size: 0.75rem; padding: 2px 6px; border-radius: var(--radius-sm); }
.step-done { background: var(--level-beginner-bg); color: var(--level-beginner); }
.step-miss { background: var(--bg-surface-alt); color: var(--text-muted); }
.loading-state, .error-state { text-align: center; padding: 60px 0; color: var(--text-muted); }
</style>
