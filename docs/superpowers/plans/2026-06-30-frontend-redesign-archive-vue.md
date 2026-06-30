# 前端重构实现计划 — 档案室

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前 Vue 3 CDN 单 HTML 文件重构成 Vite + Vue 3 SFC + Vue Router 多页面项目。视觉设计为"档案室"风格（暖亮色、衬线字体、火漆徽章）。适配 13 寸笔记本屏幕。

**Architecture:** Vite 构建项目放在 `src/web/frontend/`，build 产物输出到 `src/web/static/`（FastAPI 已挂载的静态目录），后端代码零改动。

**Tech Stack:** Vue 3 (Composition API + `<script setup>`)、Vite、Vue Router 4、手写 CSS（无 Tailwind/UI 库）、Google Fonts（Instrument Serif + Spectral + Karla）

## Global Constraints

- 所有 UI 文本使用中文
- 不引入任何 UI 组件库（Tailwind、daisyUI、Element Plus 等）
- 构建产物输出到 `src/web/static/`，覆盖旧的 index.html
- 颜色方案：暖白纸色背景 `#f5f0eb`、朱砂红主色 `#b84a3a`、暖褐次级 `#7a6b5d`
- 等级标签：初级 `#6b8f71`、中级 `#b8944a`、高级 `#a84a4a`
- 每次 commit 消息以 `feat(web):` 或 `fix(web):` 开头

---


- 所有 UI 文本使用中文
- 不引入任何 UI 组件库（Tailwind、daisyUI、Element Plus 等）
- 构建产物输出到 `src/web/static/`，覆盖旧的 index.html
- 后端改文件名/目录等操作完成后重建 static 目录
- 颜色方案：暖白纸色背景 `#f5f0eb`、朱砂红主色 `#b84a3a`、暖褐次级 `#7a6b5d`
- 等级标签：初级 `#6b8f71`、中级 `#b8944a`、高级 `#a84a4a`
- 每次 commit 消息以 `feat(web):` 或 `fix(web):` 开头

---

## File Structure

```
src/web/
├── __init__.py
├── app.py                  # FastAPI（不改动）
├── config.py               # 字段配置（不改动）
├── frontend/               # ← 新建：Vite 项目根
│   ├── index.html          # Vite 入口 HTML
│   ├── package.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── main.js         # Vue 入口
│   │   ├── router.js       # Vue Router
│   │   ├── App.vue         # 根组件
│   │   ├── style.css       # 全局样式 + CSS 自定义属性
│   │   ├── api.js          # API 封装层
│   │   ├── composables/
│   │   │   └── useRecords.js
│   │   ├── components/
│   │   │   ├── AppHeader.vue
│   │   │   ├── TagBadge.vue
│   │   │   ├── ScanToolbar.vue
│   │   │   ├── RecordCard.vue
│   │   │   ├── SummaryChip.vue
│   │   │   ├── SearchInput.vue
│   │   │   ├── ExportBar.vue
│   │   │   └── ProgressBar.vue
│   │   └── views/
│   │       ├── Dashboard.vue
│   │       └── RecordDetail.vue
├── static/                 # Vite build 产物（覆盖旧 index.html）
│   ├── index.html
│   ├── assets/
│   └── ...
└── __pycache__/
```

---

### Task 1: 脚手架 — Vite + Vue 3 项目初始化

**Files:**
- Create: `src/web/frontend/package.json`
- Create: `src/web/frontend/vite.config.js`
- Create: `src/web/frontend/index.html`
- Create: `src/web/frontend/src/main.js`
- Create: `src/web/frontend/src/App.vue`
- Create: `src/web/frontend/src/router.js`

**Interfaces:**
- Produces: Scaffolded Vite project with vue-router. Build output goes to `../static/`.

- [ ] **Step 1: Create `src/web/frontend/package.json`**

```json
{
  "name": "audio-record-filter-frontend",
  "version": "0.3.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.5",
    "vue-router": "^4.5"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2",
    "vite": "^6.3"
  }
}
```

- [ ] **Step 2: Create `src/web/frontend/vite.config.js`**

```js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  root: '.',
  base: '/',
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8080',
    },
  },
})
```

`proxy` 让 `vite dev` 时 `/api/*` 请求自动转发到 FastAPI。

