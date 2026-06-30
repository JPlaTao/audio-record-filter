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
