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
      <div class="mode-badge" :class="uiStore.workMode">
        {{ uiStore.workMode === 'incentive' ? '激励模式' : '普通模式' }}
      </div>

      <nav class="nav-list">
        <!-- 核心工作流 -->
        <router-link to="/daily-task" class="nav-item" :class="{ active: $route.path === '/daily-task' }">
          <span class="nav-icon">📋</span>
          <span class="nav-label">每日任务</span>
        </router-link>
        <router-link to="/" class="nav-item" :class="{ active: $route.path === '/' }">
          <span class="nav-icon">🚀</span>
          <span class="nav-label">搭建控制</span>
        </router-link>
        <router-link to="/records" class="nav-item" :class="{ active: $route.path === '/records' }">
          <span class="nav-icon">📊</span>
          <span class="nav-label">搭建记录</span>
        </router-link>

        <div class="nav-divider"></div>

        <!-- 分组导航 -->
        <div v-for="group in navGroups" :key="group.title" class="nav-group">
          <div
            class="nav-group-title"
            role="button"
            tabindex="0"
            @click="toggleGroup(group.title)"
            @keydown.enter.prevent="toggleGroup(group.title)"
            @keydown.space.prevent="toggleGroup(group.title)"
          >
            <span class="nav-group-label">{{ group.title }}</span>
            <span class="nav-group-arrow" :class="{ expanded: expandedGroups[group.title] }">›</span>
          </div>
          <transition name="collapse">
            <div v-show="expandedGroups[group.title]" class="nav-group-items">
              <router-link
                v-for="item in group.items"
                :key="item.path"
                :to="item.path"
                class="nav-item nav-item-sub"
                :class="{ active: $route.path === item.path }"
              >
                <span class="nav-icon">{{ item.icon }}</span>
                <span class="nav-label">{{ item.title }}</span>
              </router-link>
            </div>
          </transition>
        </div>

        <!-- 底部固定项 -->
        <div class="nav-divider"></div>
        <router-link to="/account-pool" class="nav-item" :class="{ active: $route.path === '/account-pool' }">
          <span class="nav-icon">🗂</span>
          <span class="nav-label">账户池</span>
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
    <ToastContainer />
  </div>
</template>

<script setup>
import { computed, reactive } from 'vue'
import { useBackendEvents } from './composables/useEvents'
import { useBuildStore } from './stores/build'
import { useUiStore } from './stores/ui'
import ToastContainer from './components/ToastContainer.vue'

useBackendEvents()
const buildStore = useBuildStore()
const uiStore = useUiStore()

// 分组展开状态（默认全部展开）
const expandedGroups = reactive({
  '链接管理': true,
  '推广工具': true,
  '素材管理': true,
})

function toggleGroup(title) {
  expandedGroups[title] = !expandedGroups[title]
}

const navGroups = computed(() => {
  const isIncentive = uiStore.workMode === 'incentive'
  return [
    {
      title: '链接管理',
      items: [
        {
          path: isIncentive ? '/incentive-link' : '/juming',
          title: isIncentive ? '激励链接分配' : '剧名链接分配',
          icon: isIncentive ? '⚡' : '📋',
        },
      ],
    },
    {
      title: '推广工具',
      items: [
        {
          path: isIncentive ? '/incentive-chain' : '/promo-chain',
          title: isIncentive ? '激励推广链生成' : '推广链生成',
          icon: '🔗',
        },
        {
          path: isIncentive ? '/incentive-split' : '/promo-split',
          title: isIncentive ? '激励链分割' : '推广链分割',
          icon: '✂️',
        },
      ],
    },
    {
      title: '素材管理',
      items: [
        {
          path: isIncentive ? '/incentive-push' : '/material-push',
          title: isIncentive ? '激励素材推送' : '素材推送',
          icon: '📤',
        },
        { path: '/crawl-material', title: '素材爬取', icon: '🕷️' },
        { path: '/history', title: '素材历史', icon: '📚' },
        { path: '/rta-tool', title: 'RTA 工具', icon: '📡' },
      ],
    },
  ]
})
</script>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  background:
    radial-gradient(circle at 18% 6%, rgba(255, 213, 136, 0.32), transparent 30%),
    radial-gradient(circle at 82% 10%, rgba(181, 219, 236, 0.45), transparent 28%),
    var(--c-bg);
}

