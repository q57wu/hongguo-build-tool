<template>
  <div class="view-container">
    <div class="view-header">
      <h2>🔗 激励推广链生成</h2>
      <p class="view-desc">为短剧激励活动批量创建推广链接</p>
    </div>
    <div class="card">
      <div class="form-row">
        <div class="form-col">
          <label class="field-label">执行次数</label>
          <input v-model.number="count" type="number" class="param-input" min="1" />
        </div>
        <div class="form-col">
          <label class="field-label">方向后缀</label>
          <select v-model="suffix" class="param-input" style="width: 120px;">
            <option value="每留">每留</option>
            <option value="七留">七留</option>
          </select>
        </div>
      </div>

      <div class="btn-row">
        <button class="btn btn-primary" :disabled="running" @click="start">🚀 开始生成</button>
        <button class="btn btn-ghost" :disabled="!running" @click="stop">停止</button>
        <button class="btn btn-ghost" @click="logs = []">清空日志</button>
      </div>

      <div class="status-tag" :class="running ? 'status-running' : 'status-idle'">
        {{ running ? '运行中' : '就绪' }}
      </div>

      <div class="log-box" ref="logBox">
        <div v-for="(line, i) in logs" :key="i" class="log-line">{{ line }}</div>
        <div v-if="!logs.length" class="log-empty">等待执行...</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { generateIncentiveChain, stopIncentiveChain } from '@/services/api'

const count = ref(parseInt(localStorage.getItem('incentiveChain_count')) || 10)
const suffix = ref(localStorage.getItem('incentiveChain_suffix') || '每留')

watch(count, (v) => localStorage.setItem('incentiveChain_count', v))
watch(suffix, (v) => localStorage.setItem('incentiveChain_suffix', v))
const running = ref(false)
const logs = ref([])
const logBox = ref(null)
const autoScroll = ref(true)

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
function onToolDone() { running.value = false }

onMounted(() => {
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
  if (!count.value || count.value < 1) { logs.value.push('⚠️ 请输入有效的正整数'); return }
  running.value = true; logs.value = []
  await generateIncentiveChain({ count: count.value, suffix: suffix.value })
}

async function stop() {
  await stopIncentiveChain()
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
.param-input { width: 90px; padding: 7px 10px; border: 1px solid var(--c-border); border-radius: var(--r-sm); font-size: 13px; font-family: var(--f-ui); background: #fff; }
.btn-row { display: flex; gap: 8px; margin-top: 16px; }
.status-tag { display: inline-block; font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 10px; margin-top: 12px; }
.status-idle { background: var(--c-surface); color: var(--c-dim); }
.status-running { background: #ecfdf5; color: #065f46; }
.log-box { margin-top: 12px; background: var(--c-log-bg); border-radius: var(--r-md); padding: 14px; max-height: 360px; overflow-y: auto; font-family: var(--f-mono); font-size: 12px; line-height: 1.7; color: var(--c-log-fg); user-select: text; -webkit-user-select: text; cursor: text; }
.log-line { padding: 1px 0; }
.log-empty { color: var(--c-log-dim); }
</style>
