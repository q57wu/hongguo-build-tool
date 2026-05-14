<template>
  <div class="dashboard">
    <!-- 断点续传提示 -->
    <div v-if="pendingBuild" class="resume-panel">
      <div class="resume-info">
        ⚠️ 发现未完成的搭建任务
        <br><small>{{ pendingBuild.profile }} · {{ pendingBuild.completed_count }}/{{ pendingBuild.total_count }} 完成</small>
        <div class="resume-progress-bar">
          <div class="resume-progress-fill" :style="{ width: (pendingBuild.total_count ? (pendingBuild.completed_count / pendingBuild.total_count * 100) : 0) + '%' }"></div>
        </div>
      </div>
      <div class="resume-actions">
        <button class="btn-resume" @click="resumeBuild">继续搭建</button>
        <button class="btn-dismiss" @click="dismissBuild" title="清除记录，从头开始。已完成的账户不受影响。">重新搭建</button>
      </div>
    </div>

    <!-- 搭建前置检查 -->
    <div class="checklist-panel" :class="{ 'checklist-collapsed': !checklistExpanded && allChecksPass }">
      <div class="checklist-header" @click="checklistExpanded = !checklistExpanded">
        <div class="checklist-title-row">
          <h3>搭建准备检查</h3>
          <span v-if="allChecksPass" class="checklist-badge pass">全部通过</span>
          <span v-else class="checklist-badge fail">{{ failedCheckCount }} 项未通过</span>
        </div>
        <span class="checklist-toggle">{{ checklistExpanded ? '收起' : '展开' }}</span>
      </div>
      <transition name="collapse">
      <div v-show="checklistExpanded" class="checklist-items">
        <div class="check-item" :class="{ pass: checks.browser, fail: !checks.browser }">
          <span class="check-icon">{{ checks.browser ? '✅' : '❌' }}</span>
          <span class="check-label">Chrome 浏览器连接</span>
          <button v-if="!checks.browser" class="btn-fix" @click="launchBrowser" :disabled="launching">
            {{ launching ? '启动中...' : '自动启动' }}
          </button>
          <router-link v-if="!checks.browser" to="/settings" class="check-fix-link">去配置 →</router-link>
          <div v-if="browserError" class="check-error">{{ browserError }}</div>
        </div>
        <div class="check-item" :class="{ pass: checks.profile, fail: !checks.profile }">
          <span class="check-icon">{{ checks.profile ? '✅' : '❌' }}</span>
          <span class="check-label">搭建配置已选择</span>
          <span v-if="checks.profile" class="check-detail">{{ selectedProfile }}</span>
          <router-link v-if="!checks.profile" to="/settings" class="check-fix-link">去配置 →</router-link>
        </div>
        <div class="check-item" :class="{ pass: checks.groups, fail: !checks.groups }">
          <span class="check-icon">{{ checks.groups ? '✅' : '❌' }}</span>
          <span class="check-label">账户组数据已配置</span>
          <span v-if="checks.groups" class="check-detail">{{ groupCount }} 组</span>
          <router-link v-if="!checks.groups" to="/settings" class="check-fix-link">去配置 →</router-link>
        </div>
        <div class="check-item" :class="{ pass: checks.monitorLinks, fail: !checks.monitorLinks }">
          <span class="check-icon">{{ checks.monitorLinks ? '✅' : '❌' }}</span>
          <span class="check-label">监测链接已配置</span>
          <router-link v-if="!checks.monitorLinks" :to="uiStore.workMode === 'incentive' ? '/incentive-link' : '/juming'" class="check-fix-link">去配置 →</router-link>
        </div>
        <div class="check-item" :class="{ pass: checks.materialIds, fail: !checks.materialIds }">
          <span class="check-icon">{{ checks.materialIds ? '✅' : '❌' }}</span>
          <span class="check-label">素材账户 ID 已配置</span>
          <router-link v-if="!checks.materialIds" to="/settings" class="check-fix-link">去配置 →</router-link>
        </div>
        <div class="check-item" :class="{ pass: checks.audienceKeyword, fail: !checks.audienceKeyword }">
          <span class="check-icon">{{ checks.audienceKeyword ? '✅' : '❌' }}</span>
          <span class="check-label">受众关键词已填写</span>
          <router-link v-if="!checks.audienceKeyword" to="/settings" class="check-fix-link">去配置 →</router-link>
        </div>
        <div v-if="poolCheckInfo.checked" class="check-item" :class="poolCheckInfo.matched > 0 ? 'pass' : 'warn'">
          <span class="check-icon">{{ poolCheckInfo.matched > 0 ? 'ℹ️' : '⚠️' }}</span>
          <span class="check-label">账户池匹配</span>
          <span class="check-detail">池中 {{ poolCheckInfo.matched }} 个可用账户</span>
          <router-link to="/account-pool" class="check-fix-link">查看账户池 →</router-link>
        </div>
      </div>
      </transition>
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
          <label class="config-label">平台</label>
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
          <label class="config-label">留存类型</label>
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
          <label class="config-label">执行模式</label>
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
          <label class="config-label">并发数</label>
          <div class="seg-group">
            <button
              v-for="n in [2, 3, 5, 8, 10]"
              :key="n"
              class="seg-btn"
              :class="{ active: maxWorkers === n, accent: maxWorkers === n, disabled: buildStore.isRunning }"
              :disabled="buildStore.isRunning"
              @click="maxWorkers = n"
            >{{ n }}</button>
          </div>
        </div>

      </div>

      <!-- 操作按钮独立行 -->
      <div class="action-row">
        <div class="action-hint">
          <span v-if="!allChecksPass" class="hint-warn">⚠ {{ failedCheckCount }} 项检查未通过</span>
          <span v-else class="hint-ready">✅ 环境就绪 · {{ currentProfileLabel }}</span>
        </div>
        <div class="action-btns">
          <button
            class="btn btn-ghost btn-stop"
            :disabled="!buildStore.isRunning || buildStore.isStopping"
            @click="handleStop"
          >{{ buildStore.isStopping ? '停止中...' : '停止' }}</button>
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
              class="btn btn-ghost btn-sm btn-status-action"
              @click="buildStore.reset()"
              aria-label="清除状态">
        清除
      </button>
      <router-link v-if="buildStore.status === 'completed'"
                   to="/records"
                   class="btn btn-ghost btn-sm btn-status-action">
        查看记录 →
      </router-link>
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
  getAccountPool,
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
  if (buildStore.status === 'stopping') {
    return stoppingSeconds.value > 0 ? `正在停止... (${stoppingSeconds.value}s)` : '正在停止'
  }
  const map = {
    running: '正在搭建',
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
    startStoppingTimer()
    return
  }
  const confirmed = await confirmDialog.value.show()
  if (!confirmed) return
  await buildStore.stopBuild()
  startStoppingTimer()
}