- [ ] **Step 3: Create `src/web/frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>通话录音分级系统</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Spectral:ital,wght@0,300;0,400;0,600;1,400&family=Karla:wght@400;500;600;700&display=swap" rel="stylesheet">
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

- [ ] **Step 4: Create `src/web/frontend/src/main.js`**

```js
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)
app.use(router)
app.mount('#app')
```

- [ ] **Step 5: Create `src/web/frontend/src/router.js`**

```js
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'dashboard',
    component: () => import('./views/Dashboard.vue'),
  },
  {
    path: '/record/:id',
    name: 'record-detail',
    component: () => import('./views/RecordDetail.vue'),
  },
  // Reserved for future expansion
  // { path: '/settings', name: 'settings', component: () => import('./views/Settings.vue') },
  // { path: '/trends', name: 'trends', component: () => import('./views/Trends.vue') },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
```

`createWebHistory()` = 无 `#` 的 URL。FastAPI `StaticFiles(html=True)` 自动 fallback 到 index.html。

- [ ] **Step 6: Create `src/web/frontend/src/App.vue`**（框架骨架）

```vue
<template>
  <div class="app-layout">
    <AppHeader />
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import AppHeader from './components/AppHeader.vue'
</script>

<style scoped>
.app-layout {
  max-width: 1100px;
  margin: 0 auto;
  padding: 0 20px 40px;
  min-height: 100vh;
}
.main-content {
  margin-top: 24px;
}
</style>
```

- [ ] **Step 7: Install and verify**

```bash
cd src/web/frontend
pnpm install
pnpm run build
```

Verify: `ls ../static/` 显示 `index.html` 和 `assets/` 目录。`index.html` 中引用的 JS/CSS 路径正确（如 `/assets/index-xxxxx.js`）。

- [ ] **Step 8: Commit**

```bash
git add src/web/frontend/
git commit -m "feat(web): scaffold Vite + Vue 3 project with router"
```

---

### Task 2: 全局样式设计系统 + API 层

**Files:**
- Create: `src/web/frontend/src/style.css`
- Create: `src/web/frontend/src/api.js`

**Interfaces:**
- Consumes: Vite project from Task 1
- Produces: Global CSS custom properties + fetch-based API layer
- Consumed by: All components and views in later tasks

- [ ] **Step 1: Create `src/web/frontend/src/style.css`**

```css
/* ── Design tokens ──────────────────────────────────── */
:root {
  /* Colors */
  --bg-page: #f5f0eb;
  --bg-surface: #ffffff;
  --bg-surface-alt: #faf7f3;
  --bg-hover: #f3ede6;
  --text-primary: #2a2a2a;
  --text-secondary: #7a6b5d;
  --text-muted: #b0a090;
  --border: #e5ddd5;
  --border-light: #f0eae3;
  --accent: #b84a3a;
  --accent-hover: #a03d2e;
  --accent-light: #fdf0ed;

  /* Level colors (fire seal badges) */
  --level-beginner: #6b8f71;
  --level-beginner-bg: #eef5ef;
  --level-intermediate: #b8944a;
  --level-intermediate-bg: #faf5ea;
  --level-advanced: #a84a4a;
  --level-advanced-bg: #fceeef;

  /* Typography */
  --font-display: 'Instrument Serif', Georgia, serif;
  --font-body: 'Spectral', Georgia, serif;
  --font-ui: 'Karla', -apple-system, sans-serif;

  /* Spacing */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.06);
  --shadow-md: 0 2px 8px rgba(0,0,0,0.08);
  --shadow-lg: 0 4px 24px rgba(0,0,0,0.10);

  /* Radiuses */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;

  /* Transitions */
  --transition-fast: 150ms ease;
  --transition-normal: 250ms ease;
}

/* ── Reset & Base ────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html { font-size: 15px; }

body {
  font-family: var(--font-body);
  background: var(--bg-page);
  color: var(--text-primary);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}

/* ── Typography helpers ──────────────────────────────── */
h1, h2, h3 { font-family: var(--font-display); font-weight: 400; }
h1 { font-size: 1.8rem; }
h2 { font-size: 1.4rem; }
h3 { font-size: 1.15rem; }

/* ── Common button styles ───────────────────────────── */
.btn {
  font-family: var(--font-ui);
  font-weight: 500;
  font-size: 0.85rem;
  padding: 6px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-primary);
  cursor: pointer;
  transition: all var(--transition-fast);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.btn:hover { background: var(--bg-hover); border-color: var(--text-muted); }
.btn:active { transform: scale(0.97); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

.btn-accent { background: var(--accent); color: #fff; border-color: var(--accent); }
.btn-accent:hover { background: var(--accent-hover); border-color: var(--accent-hover); }
.btn-accent:disabled { background: #d4a090; border-color: #d4a090; }

.btn-ghost { border-color: transparent; background: transparent; color: var(--text-secondary); }
.btn-ghost:hover { background: var(--bg-hover); color: var(--text-primary); }

/* ── Panel / card ───────────────────────────────────── */
.panel {
  background: var(--bg-surface);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-light);
}

/* ── Table ──────────────────────────────────────────── */
table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border-light); }
th { font-family: var(--font-ui); font-weight: 600; color: var(--text-secondary); font-size: 0.78rem; letter-spacing: 0.02em; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: var(--bg-hover); }

/* ── Link-like ──────────────────────────────────────── */
.link-like { font-family: var(--font-ui); font-size: 0.82rem; color: var(--accent); cursor: pointer; }
.link-like:hover { text-decoration: underline; }

/* ── Input ──────────────────────────────────────────── */
input[type="text"], select {
  font-family: var(--font-ui);
  font-size: 0.85rem;
  padding: 4px 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  color: var(--text-primary);
  width: 100%;
}
input[type="text"]:focus, select:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-light);
}

/* ── Scrollbar ──────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

/* ── Selection ──────────────────────────────────────── */
::selection { background: var(--accent-light); color: var(--accent); }
```

