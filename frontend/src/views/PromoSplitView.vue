<template>
  <div class="view-container">
    <div class="view-header">
      <h2>✂️ 推广链分割</h2>
      <p class="view-desc">处理推广链统计表，按 IOS/Android × 每留/七留 拆分</p>
    </div>
    <div class="card">
      <div class="btn-row">
        <button class="btn btn-primary" :disabled="running" @click="startSplit">🚀 开始拆分</button>
        <button class="btn btn-ghost" @click="clearAll">清空日志</button>
      </div>

      <!-- 剧名过滤区 -->
      <div class="filter-block">
        <label class="filter-toggle">
          <input type="checkbox" v-model="useFilter" />
          <span>🎬 按剧名清单过滤</span>
        </label>
        <div v-if="useFilter" class="filter-body">
          <textarea
            v-model="filterText"
            class="filter-textarea"
            rows="4"
            placeholder="每行一个剧名，留空则不过滤"
          ></textarea>
          <p class="filter-hint">
            共 {{ filterNames.length }} 个剧名
            <span v-if="buildStore.lastDramaNames.length">
              · 上次搭建剧名：
              <button class="btn btn-ghost btn-sm" @click="fillFromLastBuild">填入</button>
            </span>
          </p>
        </div>
      </div>

      <div class="status-tag" :class="running ? 'status-running' : 'status-idle'">
        {{ running ? '处理中...' : statusText }}
      </div>

      <!-- 4宫格结果 -->
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
        <div v-if="!logs.length" class="log-empty">
          <p class="empty-title">📋 使用步骤</p>
          <ol class="empty-steps">
            <li>先在「推广链生成」页面生成推广链接</li>
            <li>从巨量引擎后台导出推广链统计表（Excel）</li>
            <li>确保 Excel 文件在下载目录中</li>
            <li>点击「开始拆分」自动读取并按方向分组</li>
          </ol>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { splitPromoLinks } from '@/services/api'
import { useBuildStore } from '@/stores/build'
import { useUiStore } from '@/stores/ui'
import { useToolLogger } from '../composables/useToolLogger'

const buildStore = useBuildStore()
const uiStore = useUiStore()
const router = useRouter()
const statusText = ref('就绪')
const { logs, running, logBox } = useToolLogger({
  onDone: () => { statusText.value = '处理完成' }
})

// 剧名过滤（持久化）
const useFilter = ref(localStorage.getItem('promoSplit_useFilter') === '1')
const filterText = ref(localStorage.getItem('promoSplit_filterText') || '')
const filterNames = computed(() =>
  filterText.value.split('\n').map(s => s.trim()).filter(Boolean)
)
watch(useFilter, (v) => localStorage.setItem('promoSplit_useFilter', v ? '1' : '0'))
watch(filterText, (v) => localStorage.setItem('promoSplit_filterText', v))

function fillFromLastBuild() {
  filterText.value = buildStore.lastDramaNames.join('\n')
}

// profile_key 映射：分割结果 key → 配置 profile key
const GROUPS_CACHE_KEY = 'promoSplit_groups'

function saveGroups() {
  const data = groups.value.map(({ key, text, count }) => ({ key, text, count }))
  localStorage.setItem(GROUPS_CACHE_KEY, JSON.stringify(data))
}

function loadGroups() {
  try {
    const raw = localStorage.getItem(GROUPS_CACHE_KEY)
    if (!raw) return
    const data = JSON.parse(raw)
    for (const g of groups.value) {
      const cached = data.find(d => d.key === g.key)
      if (cached) { g.text = cached.text || ''; g.count = cached.count || 0 }
    }
  } catch (_) {}
}

const groups = ref([
  { key: 'Android-每留', label: '安卓每留', count: 0, text: '' },
  { key: 'Android-七留', label: '安卓七留', count: 0, text: '' },
  { key: 'IOS-每留', label: 'iOS每留', count: 0, text: '' },
  { key: 'IOS-七留', label: 'iOS七留', count: 0, text: '' },
])

function onSplitResult(e) {
  const { texts, counts } = e.detail
  for (const g of groups.value) {
    if (texts[g.key] !== undefined) g.text = texts[g.key]
    if (counts[g.key] !== undefined) g.count = counts[g.key]
  }
  saveGroups()
}