function startStoppingTimer() {
  stoppingSeconds.value = 0
  if (stoppingTimer) clearInterval(stoppingTimer)
  stoppingTimer = setInterval(() => {
    stoppingSeconds.value++
  }, 1000)
}

// ── 前置检查 ──────────────────────────────────────────────
const checks = ref({
  browser: false,
  profile: false,
  groups: false,
  monitorLinks: false,
  materialIds: false,
  audienceKeyword: false,
})
const poolCheckInfo = ref({ matched: 0, total: 0, checked: false })
const launching = ref(false)
const browserError = ref('')
// 停止计时器
const stoppingSeconds = ref(0)
let stoppingTimer = null
const selectedProfile = ref('')
const groupCount = ref(0)

const allChecksPass = computed(() =>
  checks.value.browser && checks.value.profile && checks.value.groups
    && checks.value.monitorLinks && checks.value.materialIds && checks.value.audienceKeyword
)

const checklistExpanded = ref(true)
const failedCheckCount = computed(() => {
  const c = checks.value
  return [c.browser, c.profile, c.groups, c.monitorLinks, c.materialIds, c.audienceKeyword]
    .filter(v => !v).length
})

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
    checks.value.profile = profiles.length > 0 && !!config.profiles?.[currentProfileKey.value]
    const activeProfile = config.profiles?.[currentProfileKey.value]
    const groups = activeProfile?.groups || []
    checks.value.groups = groups.length > 0
    groupCount.value = groups.length

    // 检查监测链接
    const isIncentive = currentProfileKey.value?.includes('激励')
    if (isIncentive) {
      // 激励模式：检查组级链接
      checks.value.monitorLinks = groups.length > 0 && groups.every(g => g.click_url?.trim() && g.show_url?.trim())
    } else {
      // 非激励：检查每部剧的链接
      const allDramas = groups.flatMap(g => g.dramas || [])
      checks.value.monitorLinks = allDramas.length > 0 && allDramas.every(d => d.click?.trim() && d.show?.trim())
    }

    // 检查素材账户ID（material_account_id 填了即可，自定义素材ID是可选的）
    if (isIncentive) {
      checks.value.materialIds = true  // 激励模式不需要素材ID
    } else {
      checks.value.materialIds = !!activeProfile?.material_account_id?.trim()
    }

    // 检查受众关键词
    checks.value.audienceKeyword = !!activeProfile?.audience_keyword?.trim()
  } catch {
    checks.value.profile = false
    checks.value.groups = false
    checks.value.monitorLinks = false
    checks.value.materialIds = false
    checks.value.audienceKeyword = false
  }
  // 检查账户池匹配情况（非阻塞）
  try {
    const pk = currentProfileKey.value
    const isIncentive = pk.includes('激励')
    const plat = pk.startsWith('IOS') ? 'IOS' : '安卓'
    const strat = pk.includes('七留') ? '七留' : '每留'
    const poolRes = await getAccountPool('media', '', '', plat, strat, '')
    const poolCount = poolRes?.accounts?.length || 0
    // Count accounts currently in config groups
    const cfg2 = await getConfig()
    const prof2 = cfg2?.profiles?.[pk]
    const configIds = new Set((prof2?.groups || []).flatMap(g => g.account_ids || []))
    poolCheckInfo.value = { matched: poolCount, total: configIds.size, checked: true }
  } catch {
    poolCheckInfo.value = { matched: 0, total: 0, checked: false }
  }
  // 全部通过时自动折叠，有失败项时自动展开
  if (allChecksPass.value) {
    checklistExpanded.value = false
  } else {
    checklistExpanded.value = true
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
  if (stoppingTimer) {
    clearInterval(stoppingTimer)
    stoppingTimer = null
  }
})