.sidebar {
  width: 230px;
  min-width: 230px;
  background: linear-gradient(180deg, rgba(255, 253, 248, 0.96), rgba(247, 241, 230, 0.94));
  border-right: 1px solid rgba(165, 136, 91, 0.22);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

.sidebar::after {
  content: '';
  position: absolute;
  inset: 0;
  background:
    linear-gradient(90deg, rgba(255,255,255,0.55), transparent 42%),
    repeating-linear-gradient(0deg, transparent, transparent 7px, rgba(165, 136, 91, 0.035) 7px, rgba(165, 136, 91, 0.035) 8px);
  pointer-events: none;
  z-index: 1;
}

.sidebar-header {
  display: flex;
  align-items: center;
  padding: 22px 18px 18px;
  border-bottom: 1px solid rgba(165, 136, 91, 0.18);
  position: relative;
  z-index: 2;
}

.logo {
  font-size: 28px;
  margin-right: 12px;
  filter: drop-shadow(0 0 6px rgba(240, 165, 0, 0.4));
}

.title-group {
  display: flex;
  flex-direction: column;
}

.app-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--c-accent);
  margin: 0;
  font-family: var(--f-mono);
  letter-spacing: 0.5px;
  text-shadow: none;
}

.app-subtitle {
  font-size: 10px;
  color: var(--c-dim);
  margin: 3px 0 0;
  font-family: var(--f-mono);
  letter-spacing: 1px;
  text-transform: uppercase;
}

/* Mode Switcher: Toggle switch feel */
.mode-switcher {
  display: flex;
  margin: 14px 12px 6px;
  background: rgba(237, 244, 247, 0.72);
  border-radius: 6px;
  padding: 3px;
  gap: 2px;
  border: 1px solid rgba(165, 136, 91, 0.16);
  position: relative;
  z-index: 2;
}

.mode-switcher button {
  flex: 1;
  padding: 7px 0;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--c-dim);
  background: transparent;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: var(--f-mono);
}

.mode-switcher button:hover {
  color: var(--c-text);
  background: rgba(255, 253, 248, 0.72);
}

.mode-switcher button.active {
  background: var(--c-card);
  color: var(--c-accent);
  box-shadow: 0 1px 8px rgba(72, 58, 36, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.75);
}

/* Mode Badge: Indicator light */
.mode-badge {
  text-align: center;
  font-size: 10px;
  font-weight: 600;
  padding: 3px 0;
  margin: 0 12px 8px;
  border-radius: 3px;
  font-family: var(--f-mono);
  letter-spacing: 0.5px;
  position: relative;
  z-index: 2;
}
.mode-badge.normal {
  color: #2d7aed;
  background: rgba(45, 122, 237, 0.08);
  border: 1px solid rgba(45, 122, 237, 0.15);
}
.mode-badge.incentive {
  color: var(--c-accent);
  background: rgba(240, 165, 0, 0.08);
  border: 1px solid rgba(240, 165, 0, 0.15);
}

.nav-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 10px;
  position: relative;
  z-index: 2;
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
  transition: all 0.15s ease;
  cursor: pointer;
  position: relative;
}

.nav-item:hover {
  background: rgba(255, 253, 248, 0.72);
  color: var(--c-text);
}

.nav-item.active {
  background: rgba(216, 137, 0, 0.1);
  color: var(--c-accent);
  border: 1px solid rgba(216, 137, 0, 0.2);
  box-shadow: 0 8px 18px rgba(216, 137, 0, 0.08);
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 60%;
  background: var(--c-accent);
  border-radius: 0 2px 2px 0;
  box-shadow: 0 0 6px rgba(240, 165, 0, 0.5);
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
  background: linear-gradient(90deg, transparent, rgba(240, 165, 0, 0.1), transparent);
  margin: 10px 14px;
}

.nav-group {
  margin-bottom: 2px;
}

.nav-group-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 14px;
  font-size: 10px;
  font-weight: 700;
  color: rgba(136, 153, 180, 0.35);
  letter-spacing: 1.2px;
  text-transform: uppercase;
  cursor: pointer;
  user-select: none;
  border-radius: var(--r-sm);
  transition: color var(--transition-fast);
  font-family: var(--f-mono);
}

.nav-group-title:hover {
  color: rgba(136, 153, 180, 0.6);
}

.nav-group-label {
  flex: 1;
}

.nav-group-arrow {
  font-size: 12px;
  transition: transform 0.2s ease;
  color: rgba(136, 153, 180, 0.3);
}

.nav-group-arrow.expanded {
  transform: rotate(90deg);
}

.nav-group-items {
  overflow: hidden;
  position: relative;
  z-index: 2;
}

.nav-item-sub {
  padding-left: 22px;
  font-size: 12.5px;
}

.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.2s ease;
  max-height: 300px;
}

.collapse-enter-from,
.collapse-leave-to {
  max-height: 0;
  opacity: 0;
}

.main-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: transparent;
}

@media (max-width: 900px) {
  .sidebar { width: 56px; min-width: 56px; }
  .sidebar-header { padding: 16px 10px 12px; justify-content: center; }
  .title-group { display: none; }
  .logo { margin-right: 0; }
  .mode-switcher { display: none; }
  .mode-badge { display: none; }
  .nav-label { display: none; }
  .nav-item { justify-content: center; padding: 10px 0; }
  .nav-icon { margin-right: 0; font-size: 18px; }
  .nav-divider { margin: 8px 6px; }
  .nav-group-title { display: none; }
}
</style>
