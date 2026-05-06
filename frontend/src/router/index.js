import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'dashboard', component: () => import('../views/DashboardView.vue'), meta: { title: '搭建控制' } },
  { path: '/juming', name: 'juming', component: () => import('../views/JuMingView.vue'), meta: { title: '剧名链接' } },
  { path: '/promo-chain', name: 'promo-chain', component: () => import('../views/PromoChainView.vue'), meta: { title: '推广链生成' } },
  { path: '/promo-split', name: 'promo-split', component: () => import('../views/PromoSplitView.vue'), meta: { title: '推广链分割' } },
  { path: '/incentive-split', name: 'incentive-split', component: () => import('../views/IncentiveSplitView.vue'), meta: { title: '激励分割', mode: 'incentive' } },
  { path: '/material-push', name: 'material-push', component: () => import('../views/MaterialPushView.vue'), meta: { title: '素材推送' } },
  { path: '/incentive-chain', name: 'incentive-chain', component: () => import('../views/IncentiveChainView.vue'), meta: { title: '激励推广链', mode: 'incentive' } },
  { path: '/incentive-push', name: 'incentive-push', component: () => import('../views/IncentivePushView.vue'), meta: { title: '激励推送', mode: 'incentive' } },
  { path: '/incentive-link', name: 'incentive-link', component: () => import('../views/IncentiveLinkView.vue'), meta: { title: '激励链接', mode: 'incentive' } },
  { path: '/history', name: 'history', component: () => import('../views/HistoryView.vue'), meta: { title: '素材历史' } },
  { path: '/records', name: 'records', component: () => import('../views/RecordsView.vue'), meta: { title: '搭建记录' } },
  { path: '/crawl-material', name: 'crawl-material', component: () => import('../views/CrawlMaterialView.vue'), meta: { title: '爬取历史跑量素材' } },
  { path: '/rta-tool', name: 'rta-tool', component: () => import('../views/RtaToolView.vue'), meta: { title: 'RTA 工具' } },
  { path: '/daily-task', name: 'daily-task', component: () => import('../views/DailyTaskView.vue'), meta: { title: '每日任务' } },
  { path: '/settings', name: 'settings', component: () => import('../views/SettingsView.vue'), meta: { title: '设置' } },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
