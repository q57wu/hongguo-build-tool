<template>
  <div class="view-container">
    <div class="view-header">
      <h2>🔍 {{ isIncentive ? '激励素材推送' : '素材搜索推送' }}</h2>
      <p class="view-desc">输入剧名，自动搜索素材并批量推送到广告账户</p>
    </div>
    <div class="card">
      <div class="form-row">
        <div class="form-col" v-if="!isIncentive">
          <label class="field-label">推送方向</label>
          <div class="seg-group">
            <button class="seg-btn" :class="{ active: platform === '安卓' }" @click="platform = '安卓'">安卓</button>
            <button class="seg-btn" :class="{ active: platform === 'iOS' }" @click="platform = 'iOS'">iOS</button>
          </div>
        </div>
        <div class="form-col">
          <label class="field-label">广告账户 ID</label>
          <input v-model="accountId" class="text-input" placeholder="输入广告账户ID" />
        </div>
      </div>

      <label class="field-label">剧名（每行一个）</label>
      <textarea v-model="dramaNames" class="input-area" rows="8" placeholder="输入剧名，每行一个"></textarea>

      <div class="btn-row">
        <button class="btn btn-primary" :disabled="running" @click="startPush">🚀 开始推送</button>
        <button class="btn btn-ghost" :disabled="!running" @click="stopPush">停止</button>
        <button class="btn btn-ghost" @click="logs = []">清空日志</button>
      </div>

      <div class="status-tag" :class="running ? 'status-running' : 'status-idle'">
        {{ running ? '运行中' : '就绪' }}
      </div>

      <div class="log-box" ref="logBox">
        <div v-for="(line, i) in logs" :key="i" class="log-line" :class="lineClass(line)">{{ line }}</div>
        <div v-if="!logs.length" class="log-empty">等待执行...</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { getRawConfig, searchMaterialPush, stopMaterialPush } from '@/services/api'

const route = useRoute()
const isIncentive = computed(() => route.meta.mode === 'incentive')

// 防抖工具：在 delay ms 内仅执行最后一次调用
function debounce(fn, delay) {
  let t = null
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay) }
}

// 素材账号ID映射：默认空值，onMounted 时从配置读取，避免硬编码账户ID
const accountMap = ref({
  '安卓': '',
  'iOS': '',
})
const incentiveAccountId = ref('')

const _storedPlatform = localStorage.getItem('materialPush_platform')
const platform = ref(_storedPlatform || '安卓')
const accountId = ref('')
const dramaNames = ref(localStorage.getItem('materialPush_dramaNames') || '')
const running = ref(false)
const logs = ref([])
const logBox = ref(null)
const autoScroll = ref(true)

// 按平台分开的 localStorage key
const ACCOUNT_KEY = {
  '安卓': 'materialPush_accountId_android',
  'iOS': 'materialPush_accountId_ios',
}

// 缓存 dramaNames 和 platform
watch(dramaNames, (v) => localStorage.setItem('materialPush_dramaNames', v))
watch(platform, (v) => localStorage.setItem('materialPush_platform', v))
// accountId：用户手动修改时缓存到当前平台对应的 key（非自动填充触发）
// 初始为 true，防止 onMounted 前把空值写入 localStorage
let isAutoFill = true
const saveAccountId = debounce((v) => {
  const key = isIncentive.value ? 'materialPush_accountId_incentive' : ACCOUNT_KEY[platform.value]
  if (key) localStorage.setItem(key, v)
}, 400)
watch(accountId, (v) => {
  if (!isAutoFill) saveAccountId(v)
})

function onLogScroll() {
  if (!logBox.value) return
  const el = logBox.value
  autoScroll.value = el.scrollHeight - el.scrollTop - el.clientHeight < 40
}

// 切换平台或模式时，读取对应平台的缓存值；无缓存则回落到配置默认值
// 仅在配置已加载后执行（避免 onMounted 前覆盖）
let configLoaded = false
watch([platform, isIncentive], ([p, inc]) => {
  if (!configLoaded) return  // 配置未就绪时不覆盖，等 onMounted 赋值
  isAutoFill = true
  if (inc) {
    const cached = localStorage.getItem('materialPush_accountId_incentive')
    accountId.value = cached !== null ? cached : incentiveAccountId.value
  } else {
    const cached = localStorage.getItem(ACCOUNT_KEY[p])
    accountId.value = cached !== null ? cached : (accountMap.value[p] || accountMap.value['安卓'] || '')
  }
  nextTick(() => { isAutoFill = false })
})

function lineClass(line) {
  if (line.includes('✅') || line.includes('✔')) return 'log-success'
  if (line.includes('❌') || line.includes('失败')) return 'log-error'
  if (line.includes('⚠️') || line.includes('跳过')) return 'log-warn'
  return ''
}

function onToolLog(e) {
  logs.value.push(e.detail.message)
  if (autoScroll.value) {
    nextTick(() => { if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight })
  }
}
function onToolDone() { running.value = false }