onMounted(() => {
  window.addEventListener('honguo:split-result', onSplitResult)
  loadGroups()
})
onUnmounted(() => {
  window.removeEventListener('honguo:split-result', onSplitResult)
})

async function startSplit() {
  running.value = true
  logs.value = []
  statusText.value = '处理中...'
  const filter = useFilter.value && filterNames.value.length ? filterNames.value : null
  try {
    await splitPromoLinks('normal', filter)
  } catch (e) {
    logs.value.push(`❌ 分割失败: ${e.message || e}`)
    running.value = false
  }
}

function copyGroup(group) {
  navigator.clipboard.writeText(group.text)
  statusText.value = `✅ 已复制 ${group.label}`
}

function _isKnownLink(url) {
  const u = url.toLowerCase()
  return u.startsWith('http') && (
    u.includes('action_type=effective_play') ||
    u.includes('action_type=click') ||
    u.includes('action_type=view') ||
    u.includes('effective_play') ||
    u.includes('/display/') ||
    u.includes('impression')
  )
}

function _filterGroupText(raw) {
  // 每行 tab 分隔：计划名 + 多个链接列，只保留计划名 + 可识别的监控链接
  return raw.split('\n').map(line => {
    const cols = line.split('\t')
    if (cols.length <= 1) return line
    const name = cols[0]
    const links = cols.slice(1).filter(c => _isKnownLink(c.trim()))
    return [name, ...links].join('\t')
  }).join('\n')
}

function fillToLinkAssign(group) {
  if (!group.text) return
  uiStore.setPendingLinkData(_filterGroupText(group.text))
  router.push({ name: 'juming' })
}

function clearAll() {
  logs.value = []
  groups.value.forEach(g => { g.text = ''; g.count = 0 })
  statusText.value = '就绪'
  localStorage.removeItem(GROUPS_CACHE_KEY)
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
.status-running { background: rgba(0, 212, 138, 0.12); color: var(--c-green); }
.result-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 16px; }

@media (max-width: 768px) {
  .result-grid { grid-template-columns: 1fr; }
  .btn-row { flex-direction: column; }
}
.result-card { padding: 14px; }
.result-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.result-title { font-size: 13px; font-weight: 700; color: var(--c-text); }
.result-count { font-size: 11px; color: var(--c-dim); background: var(--c-surface); padding: 2px 8px; border-radius: 10px; }
.btn-sm { padding: 3px 8px; font-size: 11px; }
.result-textarea { width: 100%; padding: 8px 10px; border: 1px solid var(--c-border); border-radius: var(--r-sm); font-family: var(--f-mono); font-size: 11px; resize: vertical; background: var(--c-surface); color: var(--c-text); outline: none; }
.log-box { margin-top: 14px; background: var(--c-log-bg); border-radius: var(--r-md); padding: 14px; max-height: 180px; overflow-y: auto; font-family: var(--f-mono); font-size: 12px; line-height: 1.7; color: var(--c-log-fg); user-select: text; -webkit-user-select: text; cursor: text; }
.log-line { padding: 1px 0; }
.log-empty { color: var(--c-log-dim); }
.empty-title { font-size: 13px; font-weight: 600; color: var(--c-text-2); margin-bottom: 8px; }
.empty-steps { margin: 0; padding-left: 20px; font-size: 12px; color: var(--c-dim); line-height: 2; }
.empty-steps li { padding: 0; }

/* 过滤区 */
.filter-block { margin-top: 14px; padding: 12px 14px; background: var(--c-surface); border-radius: var(--r-sm); border: 1px solid var(--c-border); }
.filter-toggle { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; cursor: pointer; user-select: none; }
.filter-toggle input { accent-color: var(--c-primary); width: 15px; height: 15px; cursor: pointer; }
.filter-body { margin-top: 10px; }
.filter-textarea { width: 100%; padding: 8px 10px; border: 1px solid var(--c-border); border-radius: var(--r-sm); font-family: var(--f-mono); font-size: 12px; resize: vertical; background: var(--c-bg); color: var(--c-text); outline: none; }
.filter-hint { margin-top: 6px; font-size: 11px; color: var(--c-dim); display: flex; align-items: center; gap: 6px; }
</style>