// 监听 URL query 变化，支持从每日任务页多次跳转时更新 profile
watch(() => route.query.profile, (newProfile) => {
  if (newProfile) {
    applyProfileFromQuery()
  }
})

watch(currentProfileKey, () => {
  runChecks()
})

watch(() => buildStore.status, (newStatus) => {
  if (newStatus !== 'stopping' && stoppingTimer) {
    clearInterval(stoppingTimer)
    stoppingTimer = null
    stoppingSeconds.value = 0
  }
})

async function launchBrowser() {
  launching.value = true
  browserError.value = ''
  try {
    const result = await launchBrowserApi()
    if (result.ok) {
      checks.value.browser = true
      browserError.value = ''
    } else {
      browserError.value = result.message || '启动失败，请检查 Chrome 是否已安装'
    }
  } catch (e) {
    browserError.value = '启动失败：请先关闭已打开的 Chrome 窗口，或在设置页配置 Chrome 路径'
  }
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
  background: rgba(255, 253, 248, 0.94);
  border: 1px solid var(--c-border-s);
  box-shadow: var(--shadow-sm);
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.config-card:hover {
  border-color: rgba(216, 137, 0, 0.2);
  box-shadow: var(--shadow-md), 0 0 0 1px rgba(216, 137, 0, 0.06);
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
}

.config-col {
  display: flex;
  flex-direction: column;
}

/* 操作按钮独立行 */
.action-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--c-border-s);
}

