<template>
  <div class="view-container">
    <div class="view-header">
      <h2>🕷️ 爬取历史跑量素材</h2>
      <p class="view-desc">输入剧名，自动从素材管理页面爬取历史跑量素材ID</p>
    </div>
    <div class="card">
      <div class="form-row">
        <div class="form-col">
          <label class="field-label">最低消耗（元）</label>
          <input v-model.number="minCost" type="number" class="text-input" style="width: 140px;" />
        </div>
        <div class="form-col">
          <label class="field-label">最少集数</label>
          <input v-model.number="minCount" type="number" class="text-input" style="width: 140px;" />
        </div>
      </div>

      <label class="field-label">剧名（每行一个）</label>
      <textarea v-model="dramaNames" class="input-area" rows="6" placeholder="输入剧名，每行一个"></textarea>

      <div class="btn-row">
        <button class="btn btn-primary" :disabled="running" @click="startCrawl">🚀 开始爬取</button>
        <button class="btn btn-ghost" :disabled="!running" @click="stopCrawl">停止</button>
        <button class="btn btn-ghost" @click="logs = []">清空日志</button>
      </div>

      <div class="status-tag" :class="running ? 'status-running' : 'status-idle'">
        {{ running ? '爬取中...' : '就绪' }}
      </div>

      <div class="log-box" ref="logBox">
        <div v-for="(line, i) in logs" :key="i" class="log-line" :class="lineClass(line)">{{ line }}</div>
        <div v-if="!logs.length" class="log-empty">等待执行...</div>
      </div>

      <!-- 结果区域 -->
      <div v-if="result" class="result-section">
        <div class="result-header">
          <label class="field-label" style="margin-top: 0;">📋 爬取结果</label>
          <button class="btn btn-ghost btn-sm" @click="copyResult">复制结果</button>
        </div>
        <pre class="result-box">{{ result }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { crawlMaterialIds, stopCrawlMaterial } from '@/services/api'

const minCost = ref(parseFloat(localStorage.getItem('crawl_minCost')) || 1000)
const minCount = ref(parseInt(localStorage.getItem('crawl_minCount')) || 6)
const dramaNames = ref(localStorage.getItem('crawl_dramaNames') || '')

watch(minCost, (v) => localStorage.setItem('crawl_minCost', v))
watch(minCount, (v) => localStorage.setItem('crawl_minCount', v))
watch(dramaNames, (v) => localStorage.setItem('crawl_dramaNames', v))
const running = ref(false)
const logs = ref([])
const result = ref('')
const logBox = ref(null)
const autoScroll = ref(true)

function onLogScroll() {
  if (!logBox.value) return
  const el = logBox.value
  autoScroll.value = el.scrollHeight - el.scrollTop - el.clientHeight < 40
}

function lineClass(line) {
  if (line.includes('✅') || line.includes('完成')) return 'log-success'
  if (line.includes('❌') || line.includes('失败')) return 'log-error'
  if (line.includes('⚠️') || line.includes('跳过')) return 'log-warn'
  if (line.startsWith('结果:')) return 'log-success'
  return ''
}

function onToolLog(e) {
  const msg = e.detail.message
  logs.value.push(msg)
  if (msg.startsWith('RESULT:')) {
    result.value = msg.replace(/^RESULT:\s*/, '').trim()
  }
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

async function startCrawl() {
  const names = dramaNames.value.split('\n').map(s => s.trim()).filter(Boolean)
  if (!names.length) { logs.value.push('⚠️ 请输入剧名'); return }
  running.value = true
  logs.value = []
  result.value = ''
  await crawlMaterialIds(names, minCost.value, minCount.value)
}

async function stopCrawl() {
  await stopCrawlMaterial()
}

function copyResult() {
  if (result.value) {
    navigator.clipboard.writeText(result.value)
    logs.value.push('✅ 已复制到剪贴板')
  }
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
.text-input { padding: 8px 12px; border: 1px solid var(--c-border); border-radius: var(--r-sm); font-family: var(--f-mono); font-size: 13px; background: var(--c-card); color: var(--c-text); outline: none; }
.text-input:focus { border-color: var(--c-primary); }
.input-area { width: 100%; padding: 10px 14px; border: 1px solid var(--c-border); border-radius: var(--r-sm); font-family: var(--f-mono); font-size: 12px; resize: vertical; background: var(--c-card); color: var(--c-text); outline: none; }
.btn-row { display: flex; gap: 8px; margin-top: 16px; }
.btn-sm { font-size: 11px; padding: 4px 10px; }
.status-tag { display: inline-block; font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 10px; margin-top: 12px; }
.status-idle { background: var(--c-surface); color: var(--c-dim); }
.status-running { background: #ecfdf5; color: #065f46; }
.log-box { margin-top: 12px; background: var(--c-log-bg); border-radius: var(--r-md); padding: 14px; max-height: 300px; overflow-y: auto; font-family: var(--f-mono); font-size: 12px; line-height: 1.7; color: var(--c-log-fg); user-select: text; -webkit-user-select: text; cursor: text; }
.log-line { padding: 1px 0; }
.log-empty { color: var(--c-log-dim); }
.log-success { color: var(--c-green); }
.log-error { color: var(--c-red); }
.log-warn { color: var(--c-orange); }
.result-section { margin-top: 16px; }
.result-header { display: flex; justify-content: space-between; align-items: center; }
.result-box { background: var(--c-surface); border: 1px solid var(--c-border); border-radius: var(--r-sm); padding: 14px; font-family: var(--f-mono); font-size: 12px; line-height: 1.8; white-space: pre-wrap; word-break: break-all; max-height: 300px; overflow-y: auto; margin-top: 6px; }
</style>
