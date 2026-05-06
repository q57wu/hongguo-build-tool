<template>
  <div class="dashboard">
    <!-- 断点续传提示 -->
    <div v-if="pendingBuild" class="resume-panel">
      <div class="resume-info">
        ⚠️ 发现未完成的搭建任务
        <br><small>{{ pendingBuild.profile }} · {{ pendingBuild.completed_count }}/{{ pendingBuild.total_count }} 完成</small>
      </div>
      <div class="resume-actions">
        <button class="btn-resume" @click="resumeBuild">继续搭建</button>
        <button class="btn-dismiss" @click="dismissBuild">忽略</button>
      </div>
    </div>

    <!-- 搭建前置检查 -->
    <div class="checklist-panel">
      <h3>搭建准备检查</h3>
      <div class="checklist-items">
        <div class="check-item" :class="{ pass: checks.browser, fail: !checks.browser }">
          <span class="check-icon">{{ checks.browser ? '✅' : '❌' }}</span>
          <span class="check-label">Chrome 浏览器连接</span>
          <button v-if="!checks.browser" class="btn-fix" @click="launchBrowser" :disabled="launching">
            {{ launching ? '启动中...' : '自动启动' }}
          </button>
        </div>
        <div class="check-item" :class="{ pass: checks.profile, fail: !checks.profile }">
          <span class="check-icon">{{ checks.profile ? '✅' : '❌' }}</span>
          <span class="check-label">搭建配置已选择</span>
          <span v-if="checks.profile" class="check-detail">{{ selectedProfile }}</span>
        </div>
        <div class="check-item" :class="{ pass: checks.groups, fail: !checks.groups }">
          <span class="check-icon">{{ checks.groups ? '✅' : '❌' }}</span>
          <span class="check-label">账户组数据已配置</span>
          <span v-if="checks.groups" class="check-detail">{{ groupCount }} 组</span>
        </div>
      </div>
      <p v-if="!allChecksPass" class="checklist-warning">⚠️ 请先完成以上检查项再开始搭建</p>
    </div>

    <!-- 配置卡片 -->
    <div class="card config-card">
      <div class="card-head">
        <h3 class="card-title">构建配置</h3>
        <span class="config-hint">{{ currentProfileLabel }}</span>
      </div>
      <div class="config-row">
        <!-- 平台选择 -->
        <div class="config-col">
          <label class="config-label">PLATFORM</label>
          <div class="seg-group">
            <button
              v-for="p in platforms"
              :key="p"
              class="seg-btn"
              :class="{ active: platform === p, accent: platform === p, disabled: isPlatformDisabled(p) || buildStore.isRunning }"
              :disabled="isPlatformDisabled(p) || buildStore.isRunning"
              :aria-pressed="platform === p"
              @click="platform = p"
            >{{ p }}</button>
          </div>
        </div>

        <!-- 留存选择 -->
        <div class="config-col">
          <label class="config-label">RETENTION</label>
          <div class="seg-group">
            <button
              v-for="r in retentions"
              :key="r"
              class="seg-btn"
              :class="{ active: retention === r, accent: retention === r, disabled: buildStore.isRunning }"
              :disabled="buildStore.isRunning"
              :aria-pressed="retention === r"
              @click="retention = r"
            >{{ r }}</button>
          </div>
        </div>

        <!-- 并行配置 -->
        <div class="config-col">
          <label class="config-label">MODE</label>
          <div class="seg-group">
            <button
              class="seg-btn"
              :class="{ active: !parallelMode, accent: !parallelMode, disabled: buildStore.isRunning }"
              :disabled="buildStore.isRunning"
              @click="parallelMode = false"
            >串行</button>
            <button
              class="seg-btn"
              :class="{ active: parallelMode, accent: parallelMode, disabled: buildStore.isRunning }"
              :disabled="buildStore.isRunning"
              @click="parallelMode = true"
            >并行</button>
          </div>
        </div>

        <div v-if="parallelMode" class="config-col">
          <label class="config-label">WORKERS</label>
          <div class="seg-group">
            <button
              v-for="n in [2, 3, 4, 5]"
              :key="n"
              class="seg-btn"
              :class="{ active: maxWorkers === n, accent: maxWorkers === n, disabled: buildStore.isRunning }"
              :disabled="buildStore.isRunning"
              @click="maxWorkers = n"
            >{{ n }}</button>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="config-col config-col-actions">
          <button
            class="btn btn-ghost btn-stop"
            :disabled="!buildStore.isRunning"
            @click="handleStop"
          >停止</button>
          <button
            class="btn btn-start"
            :class="{ running: buildStore.isRunning }"
            :disabled="!buildStore.canStart || !allChecksPass"
            @click="handleStart"
          >
            <span v-if="buildStore.isRunning" class="spinner"></span>
            {{ startBtnText }}
          </button>
        </div>
      </div>
    </div>

    <!-- 状态栏 -->
    <div v-if="buildStore.status !== 'idle'" class="status-bar" :class="statusClass">
      <span class="status-dot"></span>
      <span class="status-text">{{ statusText }}</span>
      <span v-if="buildStore.error && buildStore.status === 'error'" class="status-detail">
        — {{ buildStore.error }}
      </span>
      <span v-else-if="buildStore.progress.message" class="status-detail">
        — {{ buildStore.progress.message }}
      </span>
      <button v-if="buildStore.status === 'error' || buildStore.status === 'completed'"
              class="btn btn-ghost btn-sm"
              @click="buildStore.reset()"
              aria-label="清除状态"
              style="margin-left: auto; font-size: 11px;">
        清除
      </button>
    </div>

    <!-- 日志面板 -->
    <LogPanel />

    <!-- 停止确认弹窗 -->
    <ConfirmDialog
      ref="confirmDialog"
      title="确认停止"
      message="确定要停止当前搭建任务吗？已完成的账户不受影响。"
      confirm-text="停止"
      :is-danger="true"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useBuildStore } from '../stores/build'
