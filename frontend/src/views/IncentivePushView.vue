<template>
  <div class="view-container">
    <div class="view-header">
      <h2>📤 激励推送</h2>
      <p class="view-desc">连接浏览器，在素材管理页面逐页全选并批量推送</p>
    </div>
    <div class="card">
      <label class="field-label">广告账户 ID</label>
      <input v-model="accountId" class="text-input" placeholder="输入广告账户ID" />

      <div class="btn-row">
        <button class="btn btn-primary" :disabled="running" @click="start">🚀 开始推送</button>
        <button class="btn btn-ghost" :disabled="!running" @click="stop">停止</button>
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
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { getConfig, startIncentivePush, stopIncentivePush } from '@/services/api'

// 默认空值，onMounted 时从配置读取，避免硬编码账户ID
const accountId = ref('')
const running = ref(false)
const logs = ref([])
const logBox = ref(null)
const autoScroll = ref(true)

function onLogScroll() {
  if (!logBox.value) return
  const el = logBox.value
  autoScroll.value = el.scrollHeight - el.scrollTop - el.clientHeight < 40
}

function lineClass(line) {
  if (line.includes('✅') || line.includes('✔')) return 'log-success'
  if (line.includes('❌')) return 'log-error'
  if (line.includes('⚠️')) return 'log-warn'
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
  // 从 config.json 读取默认激励账户ID，避免硬编码
  try {
    const cfg = await getConfig()
    accountId.value = cfg?.common?.default_account_ids?.incentive ?? ''
  } catch (_) { /* 读取失败时保持空值，用户手动输入 */ }
  window.addEventListener('honguo:tool-log', onToolLog)
  window.addEventListener('honguo:tool-done', onToolDone)
  if (logBox.value) logBox.value.addEventListener('scroll', onLogScroll)
})
onUnmounted(() => {
  window.removeEventListener('honguo:tool-log', onToolLog)
  window.removeEventListener('honguo:tool-done', onToolDone)
  if (logBox.value) logBox.value.removeEventListener('scroll', onLogScroll)
})

async function start() {
  if (running.value) return
  if (!accountId.value.trim()) { logs.value.push('⚠️ 请输入广告账户 ID'); return }
  running.value = true; logs.value = []
  await startIncentivePush(accountId.value.trim(), {})
}

async function stop() {
  await stopIncentivePush()
}
</script>

<style scoped>
.view-container { max-width: 960px; }
.view-header { margin-bottom: 16px; }
.view-header h2 { font-size: 20px; font-weight: 700; margin-bottom: 4px; }
.view-desc { font-size: 13px; color: var(--c-dim); }
.field-label { display: block; font-size: 12px; font-weight: 600; color: var(--c-text-2); margin: 14px 0 6px; }
.text-input { padding: 8px 12px; border: 1px solid var(--c-border); border-radius: var(--r-sm); font-family: var(--f-mono); font-size: 13px; width: 300px; background: #fff; outline: none; }
.text-input:focus { border-color: var(--c-primary); }
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
