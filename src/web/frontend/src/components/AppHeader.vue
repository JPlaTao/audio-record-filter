<template>
  <header class="app-header">
    <div class="header-inner">
      <router-link to="/" class="brand">
        <span class="brand-icon">&#9776;</span>
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