import { useLogStore } from '../stores/log'
import { useUiStore } from '../stores/ui'
import LogPanel from '../components/LogPanel.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import {
  checkBrowser,
  launchBrowser as launchBrowserApi,
  getConfig,
  getPendingBuild,
  resumeBuild as resumeBuildApi,
  dismissPendingBuild,
} from '@/services/api'

const confirmDialog = ref(null)
const route = useRoute()

const buildStore = useBuildStore()
const logStore = useLogStore()
const uiStore = useUiStore()

// 配置选项
const platforms = ['安卓', 'IOS']
const retentions = ['每留', '七留']

// mode 跟随顶部 Tab
const mode = computed(() => uiStore.workMode === 'incentive' ? '激励' : '普通')

// 从 localStorage 恢复上次选择
const STORAGE_KEY = 'dashboard_config'
function loadSavedConfig() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const obj = JSON.parse(raw)
    return obj && typeof obj === 'object' ? obj : {}
  } catch (e) {
    return {}
  }
}
const saved = loadSavedConfig()

const platform = ref(platforms.includes(saved.platform) ? saved.platform : '安卓')
const retention = ref(retentions.includes(saved.retention) ? saved.retention : '每留')
const parallelMode = ref(saved.parallel !== undefined ? saved.parallel : true)
const maxWorkers = ref(saved.maxWorkers || 3)

// 从每日任务页跳转过来时，自动选中 profile
function applyProfileFromQuery() {
  const profileKey = route.query.profile
  if (!profileKey) return
  // 解析 profile_key，如 "安卓-每留" / "IOS-激励每留"
  const isIncentive = profileKey.includes('激励')
  if (isIncentive) {
    uiStore.setWorkMode('incentive')
  } else {
    uiStore.setWorkMode('normal')
  }
  // 提取平台
  if (profileKey.startsWith('IOS')) {
    platform.value = 'IOS'
  } else if (profileKey.startsWith('安卓')) {
    platform.value = '安卓'
  }
  // 提取留存
  if (profileKey.includes('七留')) {
    retention.value = '七留'
  } else if (profileKey.includes('每留')) {
    retention.value = '每留'
  }
}

// 有效的 profile 组合
const validProfiles = new Set([
  '安卓-每留', '安卓-七留', 'IOS-每留', 'IOS-七留',
  '安卓-激励每留', '安卓-激励七留',
])

// 判断某个平台在当前模式下是否可用
function isPlatformDisabled(p) {
  if (mode.value === '激励') {
    return !validProfiles.has(`${p}-激励${retention.value}`)
  }
  return !validProfiles.has(`${p}-${retention.value}`)
}

// 启动时校正：如果恢复的组合不合法（如 IOS+激励），回退到安卓
if (isPlatformDisabled(platform.value)) {
  platform.value = '安卓'
}

