<template>
  <div class="view-container">
    <div class="view-header">
      <h2>⚡ 激励推广链分割</h2>
      <p class="view-desc">处理推广链统计表，按激励每留/七留拆分</p>
    </div>
    <div class="card">
      <div class="btn-row">
        <button class="btn btn-primary" :disabled="running" @click="startSplit">🚀 开始拆分</button>
        <button class="btn btn-ghost" @click="clearAll">清空日志</button>
      </div>

      <div class="status-tag" :class="running ? 'status-running' : 'status-idle'">
        {{ running ? '处理中...' : statusText }}
      </div>

      <div class="result-grid">
        <div v-for="group in groups" :key="group.key" class="result-card card">
          <div class="result-head">
            <span class="result-title">{{ group.label }}</span>
            <span class="result-count">{{ group.count }} 条</span>
            <button class="btn btn-ghost btn-sm" @click="copyGroup(group)">📋 复制</button>
            <button class="btn btn-ghost btn-sm" :disabled="!group.text" @click="fillToLinkAssign(group)">
              🔗 填入链接分配
            </button>
          </div>
          <textarea :value="group.text" class="result-textarea" rows="8" readonly></textarea>
        </div>
      </div>

      <div class="log-box" ref="logBox">
        <div v-for="(line, i) in logs" :key="i" class="log-line">{{ line }}</div>
        <div v-if="!logs.length" class="log-empty">等待处理...</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { splitIncentiveLinks } from '@/services/api'
import { useUiStore } from '@/stores/ui'

const uiStore = useUiStore()
const router = useRouter()

const running = ref(false)
const statusText = ref('就绪')
const logs = ref([])
const logBox = ref(null)
const autoScroll = ref(true)

const groups = ref([
  { key: '激励-每留', label: '激励每留', count: 0, text: '' },
  { key: '激励-七留', label: '激励七留', count: 0, text: '' },
])

function onLogScroll() {
  if (!logBox.value) return
  const el = logBox.value
  autoScroll.value = el.scrollHeight - el.scrollTop - el.clientHeight < 40
}

function onToolLog(e) {
  logs.value.push(e.detail.message)
  if (autoScroll.value) {
    nextTick(() => { if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight })
  }
}
function onSplitResult(e) {
  const { texts, counts } = e.detail
  for (const g of groups.value) {
    if (texts[g.key] !== undefined) g.text = texts[g.key]
    if (counts[g.key] !== undefined) g.count = counts[g.key]
  }
}
function onToolDone() { running.value = false; statusText.value = '处理完成' }

onMounted(() => {
  window.addEventListener('honguo:tool-log', onToolLog)
  window.addEventListener('honguo:split-result', onSplitResult)
  window.addEventListener('honguo:tool-done', onToolDone)
  if (logBox.value) logBox.value.addEventListener('scroll', onLogScroll)
})
onUnmounted(() => {
  window.removeEventListener('honguo:tool-log', onToolLog)
  window.removeEventListener('honguo:split-result', onSplitResult)
  window.removeEventListener('honguo:tool-done', onToolDone)
  if (logBox.value) logBox.value.removeEventListener('scroll', onLogScroll)
})

async function startSplit() {
  running.value = true; logs.value = []; statusText.value = '处理中...'
  await splitIncentiveLinks()
}

function copyGroup(group) {
  navigator.clipboard.writeText(group.text)
  statusText.value = `✅ 已复制 ${group.label}`
}

function fillToLinkAssign(group) {
  if (!group.text) return
  uiStore.setPendingLinkData(group.text)
  router.push({ name: 'incentive-link' })
}

function clearAll() {
  logs.value = []; groups.value.forEach(g => { g.text = ''; g.count = 0 }); statusText.value = '就绪'
}
</script>

<style scoped>
.view-container { max-width: 1000px; }
.view-header { margin-bottom: 16px; }
.view-header h2 { font-size: 20px; font-weight: 700; margin-bottom: 4px; }
.view-desc { font-size: 13px; color: var(--c-dim); }
.btn-row { display: flex; gap: 8px; }
.status-tag { display: inline-block; font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 10px; margin-top: 12px; }
.status-idle { background: var(--c-surface); color: var(--c-dim); }
.status-running { background: #ecfdf5; color: #065f46; }
.result-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 16px; }
.result-card { padding: 14px; }
.result-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.result-title { font-size: 13px; font-weight: 700; }
.result-count { font-size: 11px; color: var(--c-dim); background: var(--c-surface); padding: 2px 8px; border-radius: 10px; }
.btn-sm { padding: 3px 8px; font-size: 11px; }
.result-textarea { width: 100%; padding: 8px 10px; border: 1px solid var(--c-border); border-radius: var(--r-sm); font-family: var(--f-mono); font-size: 11px; resize: vertical; background: var(--c-surface); color: var(--c-text); }
.log-box { margin-top: 14px; background: var(--c-log-bg); border-radius: var(--r-md); padding: 14px; max-height: 180px; overflow-y: auto; font-family: var(--f-mono); font-size: 12px; line-height: 1.7; color: var(--c-log-fg); user-select: text; -webkit-user-select: text; cursor: text; }
.log-line { padding: 1px 0; }
.log-empty { color: var(--c-log-dim); }
</style>