onMounted(async () => {
  window.addEventListener('honguo:tool-log', onToolLog)
  window.addEventListener('honguo:tool-done', onToolDone)
  if (logBox.value) logBox.value.addEventListener('scroll', onLogScroll)

  // 等待 pywebview API 就绪后再读取配置
  try {
    const cfg = await getRawConfig()
    const ids = cfg?.common?.default_account_ids ?? {}
    if (ids.android) accountMap.value['安卓'] = ids.android
    if (ids.ios) accountMap.value['iOS'] = ids.ios
    if (ids.incentive) incentiveAccountId.value = ids.incentive
    configLoaded = true
    // 读取当前平台/模式对应的缓存账号ID；无缓存则用配置默认值
    isAutoFill = true
    if (isIncentive.value) {
      const cached = localStorage.getItem('materialPush_accountId_incentive')
      accountId.value = cached !== null ? cached : (ids.incentive ?? '')
    } else {
      const cached = localStorage.getItem(ACCOUNT_KEY[platform.value])
      accountId.value = cached !== null ? cached : (accountMap.value[platform.value] ?? '')
    }
    nextTick(() => { isAutoFill = false })
  } catch (_) {
    // 配置读取失败：仍需让 configLoaded=true + isAutoFill=false 兜底，
    // 否则 watch(accountId) 永远被 isAutoFill 跳过，用户输入无法缓存
    configLoaded = true
    isAutoFill = true
    try {
      if (isIncentive.value) {
        const cached = localStorage.getItem('materialPush_accountId_incentive')
        if (cached !== null) accountId.value = cached
      } else {
        const cached = localStorage.getItem(ACCOUNT_KEY[platform.value])
        if (cached !== null) accountId.value = cached
      }
    } finally {
      nextTick(() => { isAutoFill = false })
    }
  }
})
onUnmounted(() => {
  window.removeEventListener('honguo:tool-log', onToolLog)
  window.removeEventListener('honguo:tool-done', onToolDone)
  if (logBox.value) logBox.value.removeEventListener('scroll', onLogScroll)
})

async function startPush() {
  const names = dramaNames.value.split('\n').map(s => s.trim()).filter(Boolean)
  if (!names.length) { logs.value.push('⚠️ 请输入剧名'); return }
  running.value = true; logs.value = []
  await searchMaterialPush(names.join('\n'), accountId.value)
}

async function stopPush() {
  await stopMaterialPush()
}
</script>

<style scoped>
.view-container { max-width: 960px; }
.view-header { margin-bottom: 16px; }
.view-header h2 { font-size: 20px; font-weight: 700; margin-bottom: 4px; }
.view-desc { font-size: 13px; color: var(--c-dim); }
.form-row { display: flex; gap: 24px; align-items: flex-end; }
.form-col { display: flex; flex-direction: column; }
.field-label { display: block; font-size: 12px; font-weight: 600; color: var(--c-text-2); margin: 14px 0 6px; }
.text-input { padding: 8px 12px; border: 1px solid var(--c-border); border-radius: var(--r-sm); font-family: var(--f-mono); font-size: 13px; width: 280px; background: var(--c-card); outline: none; color: var(--c-text); }
.text-input:focus { border-color: var(--c-primary); }
.seg-group { display: flex; background: var(--c-surface); border-radius: var(--r-sm); padding: 3px; gap: 2px; }
.seg-btn { padding: 6px 18px; border: none; border-radius: 6px; font-size: 13px; font-weight: 600; font-family: var(--f-ui); color: var(--c-text); background: transparent; cursor: pointer; transition: all var(--transition-fast); }
.seg-btn:hover:not(.active) { background: var(--c-hover); }
.seg-btn.active { background: var(--c-primary); color: #fff; }
.input-area { width: 100%; padding: 10px 14px; border: 1px solid var(--c-border); border-radius: var(--r-sm); font-family: var(--f-mono); font-size: 12px; resize: vertical; background: var(--c-card); color: var(--c-text); outline: none; }
.btn-row { display: flex; gap: 8px; margin-top: 16px; }
.status-tag { display: inline-block; font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 10px; margin-top: 12px; }
.status-idle { background: var(--c-surface); color: var(--c-dim); }
.status-running { background: #ecfdf5; color: #065f46; }
.log-box { margin-top: 12px; background: var(--c-log-bg); border-radius: var(--r-md); padding: 14px; max-height: 360px; overflow-y: auto; font-family: var(--f-mono); font-size: 12px; line-height: 1.7; color: var(--c-log-fg); user-select: text; -webkit-user-select: text; cursor: text; }
.log-line { padding: 1px 0; }
.log-empty { color: var(--c-log-dim); }
.log-success { color: var(--c-green); }
.log-error { color: var(--c-red); }
.log-warn { color: var(--c-orange); }
</style>