// watch mode 变化（跟随顶部Tab），如果切到激励且当前平台不可用，自动切到安卓
watch(mode, (newMode) => {
  if (newMode === '激励' && isPlatformDisabled(platform.value)) {
    platform.value = '安卓'
  }
})

// 持久化选择
watch([platform, retention, parallelMode, maxWorkers], ([p, r, par, mw]) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      platform: p, retention: r, parallel: par, maxWorkers: mw,
    }))
  } catch (e) {
    // ignore
  }
})

// 当前 profile key
const currentProfileKey = computed(() => {
  if (mode.value === '激励') {
    return `${platform.value}-激励${retention.value}`
  }
  return `${platform.value}-${retention.value}`
})

const currentProfileLabel = computed(() => {
  return `${platform.value} · ${retention.value}${mode.value === '激励' ? ' · 激励' : ''}`
})

// 按钮文字
const startBtnText = computed(() => {
  if (buildStore.isRunning) return '运行中...'
  if (buildStore.isStopping) return '停止中...'
  if (parallelMode.value) return `▶  并行搭建 ×${maxWorkers.value}`
  return '▶  开始搭建'
})

// 状态样式
const statusClass = computed(() => {
  const map = {
    running: 'status-running',
    stopping: 'status-warning',
    completed: 'status-success',
    error: 'status-error',
  }
  return map[buildStore.status] || ''
})

const statusText = computed(() => {
  const map = {
    running: '正在搭建',
    stopping: '正在停止',
    completed: '搭建完成',
    error: '搭建出错',
  }
  return map[buildStore.status] || ''
})

// 操作
async function handleStart() {
  logStore.clear()
  // 记录本次搭建的剧名清单（供推广链分割页过滤使用）
  try {
    const config = await getConfig()
    const profile = config.profiles?.[currentProfileKey.value]
    const names = (profile?.groups || []).flatMap(g => (g.dramas || []).map(d => d.name))
    buildStore.setLastDramaNames(names)
  } catch (_) {}
  const res = await buildStore.startBuild(currentProfileKey.value, {
    parallel: parallelMode.value,
    maxWorkers: maxWorkers.value,
  })
  if (!res.ok) {
    logStore.append({ message: `⚠️ ${res.error}`, level: 'error' })
  }
}

async function handleStop() {
  if (!confirmDialog.value?.show) {
    // 对话框未挂载时直接停止（兜底）
    await buildStore.stopBuild()
    return
  }
  const confirmed = await confirmDialog.value.show()
  if (!confirmed) return
  await buildStore.stopBuild()
}

// ── 前置检查 ──────────────────────────────────────────────
const checks = ref({
  browser: false,
  profile: false,
  groups: false,
})
const launching = ref(false)
const selectedProfile = ref('')
const groupCount = ref(0)

const allChecksPass = computed(() =>
  checks.value.browser && checks.value.profile && checks.value.groups
)

async function runChecks() {
  // 检查浏览器连接
  try {
    const result = await checkBrowser()
    checks.value.browser = result.connected
  } catch {
    checks.value.browser = false
  }

  // 检查配置和账户组
  try {
    const config = await getConfig()
    const profiles = Object.keys(config.profiles || {})
    checks.value.profile = profiles.length > 0
    if (profiles.length > 0) {
      selectedProfile.value = profiles[0]
    }
    const firstProfile = config.profiles?.[profiles[0]]
    const groups = firstProfile?.groups || []
    checks.value.groups = groups.length > 0
    groupCount.value = groups.length
  } catch {
    checks.value.profile = false
    checks.value.groups = false
  }
}

// 定期重新检查：每 30s 自动刷新一次前置检查状态
let checksTimer = null

onMounted(() => {
  applyProfileFromQuery()
  runChecks()
  checkPendingBuild()
  checksTimer = setInterval(runChecks, 30000)
})

onUnmounted(() => {
  if (checksTimer) {
    clearInterval(checksTimer)
    checksTimer = null
  }
})

async function launchBrowser() {
  launching.value = true
  try {
    const result = await launchBrowserApi()
    if (result.ok) {
      checks.value.browser = true
    }
  } catch {}
  launching.value = false
}

// ── 断点续传 ──────────────────────────────────────────────
const pendingBuild = ref(null)

async function checkPendingBuild() {
  try {
    const result = await getPendingBuild()
    if (result.has_pending) {
      pendingBuild.value = result
    }
  } catch {}
}

async function resumeBuild() {
  try {
    await resumeBuildApi()
  } catch {}
  pendingBuild.value = null
}

