<template>
  <div class="view-container">
    <div class="view-header">
      <h2>📡 RTA 工具</h2>
      <p class="view-desc">批量设置或检测 RTA 生效范围（依赖 Chrome 9222 CDP 连接）</p>
    </div>
    <div class="card">
      <!-- 剧型选择 -->
      <label class="field-label">剧型</label>
      <div class="radio-group">
        <label v-for="opt in dramaOptions" :key="opt.value" class="radio-label">
          <input type="radio" v-model="dramaType" :value="opt.value" :disabled="running" />
          {{ opt.label }}
        </label>
      </div>

      <!-- aadvid 输入 -->
      <label class="field-label">aadvid 列表（每行一个）</label>
      <textarea
        v-model="aadvidsText"
        class="input-area"
        rows="8"
        placeholder="粘贴 aadvid，每行一个"
        :disabled="running"
      ></textarea>

      <!-- 操作按钮 -->
      <div class="btn-row">
        <button class="btn btn-primary" :disabled="running" @click="startSet">🔧 设置 RTA</button>
        <button class="btn btn-primary btn-check" :disabled="running" @click="startCheck">🔍 检测 RTA</button>
        <button class="btn btn-ghost" :disabled="!running" @click="stopCurrent">停止</button>
        <button class="btn btn-ghost" :disabled="running" @click="logs = []">清空日志</button>
      </div>

      <!-- 状态标签 -->
      <div class="status-tag" :class="running ? 'status-running' : 'status-idle'">
        {{ running ? (currentAction === 'set' ? '设置中...' : '检测中...') : '就绪' }}
      </div>

      <!-- 日志区域 -->
      <div class="log-box" ref="logBox">
        <div v-for="(line, i) in logs" :key="i" class="log-line" :class="lineClass(line)">{{ line }}</div>
        <div v-if="!logs.length" class="log-empty">等待执行...</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { rtaSet, stopRtaSet, rtaCheck, stopRtaCheck } from '@/services/api'

const dramaOptions = [
  { value: '1', label: '常规剧' },
  { value: '2', label: '定制剧' },
  { value: '3', label: '激励' },
]

const dramaType = ref(localStorage.getItem('rta_dramaType') || '1')
const aadvidsText = ref(localStorage.getItem('rta_aadvids') || '')
const running = ref(false)
const currentAction = ref('')
const logs = ref([])
const logBox = ref(null)
const autoScroll = ref(true)

watch(dramaType, (v) => localStorage.setItem('rta_dramaType', v))
watch(aadvidsText, (v) => localStorage.setItem('rta_aadvids', v))

function parseAadvids() {
  return aadvidsText.value.split('\n').map(s => s.trim()).filter(Boolean)
}

function lineClass(line) {
  if (line.includes('✅') || line.includes('成功') || line.includes('完成')) return 'log-success'
  if (line.includes('❌') || line.includes('失败') || line.includes('异常')) return 'log-error'
  if (line.includes('⚠️') || line.includes('未启用') || line.includes('未传入')) return 'log-warn'
  return ''
}

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

function onToolDone() {
  running.value = false
  currentAction.value = ''
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

async function startSet() {
  const ids = parseAadvids()
  if (!ids.length) { logs.value.push('⚠️ 请输入 aadvid'); return }
  running.value = true
  currentAction.value = 'set'
  logs.value = []
  await rtaSet(dramaType.value, ids)
}

async function startCheck() {
  const ids = parseAadvids()
  if (!ids.length) { logs.value.push('⚠️ 请输入 aadvid'); return }
  running.value = true
  currentAction.value = 'check'
  logs.value = []
  await rtaCheck(dramaType.value, ids)
}

async function stopCurrent() {
  if (currentAction.value === 'set') await stopRtaSet()
  else if (currentAction.value === 'check') await stopRtaCheck()
}
</script>

<style scoped>
.view-container { max-width: 960px; }
.view-header { margin-bottom: 16px; }
.view-header h2 { font-size: 20px; font-weight: 700; margin-bottom: 4px; }
.view-desc { font-size: 13px; color: var(--c-dim); }
.field-label { display: block; font-size: 12px; font-weight: 600; color: var(--c-text-2); margin: 14px 0 6px; }
.radio-group { display: flex; gap: 20px; }
.radio-label { display: flex; align-items: center; gap: 6px; font-size: 13px; cursor: pointer; font-family: var(--f-ui); }
.radio-label input { accent-color: var(--c-primary); }
.input-area { width: 100%; padding: 10px 14px; border: 1px solid var(--c-border); border-radius: var(--r-sm); font-family: var(--f-mono); font-size: 12px; resize: vertical; background: var(--c-card); color: var(--c-text); outline: none; box-sizing: border-box; }
.input-area:focus { border-color: var(--c-primary); }
.btn-row { display: flex; gap: 8px; margin-top: 16px; flex-wrap: wrap; }
.btn-check { background: #0891b2; }
.btn-check:hover:not(:disabled) { background: #0e7490; }
.status-tag { display: inline-block; font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 10px; margin-top: 12px; }
.status-idle { background: var(--c-surface); color: var(--c-dim); }
.status-running { background: #ecfdf5; color: #065f46; }
.log-box { margin-top: 12px; background: var(--c-log-bg); border-radius: var(--r-md); padding: 14px; max-height: 350px; overflow-y: auto; font-family: var(--f-mono); font-size: 12px; line-height: 1.7; color: var(--c-log-fg); user-select: text; -webkit-user-select: text; cursor: text; }
.log-line { padding: 1px 0; }
.log-empty { color: var(--c-log-dim); }
.log-success { color: var(--c-green); }
.log-error { color: var(--c-red); }
.log-warn { color: var(--c-orange); }
</style>
