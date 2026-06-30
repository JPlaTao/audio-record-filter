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