async function dismissBuild() {
  try {
    await dismissPendingBuild()
  } catch {}
  pendingBuild.value = null
}
</script>

<style scoped>
.dashboard {
  max-width: 90vw;
  max-width: min(90vw, 1400px);
  display: flex;
  flex-direction: column;
  height: calc(100vh - 48px);
}

/* 配置卡片 */
.config-card {
  flex-shrink: 0;
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.config-hint {
  font-size: 12px;
  color: var(--c-dim);
}

.config-row {
  display: flex;
  align-items: flex-end;
  gap: 24px;
  flex-wrap: wrap;
}

@media (max-width: 900px) {
  .config-row {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }
  .config-col-actions {
    margin-left: 0;
    flex-direction: row;
    justify-content: flex-end;
  }
}

.config-col {
  display: flex;
  flex-direction: column;
}

.config-col-actions {
  margin-left: auto;
  flex-direction: row;
  gap: 8px;
}

.config-label {
  font-size: 10px;
  font-weight: 700;
  color: var(--c-dim);
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}

/* 分段按钮组 */
.seg-group {
  display: flex;
  background: var(--c-surface);
  border-radius: var(--r-sm);
  padding: 3px;
  gap: 2px;
}

.seg-btn {
  padding: 7px 20px;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  font-family: var(--f-ui);
  color: var(--c-text);
  background: transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.seg-btn:hover:not(.active) {
  background: var(--c-hover);
}

.seg-btn.active {
  background: var(--c-card);
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.seg-btn.active.accent {
  background: var(--c-accent);
  color: #fff;
}

.seg-btn.disabled,
.seg-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
  pointer-events: none;
}

/* 按钮 */
.btn-stop {
  height: 36px;
  padding: 0 16px;
}

.btn-start {
  height: 36px;
  padding: 0 20px;
  background: var(--c-accent);
  color: #fff;
  border: none;
  border-radius: var(--r-sm);
  font-size: 13px;
  font-weight: 700;
  font-family: var(--f-ui);
  cursor: pointer;
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
  gap: 6px;
}

.btn-start:hover {
  background: var(--c-accent-h);
}

.btn-start:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-start.running {
  background: var(--c-orange);
}

/* 旋转动画 */
.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 状态栏 */
.status-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  padding: 10px 16px;
  margin-top: 12px;
  border-radius: var(--r-sm);
  font-size: 12px;
  font-weight: 500;
  gap: 8px;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.status-running {
  background: #ecfdf5;
  color: #065f46;
}
.status-running .status-dot {
  background: var(--c-green);
  animation: pulse 1.5s infinite;
}

.status-warning {
  background: #fffbeb;
  color: #92400e;
}
.status-warning .status-dot { background: var(--c-orange); }

.status-success {
  background: #ecfdf5;
  color: #065f46;
}
.status-success .status-dot { background: var(--c-green); }

.status-error {
  background: #fef2f2;
  color: #991b1b;
}
.status-error .status-dot { background: var(--c-red); }

.status-detail {
  color: inherit;
  opacity: 0.7;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* 前置检查面板 */
.checklist-panel {
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.checklist-panel h3 {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 12px 0;
}

.checklist-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.check-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  background: var(--c-card);
}

.check-item.pass {
  border-left: 3px solid #52c41a;
}

.check-item.fail {
  border-left: 3px solid #ff4d4f;
}

.check-icon { font-size: 14px; }
.check-label { flex: 1; font-size: 13px; }
.check-detail { font-size: 12px; color: var(--c-text-2); }

.btn-fix {
  padding: 4px 12px;
  font-size: 12px;
  background: var(--c-primary, #1677ff);
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-fix:focus, .btn-fix:focus-visible {
  outline: 2px solid var(--c-primary);
  outline-offset: 2px;
}

.btn-fix:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.checklist-warning {
  margin: 12px 0 0;
  font-size: 13px;
  color: var(--c-red, #ff4d4f);
}

/* 断点续传面板 */
.resume-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.resume-info {
  font-size: 13px;
  color: #92400e;
  line-height: 1.6;
}

.resume-info small {
  font-size: 12px;
  opacity: 0.8;
}

.resume-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.btn-resume {
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 600;
  background: #f59e0b;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-resume:hover {
  background: #d97706;
}

.btn-dismiss {
  padding: 6px 14px;
  font-size: 12px;
  background: transparent;
  color: #92400e;
  border: 1px solid #fbbf24;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-dismiss:hover {
  background: #fef3c7;
}
</style>