.action-hint {
  font-size: 12px;
  font-weight: 500;
}

.hint-warn {
  color: var(--c-accent, #d88900);
}

.hint-ready {
  color: var(--c-green, #10b981);
}

.action-btns {
  display: flex;
  gap: 8px;
}

.config-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--c-dim);
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
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
  border: 1px solid transparent;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  font-family: var(--f-ui);
  color: var(--c-text-2);
  background: transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.seg-btn:hover:not(.active) {
  background: var(--c-hover);
  color: var(--c-text);
}

.seg-btn.active {
  background: var(--c-card);
  color: var(--c-text);
  box-shadow: 0 1px 6px rgba(72, 58, 36, 0.1);
}

.seg-btn.active.accent {
  background: rgba(216, 137, 0, 0.12);
  color: var(--c-accent, #d88900);
  border: 1px solid rgba(216, 137, 0, 0.22);
}

.seg-btn.disabled,
.seg-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
  pointer-events: none;
}

/* 按钮 — 停止 (红色辉光) */
.btn-stop {
  height: 44px;
  padding: 0 20px;
  background: linear-gradient(135deg, #ff4757, #d63447);
  color: #fff;
  border: none;
  border-radius: var(--r-sm);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 2px 10px rgba(255, 71, 87, 0.3);
}
.btn-stop:hover:not(:disabled) {
  box-shadow: 0 4px 20px rgba(255, 71, 87, 0.45);
  transform: translateY(-1px);
}
.btn-stop:disabled {
  opacity: 0.35;
  cursor: not-allowed;
  background: linear-gradient(135deg, #ff4757, #d63447);
  transform: none;
  box-shadow: none;
}

/* 按钮 — 开始 (琥珀辉光) */
.btn-start {
  height: 44px;
  padding: 0 32px;
  min-width: 160px;
  background: linear-gradient(135deg, var(--c-accent, #d88900), #cc8c00);
  color: #fff;
  border: none;
  border-radius: var(--r-sm);
  font-size: 14px;
  font-weight: 700;
  font-family: var(--f-ui);
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  gap: 6px;
  box-shadow: 0 2px 12px rgba(216, 137, 0, 0.35);
}

.btn-start:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 24px rgba(216, 137, 0, 0.5);
  background: linear-gradient(135deg, #ffb820, #d99500);
}

.btn-start:active:not(:disabled) {
  transform: translateY(0) scale(0.98);
  box-shadow: 0 1px 6px rgba(216, 137, 0, 0.3);
}

.btn-start:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* 运行中切换为蓝色 */
.btn-start.running {
  background: linear-gradient(135deg, #2d7aed, #1a5ec4);
  box-shadow: 0 2px 12px rgba(45, 122, 237, 0.4);
}

/* 旋转动画 */
.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
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

/* 运行中 — 琥珀脉冲 */
.status-running {
  background: rgba(216, 137, 0, 0.08);
  color: var(--c-accent, #d88900);
}
.status-running .status-dot {
  background: var(--c-accent, #d88900);
  animation: pulse-dot 2s ease-in-out infinite;
  box-shadow: 0 0 0 0 rgba(216, 137, 0, 0.5);
}

.status-warning {
  background: var(--c-status-warn-bg);
  color: var(--c-status-warn-text);
}
.status-warning .status-dot { background: var(--c-orange); }

.status-success {
  background: var(--c-status-info-bg);
  color: var(--c-status-info-text);
}
.status-success .status-dot { background: var(--c-blue); }

.status-error {
  background: var(--c-status-error-bg);
  color: var(--c-status-error-text);
  border-left: 3px solid var(--c-red);
}
.status-error .status-dot { background: var(--c-red); }

.status-detail {
  color: inherit;
  opacity: 0.7;
}

.btn-status-action {
  margin-left: auto;
  font-size: var(--fs-xs, 11px);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* 前置检查面板 */
.checklist-panel {
  background: rgba(237, 244, 247, 0.82);
  border: 1px solid var(--c-border);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.checklist-panel h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text);
  margin: 0 0 12px 0;
}

.checklist-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  user-select: none;
}

.checklist-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.checklist-header h3 {
  margin: 0;
}

.checklist-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
}

.checklist-badge.pass {
  background: var(--c-status-success-bg);
  color: var(--c-status-success-text);
}

.checklist-badge.fail {
  background: var(--c-status-error-bg);
  color: var(--c-status-error-text);
}

.checklist-toggle {
  font-size: 12px;
  color: var(--c-accent, #d88900);
  font-weight: 500;
}

.checklist-collapsed {
  padding: 12px 16px;
}

.checklist-collapsed .checklist-items {
  display: none;
}

.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.25s ease;
  max-height: 500px;
  overflow: hidden;
}

.collapse-enter-from,
.collapse-leave-to {
  max-height: 0;
  opacity: 0;
}

.checklist-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 检查项 */
.check-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  background: rgba(255, 253, 248, 0.86);
}

.check-item.pass {
  border-left: 3px solid var(--c-green);
}

.check-item.fail {
  border-left: 3px solid var(--c-red);
}

.check-icon { font-size: 14px; }
.check-label { flex: 1; font-size: 13px; color: var(--c-text); }
.check-detail { font-size: 12px; color: var(--c-text-2); }

.btn-fix {
  padding: 4px 12px;
  font-size: 12px;
  background: #2d7aed;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-fix:hover {
  background: #3d8afd;
}

.btn-fix:focus, .btn-fix:focus-visible {
  outline: 2px solid #2d7aed;
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
  background: rgba(216, 137, 0, 0.06);
  border: 1px solid rgba(216, 137, 0, 0.2);
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.resume-info {
  font-size: 13px;
  color: var(--c-text);
  line-height: 1.6;
}

.resume-info small {
  font-size: 12px;
  color: var(--c-text-2);
  opacity: 0.8;
}

/* 断点续传进度条 — 琥珀色 + 流光 */
.resume-progress-bar {
  height: 3px;
  background: rgba(216, 137, 0, 0.15);
  border-radius: 2px;
  margin-top: 6px;
  width: 200px;
}
.resume-progress-fill {
  position: relative;
  overflow: hidden;
  height: 100%;
  background: var(--c-accent, #d88900);
  border-radius: 2px;
  transition: width 0.3s ease;
}
.resume-progress-fill::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent 30%, rgba(255, 255, 255, 0.25) 50%, transparent 70%);
  background-size: 200% 100%;
  animation: shimmer 2s infinite;
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
  background: var(--c-accent, #d88900);
  color: #fffaf0;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-resume:hover {
  background: #ffb820;
}

.btn-dismiss {
  padding: 6px 14px;
  font-size: 12px;
  background: transparent;
  color: var(--c-text-2);
  border: 1px solid rgba(216, 137, 0, 0.2);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-dismiss:hover {
  background: rgba(216, 137, 0, 0.08);
  color: var(--c-text);
}

.check-fix-link {
  font-size: 12px;
  color: var(--c-accent, #d88900);
  text-decoration: none;
  font-weight: 500;
  white-space: nowrap;
}

.check-fix-link:hover {
  text-decoration: underline;
  color: #ffb820;
}

.check-error {
  width: 100%;
  margin-top: 6px;
  font-size: 12px;
  color: var(--c-red);
  padding: 6px 10px;
  background: var(--c-status-error-bg);
  border-radius: 4px;
  line-height: 1.5;
}

.check-item {
  flex-wrap: wrap;
}

/* 警告状态检查项（非阻塞） */
.check-item.warn {
  border-left: 3px solid var(--c-orange, #f59e0b);
}
</style>
