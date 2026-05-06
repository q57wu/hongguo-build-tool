<template>
  <div class="view-container">
    <div class="view-header">
      <h2>🔗 推广链生成</h2>
      <p class="view-desc">输入剧名并选择方向，自动生成推广链接</p>
    </div>
    <div class="card">
      <label class="field-label">剧名（每行一个）</label>
      <textarea v-model="dramaNames" class="input-area" rows="6" placeholder="输入剧名，每行一个"></textarea>

      <label class="field-label">执行方向</label>
      <div class="checkbox-group">
        <label v-for="opt in taskOptions" :key="opt.value" class="checkbox-item">
          <input type="checkbox" v-model="opt.checked" />
          <span>{{ opt.label }}</span>
        </label>
      </div>

      <div class="btn-row">
        <button class="btn btn-primary" :disabled="running" @click="start">🚀 开始生成</button>
        <button class="btn btn-ghost" :disabled="!running" @click="stop">停止</button>
        <button class="btn btn-ghost" @click="logs = []">清空日志</button>
      </div>

      <div class="status-tag" :class="statusClass">{{ statusText }}</div>

      <div class="log-box" ref="logBox">
        <div v-for="(line, i) in logs" :key="i" class="log-line">{{ line }}</div>
        <div v-if="!logs.length" class="log-empty">等待执行...</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { generatePromoChain, stopPromoChain } from '@/services/api'

const _cachedDramaNames = localStorage.getItem('promoChain_dramaNames') || ''
const dramaNames = ref(_cachedDramaNames)
watch(dramaNames, (v) => localStorage.setItem('promoChain_dramaNames', v))

const running = ref(false)
const logs = ref([])
const status = ref('idle')
const logBox = ref(null)
const autoScroll = ref(true)

const _cachedOptions = (() => {
  try { return JSON.parse(localStorage.getItem('promoChain_options') || 'null') } catch { return null }
})()

const taskOptions = ref([
  { label: '安卓每留', value: 0, checked: _cachedOptions ? _cachedOptions[0] : true },
  { label: '安卓七留', value: 1, checked: _cachedOptions ? _cachedOptions[1] : true },
  { label: 'iOS每留', value: 2, checked: _cachedOptions ? _cachedOptions[2] : true },
  { label: 'iOS七留', value: 3, checked: _cachedOptions ? _cachedOptions[3] : true },
])
watch(taskOptions, (opts) => {
  localStorage.setItem('promoChain_options', JSON.stringify(opts.map(o => o.checked)))
}, { deep: true })

const statusClass = computed(() => ({ 'status-running': running.value, 'status-idle': !running.value }))
const statusText = computed(() => running.value ? '运行中' : '就绪')

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
function onToolDone(e) {
  running.value = false
}

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
  const names = dramaNames.value.split('\n').map(s => s.trim()).filter(Boolean)
  if (!names.length) { logs.value.push('⚠️ 请输入剧名'); return }
  const directions = taskOptions.value.filter(o => o.checked).map(o => o.value)
  if (!directions.length) { logs.value.push('⚠️ 请选择至少一个方向'); return }
  running.value = true
  logs.value = []
  await generatePromoChain(names, directions)
}

async function stop() {
  await stopPromoChain()
}
</script>

<style scoped>
.view-container { max-width: 960px; }
.view-header { margin-bottom: 16px; }
.view-header h2 { font-size: 20px; font-weight: 700; margin-bottom: 4px; }
.view-desc { font-size: 13px; color: var(--c-dim); }
.field-label { display: block; font-size: 12px; font-weight: 600; color: var(--c-text-2); margin: 14px 0 6px; }
.input-area { width: 100%; padding: 10px 14px; border: 1px solid var(--c-border); border-radius: var(--r-sm); font-family: var(--f-mono); font-size: 12px; resize: vertical; background: #fff; color: var(--c-text); outline: none; }
.input-area:focus { border-color: var(--c-primary); }

.checkbox-group { display: flex; flex-wrap: wrap; gap: 12px; }
.checkbox-item { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--c-text); cursor: pointer; }
.checkbox-item input { accent-color: var(--c-primary); }

.btn-row { display: flex; gap: 8px; margin-top: 16px; }
.status-tag { display: inline-block; font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 10px; margin-top: 12px; }
.status-idle { background: var(--c-surface); color: var(--c-dim); }
.status-running { background: #ecfdf5; color: #065f46; }

.log-box { margin-top: 12px; background: var(--c-log-bg); border-radius: var(--r-md); padding: 14px; max-height: 360px; overflow-y: auto; font-family: var(--f-mono); font-size: 12px; line-height: 1.7; color: var(--c-log-fg); user-select: text; -webkit-user-select: text; cursor: text; }
.log-line { padding: 1px 0; }
.log-empty { color: var(--c-log-dim); }
</style>
