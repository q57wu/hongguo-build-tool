<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="sidebar-header">
        <span class="logo">🍎</span>
        <div class="title-group">
          <h1 class="app-title">红果搭建工具</h1>
          <p class="app-subtitle">Hongguo Build Console</p>
        </div>
      </div>

      <!-- 模式切换 Tab -->
      <div class="mode-switcher">
        <button
          :class="{ active: uiStore.workMode === 'normal' }"
          @click="uiStore.setWorkMode('normal')"
        >单本</button>
        <button
          :class="{ active: uiStore.workMode === 'incentive' }"
          @click="uiStore.setWorkMode('incentive')"
        >激励</button>
      </div>

      <nav class="nav-list">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: $route.path === item.path }"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span class="nav-label">{{ item.title }}</span>
        </router-link>

        <!-- 底部独立项 -->
        <div class="nav-divider"></div>
        <router-link to="/daily-task" class="nav-item" :class="{ active: $route.path === '/daily-task' }">
          <span class="nav-icon">✅</span>
          <span class="nav-label">每日任务</span>
        </router-link>
        <router-link to="/records" class="nav-item" :class="{ active: $route.path === '/records' }">
          <span class="nav-icon">📊</span>
          <span class="nav-label">搭建记录</span>
        </router-link>
        <router-link to="/settings" class="nav-item" :class="{ active: $route.path === '/settings' }">
          <span class="nav-icon">⚙️</span>
          <span class="nav-label">投放配置</span>
        </router-link>
      </nav>
    </aside>
    <main class="main-content">
      <router-view v-slot="{ Component, route }">
        <transition name="page" mode="out-in">
          <component :is="Component" :key="route.path" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useBackendEvents } from './composables/useEvents'
import { useBuildStore } from './stores/build'
import { useUiStore } from './stores/ui'

useBackendEvents()
const buildStore = useBuildStore()
const uiStore = useUiStore()

const navItems = computed(() => [
  { path: '/', title: '搭建控制', icon: '🏠' },
  {
    path: uiStore.workMode === 'normal' ? '/juming' : '/incentive-link',
    title: '链接分配',
    icon: '📋',
  },
  {
    path: uiStore.workMode === 'normal' ? '/promo-chain' : '/incentive-chain',
    title: '推广链生成',
    icon: '🔗',
  },
  {
    path: uiStore.workMode === 'normal' ? '/promo-split' : '/incentive-split',
    title: '推广链分割',
    icon: '✂️',
  },
  {
    path: uiStore.workMode === 'normal' ? '/material-push' : '/incentive-push',
    title: '素材推送',
    icon: '🔍',
  },
  { path: '/crawl-material', title: '素材爬取', icon: '🕷️' },
  { path: '/rta-tool', title: 'RTA 工具', icon: '📡' },
  { path: '/history', title: '素材历史', icon: '📚' },
])
</script>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  background: var(--c-bg);
}

.sidebar {
  width: 220px;
  min-width: 220px;
  background: var(--c-card);
  border-right: 1px solid var(--c-border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  align-items: center;
  padding: 20px 18px 16px;
  border-bottom: 1px solid var(--c-border-s);
}

.logo {
  font-size: 26px;
  margin-right: 10px;
}

.title-group {
  display: flex;
  flex-direction: column;
}

.app-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--c-text);
  margin: 0;
  font-family: var(--f-ui);
}

.app-subtitle {
  font-size: 10px;
  color: var(--c-dim);
  margin: 2px 0 0;
  font-family: var(--f-ui);
}

/* 模式切换 Tab */
.mode-switcher {
  display: flex;
  margin: 12px 10px 4px;
  background: var(--c-bg);
  border-radius: 8px;
  padding: 3px;
  gap: 2px;
}

.mode-switcher button {
  flex: 1;
  padding: 6px 0;
  border: none;
  border-radius: 6px;
  font-size: 12.5px;
  font-weight: 600;
  font-family: var(--f-ui);
  color: var(--c-dim);
  background: transparent;
  cursor: pointer;
  transition: all 0.18s ease;
}

.mode-switcher button:hover {
  color: var(--c-text);
  background: var(--c-hover);
}

.mode-switcher button.active {
  background: var(--c-primary);
  color: #ffffff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
}

.nav-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 10px;
}

.nav-item {
  display: flex;
  align-items: center;
  padding: 9px 14px;
  margin-bottom: 2px;
  border-radius: var(--r-sm);
  color: var(--c-text-2);
  text-decoration: none;
  font-size: 13px;
  font-family: var(--f-ui);
  transition: all var(--transition-fast);
  cursor: pointer;
}

.nav-item:hover {
  background: var(--c-hover);
  color: var(--c-text);
}

.nav-item.active {
  background: var(--c-primary);
  color: #ffffff;
}

.nav-icon {
  margin-right: 10px;
  font-size: 15px;
}

.nav-label {
  font-weight: 500;
}

.nav-divider {
  height: 1px;
  background: var(--c-border-s);
  margin: 8px 14px;
}

.main-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

@media (max-width: 800px) {
  .sidebar {
    display: none;
  }
  .app-shell {
    flex-direction: column;
  }
}
</style>