- [ ] **Step 2: Create `src/web/frontend/src/api.js`**

```js
const BASE = ''

async function getJSON(url) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json()
}

export async function fetchFields() {
  return getJSON(`${BASE}/api/fields`)
}

export async function scanInput() {
  return getJSON(`${BASE}/api/scan`)
}

export async function fetchRecords(search = '') {
  const qs = search ? `?search=${encodeURIComponent(search)}` : ''
  return getJSON(`${BASE}/api/records${qs}`)
}

export async function fetchRecord(id) {
  return getJSON(`${BASE}/api/records/${encodeURIComponent(id)}`)
}

export async function updateRecord(id, summary) {
  const res = await fetch(`${BASE}/api/records/${encodeURIComponent(id)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ summary }),
  })
  if (!res.ok) throw new Error(`Update failed: ${res.status}`)
  return res.json()
}

export function processStream(files) {
  const params = files ? `?files=${encodeURIComponent(files.join(','))}` : ''
  return new EventSource(`${BASE}/api/process${params}`)
}

export async function exportZip(recordIds) {
  const res = await fetch(`${BASE}/api/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ record_ids: recordIds }),
  })
  if (!res.ok) throw new Error(`Export failed: ${res.status}`)
  const disposition = res.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename\*=UTF-8''(.+?)(?:;|$)/)
        || disposition.match(/filename="?(.+?)"?$/)
  const filename = match ? decodeURIComponent(match[1]) : 'export.zip'
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
```

- [ ] **Step 3: Build and verify**

```bash
pnpm build
```

No errors expected. Verify `../static/` contains the built assets.

- [ ] **Step 4: Commit**

```bash
git add src/web/frontend/src/style.css src/web/frontend/src/api.js
git commit -m "feat(web): add design tokens and API layer"
```

---

### Task 3: AppHeader + TagBadge + ProgressBar 基础组件

**Files:**
- Create: `src/web/frontend/src/components/AppHeader.vue`
- Create: `src/web/frontend/src/components/TagBadge.vue`
- Create: `src/web/frontend/src/components/ProgressBar.vue`

**Interfaces:**
- `AppHeader` — no props, renders top bar with brand name and nav
- `TagBadge({ level: string })` — renders fire-seal styled level badge (circular badge)
- `ProgressBar({ percent: number })` — thin progress indicator bar

- [ ] **Step 1: Create `src/web/frontend/src/components/AppHeader.vue`**

```vue
<template>
  <header class="app-header">
    <div class="header-inner">
      <router-link to="/" class="brand">
        <span class="brand-icon">☰</span>
        <span class="brand-text">录音档案</span>
        <span class="brand-badge">v0.3</span>
      </router-link>

      <nav class="header-nav">
        <router-link to="/" class="nav-link" :class="{ 'nav-active': $route.path === '/' }">
          首页
        </router-link>
        <span class="nav-link nav-disabled" title="即将推出">趋势</span>
        <span class="nav-link nav-disabled" title="即将推出">设置</span>
      </nav>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  padding: 16px 0 12px;
  border-bottom: 1px solid var(--border-light);
}
.header-inner {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}
.brand {
  display: flex;
  align-items: baseline;
  gap: 8px;
  text-decoration: none;
  color: var(--text-primary);
}
.brand-icon { font-size: 1.4rem; color: var(--accent); }
.brand-text {
  font-family: var(--font-display);
  font-size: 1.5rem;
  font-weight: 400;
}
.brand-badge {
  font-family: var(--font-ui);
  font-size: 0.7rem;
  color: var(--text-muted);
  border: 1px solid var(--border);
  border-radius: 3px;
  padding: 1px 6px;
}
.header-nav { display: flex; gap: 20px; }
.nav-link {
  font-family: var(--font-ui);
  font-size: 0.85rem;
  color: var(--text-secondary);
  text-decoration: none;
  cursor: pointer;
}
.nav-link:hover { color: var(--text-primary); }
.nav-active { color: var(--accent); font-weight: 600; }
.nav-disabled { opacity: 0.4; cursor: default; }
.nav-disabled:hover { color: var(--text-secondary); }
</style>
```

- [ ] **Step 2: Create `src/web/frontend/src/components/TagBadge.vue`**

```vue
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
```

- [ ] **Step 3: Create `src/web/frontend/src/components/ProgressBar.vue`**

```vue
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
```

- [ ] **Step 4: Build and commit**

```bash
pnpm build
git add src/web/frontend/src/components/AppHeader.vue src/web/frontend/src/components/TagBadge.vue src/web/frontend/src/components/ProgressBar.vue
git commit -m "feat(web): add AppHeader, TagBadge, ProgressBar components"
```

---

### Task 4: ScanToolbar + SearchInput + SummaryChip + ExportBar 操作组件

**Files:**
- Create: `src/web/frontend/src/components/ScanToolbar.vue`
- Create: `src/web/frontend/src/components/SearchInput.vue`
- Create: `src/web/frontend/src/components/SummaryChip.vue`
- Create: `src/web/frontend/src/components/ExportBar.vue`

**Interfaces:**
- `ScanToolbar` — emits: `scan`, `process`, `selectAllPending`, `clearSelection`; props: scanning/processing/progressPercent/fileCount/pendingCount/selectedCount
- `SearchInput` — v-model compatible
- `SummaryChip` — displays editable dropdown/input for summary field
- `ExportBar` — shows selected count + export button

- [ ] **Step 1: Create `src/web/frontend/src/components/ScanToolbar.vue`**

```vue
<template>
  <div class="scan-toolbar">
    <button class="btn" :disabled="scanning" @click="$emit('scan')">
      <template v-if="scanning">⟳ 扫描中...</template>
      <template v-else>🔍 扫描新录音</template>
    </button>
    <button
      class="btn btn-accent"
      :disabled="processing || pendingCount === 0"
      @click="$emit('process')"
    >
      ▶ 处理选中 <template v-if="processing">({{ progressPercent }}%)</template>
    </button>
    <button class="btn btn-ghost" :disabled="!fileCount" @click="$emit('selectAllPending')">
      ☑ 全选未处理
    </button>
    <button class="btn btn-ghost" :disabled="!selectedCount" @click="$emit('clearSelection')">
      ✕ 清空选择
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
```

- [ ] **Step 2: Create `src/web/frontend/src/components/SearchInput.vue`**

```vue
<template>
  <div class="search-wrapper">
    <span class="search-icon">🔍</span>
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
```

- [ ] **Step 3: Create `src/web/frontend/src/components/SummaryChip.vue`**

```vue
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
```

- [ ] **Step 4: Create `src/web/frontend/src/components/ExportBar.vue`**

```vue
<template>
  <div class="export-bar" v-if="selectedCount">
    <span class="export-info">已选 {{ selectedCount }} 条</span>
    <button class="btn btn-accent" @click="$emit('export')">📦 打包导出</button>
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
```

- [ ] **Step 5: Build and commit**

```bash
pnpm build
git add src/web/frontend/src/components/ScanToolbar.vue src/web/frontend/src/components/SearchInput.vue src/web/frontend/src/components/SummaryChip.vue src/web/frontend/src/components/ExportBar.vue
git commit -m "feat(web): add ScanToolbar, SearchInput, SummaryChip, ExportBar"
```

---

### Task 5: RecordCard + useRecords composable

**Files:**
- Create: `src/web/frontend/src/components/RecordCard.vue`
- Create: `src/web/frontend/src/composables/useRecords.js`

**Interfaces:**
- `RecordCard({ record, fields, selected })` — emits: `toggle`, `detail`, `reprocess`, `update-field`
- `useRecords()` — returns reactive records state, CRUD methods

- [ ] **Step 1: Create `src/web/frontend/src/composables/useRecords.js`**

```js
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
```

- [ ] **Step 2: Create `src/web/frontend/src/components/RecordCard.vue`**

```vue
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
```

- [ ] **Step 3: Build and commit**

```bash
pnpm build
git add src/web/frontend/src/composables/useRecords.js src/web/frontend/src/components/RecordCard.vue
git commit -m "feat(web): add RecordCard and useRecords composable"
```

---

### Task 6: Dashboard 首页

**Files:**
- Create: `src/web/frontend/src/views/Dashboard.vue`

**Interfaces:**
- Consumes: `api.js`, `useRecords.js`, all components from Tasks 3-5
- Produces: Full dashboard page with scan toolbar, record table, export bar, progress

- [ ] **Step 1: Create `src/web/frontend/src/views/Dashboard.vue`**

```vue
<template>
  <div class="dashboard">
    <!-- Scan & process panel -->
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
      >
        <template #extra>
          <span class="last-scan" v-if="lastScanTime">
            上次扫描: {{ lastScanTime }}
          </span>
        </template>
      </ScanToolbar>

      <ProgressBar :percent="progressPercent" v-if="processing" />

      <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>

      <!-- Scan file list -->
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
        <p class="empty-icon">📂</p>
        <p>还没有档案，点击"扫描新录音"开始整理</p>
      </div>
    </section>

    <!-- Records panel -->
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
      ⚠️ 部分录音姓名未识别，请在表中填写
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
```

- [ ] **Step 2: Build and verify**

```bash
pnpm build
```

Open browser at `http://localhost:8080/`. Verify:
- Page loads with header, empty state
- Click "扫描新录音" — file list appears
- Select files → "▶ 处理选中" triggers SSE processing
- Records appear in the bottom panel with editable fields
- "☑ 全选未处理" / "✕ 清空选择" work
- Search filters records
- "详情" link navigates to `/record/:id`
- "重新处理" triggers confirm + reprocess flow
- "📦 打包导出" works

- [ ] **Step 3: Commit**

```bash
git add src/web/frontend/src/views/Dashboard.vue
git commit -m "feat(web): add Dashboard page with scan, process, and record table"
```

---

### Task 7: RecordDetail 详情页

**Files:**
- Create: `src/web/frontend/src/views/RecordDetail.vue`

**Interfaces:**
- Route: `/record/:id`
- Consumes: `api.js` (`fetchRecord`)
- Renders: Full detail view with transcript + analysis panels

- [ ] **Step 1: Create `src/web/frontend/src/views/RecordDetail.vue`**

```vue
<template>
  <div class="detail-page" v-if="record">
    <!-- Breadcrumb -->
    <nav class="breadcrumb">
      <router-link to="/" class="breadcrumb-link">首页</router-link>
      <span class="breadcrumb-sep">/</span>
      <span class="breadcrumb-current">{{ record.file }}</span>
    </nav>

    <!-- Header -->
    <div class="detail-header">
      <div class="detail-title">
        <TagBadge :level="record.level" />
        <div>
          <h1>{{ record.file }}</h1>
          <span class="detail-meta">
            {{ Math.round(record.duration || 0) }}s ·
            {{ { beginner: '初级', intermediate: '中级', advanced: '高级' }[record.level] || record.level }}
            ({{ Math.round(record.score * 100) }}%)
          </span>
        </div>
      </div>
      <button class="btn" @click="$router.push('/')">← 返回列表</button>
    </div>

    <div class="detail-grid">
      <!-- Left: Transcript -->
      <div class="detail-transcript panel">
        <h3>文字稿</h3>
        <pre class="transcript-body">{{ record.transcript || '(暂无文字稿)' }}</pre>
      </div>

      <!-- Right: Analysis -->
      <div class="detail-analysis">
        <!-- LLM Analysis -->
        <div class="panel analysis-card" v-if="record.details?.llm_reasoning">
          <h3>🤖 LLM 深度分析</h3>
          <div class="analysis-llm">
            <p>{{ record.details.llm_reasoning }}</p>
            <p class="analysis-score" v-if="record.details.llm_level">
              LLM 评分: {{ { beginner: '初级', intermediate: '中级', advanced: '高级' }[record.details.llm_level] || record.details.llm_level }}
              ({{ Math.round((record.details.llm_score || 0) * 100) }}%)
            </p>
          </div>
        </div>

        <!-- Quality signals -->
        <div class="panel analysis-card" v-if="record.details?.quality">
          <h3>📊 通话质量分析</h3>
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

        <!-- Rule analysis -->
        <div class="panel analysis-card" v-if="record.details">
          <h3>📋 规则分析</h3>
          <p class="rule-summary">完成 {{ record.details.completed_steps }}/{{ record.details.total_steps }} 个步骤</p>
          <div class="step-list">
            <span v-for="s in record.details.step_results" :key="s.step_name"
              class="step-pill" :class="{ 'step-done': s.matched, 'step-miss': !s.matched }"
            >{{ s.matched ? '✅' : '⭕' }}{{ s.step_name }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="loading-state" v-else-if="loading"><p>加载中…</p></div>
  <div class="error-state" v-else>
    <p>❌ 记录未找到</p>
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
  return { 优秀: 'assess-great', 良好: 'assess-good', 一般: 'assess-ok', 差: 'assess-bad' }[a] || ''
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
```

- [ ] **Step 2: Build and verify**

```bash
pnpm build
```

Verify in browser:
- Navigate from dashboard to detail page
- Detail page shows breadcrumb, header, transcript, LLM analysis, quality, rule analysis
- "← 返回列表" works
- Direct URL `/record/xxx` loads correctly

- [ ] **Step 3: Commit**

```bash
git add src/web/frontend/src/views/RecordDetail.vue
git commit -m "feat(web): add RecordDetail page with full analysis view"
```

---

### Task 8: FastAPI 适配 — Build + SPA fallback 验证

**Files:**
- No code changes expected; verification only

**Interfaces:**
- Consumes: Vite build output at `src/web/static/`
- Produces: Verified FastAPI SPA fallback

- [ ] **Step 1: Build frontend**

```bash
cd src/web/frontend && pnpm build && cd ../../..
```

- [ ] **Step 2: Start server and verify**

```bash
venv/Scripts/python.exe -c "
from dotenv import load_dotenv; load_dotenv()
import uvicorn; from src.web.app import app
uvicorn.run(app, host='127.0.0.1', port=8080, log_level='info')
"
```

In another terminal:
```bash
# Main page loads (contains new brand text)
curl -s http://localhost:8080/ | grep -c "录音档案"

# SPA fallback works for unknown routes
curl -s http://localhost:8080/record/test-123 | grep -c "录音档案"

# API endpoints still work
curl -s http://localhost:8080/api/records | head -c 100
```

- [ ] **Step 3: Commit final build output**

```bash
git add src/web/static/
git commit -m "feat(web): build frontend to static/ directory"
```

---

### Self-Review Checklist

**1. Spec coverage:** 每个功能点是否有对应任务？
- Vite 脚手架 → Task 1
- 设计系统（颜色、字体、CSS 变量） → Task 2
- 品牌导航和等级标签 → Task 3
- 扫描、处理、搜索、导出操作 → Task 4
- 记录列表和状态管理 → Task 5
- Dashboard 首页 → Task 6
- 详情页 → Task 7
- FastAPI 集成验证 → Task 8
- 预留扩展（Settings, Trends） → router.js 注释预留路由

**2. Placeholder scan:** 所有代码块包含完整实现，无 TBD。

**3. Type consistency:**
- `TagBadge({ level })` 在 RecordCard 和 RecordDetail 中一致使用
- `api.js` 的函数签名在 Dashboard 和 RecordDetail 中一致
- SSE 事件名（`progress`, `done`, `error`, `complete`）与后端匹配
- 后端响应字段（`details.llm_reasoning`, `details.quality.signals` 等）匹配实际 API