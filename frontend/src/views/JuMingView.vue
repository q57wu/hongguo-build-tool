<template>
  <div class="view-container">
    <div class="view-header">
      <h2>📋 剧名链接整理</h2>
      <p class="view-desc">批量分配账户与短剧数据，管理剧单库</p>
    </div>

    <!-- Tab 切换 -->
    <div class="tab-bar">
      <button class="tab-btn" :class="{ active: tab === 'batch' }" @click="tab = 'batch'">批量分配</button>
      <button class="tab-btn" :class="{ active: tab === 'titles' }" @click="tab = 'titles'">剧单管理</button>
    </div>

    <!-- 批量分配 -->
    <div v-show="tab === 'batch'" class="tab-content">
      <div class="card">
        <label class="field-label" for="juming-account-ids">账户 ID（每行一个）</label>
        <textarea id="juming-account-ids" v-model="accountIds" class="input-area" rows="4" placeholder="输入账户ID，每行一个"></textarea>

        <label class="field-label" for="juming-drama-data">短剧数据（剧名+链接，空行分隔各组）</label>
        <textarea id="juming-drama-data" v-model="dramaData" class="input-area" rows="6" placeholder="剧名&#10;点击监测链接&#10;展示监测链接&#10;视频播放监测链接&#10;&#10;下一部剧..."></textarea>

        <label class="field-label" for="juming-material-ids">素材 ID（可选，空格/换行分隔）</label>
        <textarea id="juming-material-ids" v-model="materialIds" class="input-area" rows="3" placeholder="素材ID1 素材ID2 ..."></textarea>

        <div class="params-row">
          <div class="param-item">
            <label class="param-label">每组ID数</label>
            <input v-model.number="idsPerGroup" type="number" class="param-input" min="1" />
          </div>
          <div class="param-item">
            <label class="param-label">每组剧数</label>
            <input v-model.number="dramasPerGroup" type="number" class="param-input" min="1" />
          </div>
          <div class="param-item">
            <label class="param-label">行间距</label>
            <select v-model.number="spacing" class="param-input">
              <option :value="0">0</option>
              <option :value="1">1</option>
              <option :value="2">2</option>
              <option :value="3">3</option>
            </select>
          </div>
        </div>

        <div class="btn-row">
          <button class="btn btn-primary" @click="batchProcess">🚀 批量分配</button>
          <button class="btn btn-ghost" @click="clearBatch">🗑 清空</button>
        </div>

        <p v-if="batchStatus" class="status-text">{{ batchStatus }}</p>

        <label v-if="batchResult" class="field-label">分配结果</label>
        <textarea v-if="batchResult" v-model="batchResult" class="input-area result-area" rows="12" readonly></textarea>

        <div v-if="batchResult" class="btn-row" style="margin-top: 8px;">
          <button class="btn btn-ghost" @click="copyResult">📋 复制结果</button>
        </div>

        <div v-if="batchResult" class="add-to-config">
          <label class="field-label">添加到配置</label>
          <div class="add-btn-row">
            <button v-for="pk in profileKeys" :key="pk"
                    class="btn btn-outline-sm"
                    @click="addToProfile(pk)">
              ➕ {{ pk }}
            </button>
          </div>
          <span v-if="addStatus" class="add-status" :class="addStatus.startsWith('✅') ? 'status-ok' : 'status-err'">{{ addStatus }}</span>
        </div>
      </div>
    </div>

    <!-- 剧单管理 -->
    <div v-show="tab === 'titles'" class="tab-content">
      <div class="card">
        <label class="field-label">新增剧名（每行一个）</label>
        <textarea v-model="newTitles" class="input-area" rows="6" placeholder="输入完整剧名，每行一个"></textarea>

        <div class="btn-row">
          <button class="btn btn-primary" @click="appendTitles">➕ 追加到剧单</button>
          <button class="btn btn-ghost" @click="newTitles = ''">🗑 清空输入</button>
          <button class="btn btn-ghost" @click="loadTitles">🔄 刷新</button>
        </div>

        <p v-if="titleStatus" class="status-text">{{ titleStatus }}</p>

        <label class="field-label">当前剧单库（{{ titlesList.length }} 部）</label>
        <textarea :value="titlesList.join('\n')" class="input-area result-area" rows="14" readonly></textarea>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { batchAssign, getDramaTitles, appendDramaTitles, addResultToProfile } from '@/services/api'
import { useUiStore } from '@/stores/ui'

const uiStore = useUiStore()
const tab = ref('batch')

// 批量分配
const accountIds = ref(localStorage.getItem('juming_accountIds') || '')
const dramaData = ref(localStorage.getItem('juming_dramaData') || '')
const materialIds = ref(localStorage.getItem('juming_materialIds') || '')
const idsPerGroup = ref(parseInt(localStorage.getItem('juming_idsPerGroup')) || 6)
const dramasPerGroup = ref(parseInt(localStorage.getItem('juming_dramasPerGroup')) || 3)
const _savedJumingSpacing = localStorage.getItem('juming_spacing')
const spacing = ref(_savedJumingSpacing !== null ? parseInt(_savedJumingSpacing) : 1)
const batchResult = ref('')
const batchStatus = ref('')

watch(idsPerGroup, (v) => { if (Number.isFinite(v) && v > 0) localStorage.setItem('juming_idsPerGroup', v) })
watch(dramasPerGroup, (v) => { if (Number.isFinite(v) && v > 0) localStorage.setItem('juming_dramasPerGroup', v) })
watch(spacing, (v) => { if (Number.isFinite(v) && v >= 0) localStorage.setItem('juming_spacing', v) })
watch(accountIds, (v) => localStorage.setItem('juming_accountIds', v))
watch(dramaData, (v) => localStorage.setItem('juming_dramaData', v))
watch(materialIds, (v) => localStorage.setItem('juming_materialIds', v))

async function batchProcess() {
  batchStatus.value = '处理中...'
  try {
    const res = await batchAssign(
      accountIds.value, dramaData.value,
      idsPerGroup.value, dramasPerGroup.value,
      materialIds.value, spacing.value
    )
    if (res.ok) {
      batchResult.value = res.result
      batchStatus.value = res.summary || '分配完成'
    } else {
      batchStatus.value = '❌ ' + (res.error || '处理失败')
    }
  } catch (e) {
    batchStatus.value = '❌ ' + e.message
  }
}

function clearBatch() {
  accountIds.value = ''
  dramaData.value = ''
  materialIds.value = ''
  batchResult.value = ''
  batchStatus.value = ''
  localStorage.removeItem('juming_accountIds')
  localStorage.removeItem('juming_dramaData')
  localStorage.removeItem('juming_materialIds')
}

function copyResult() {
  navigator.clipboard.writeText(batchResult.value)
  batchStatus.value = '✅ 已复制到剪贴板'
}

// 剧单管理
const newTitles = ref('')
const titlesList = ref([])
const titleStatus = ref('')

async function loadTitles() {
  try {
    titlesList.value = await getDramaTitles()
  } catch (e) {
    titleStatus.value = '❌ 加载失败'
  }
}

async function appendTitles() {
  const titles = newTitles.value.split('\n').map(s => s.trim()).filter(Boolean)
  if (!titles.length) { titleStatus.value = '请输入剧名'; return }
  try {
    const res = await appendDramaTitles(titles)
    if (res.ok) {
      titleStatus.value = `✅ 成功追加 ${res.added} 部剧名`
      newTitles.value = ''
      await loadTitles()
    }
  } catch (e) {
    titleStatus.value = '❌ ' + e.message
  }
}

onMounted(() => {
  loadTitles()
  const pending = uiStore.consumePendingLinkData()
  if (pending) {
    dramaData.value = pending.rawData
  }
})

const profileKeys = [
  '安卓-每留', '安卓-七留', 'IOS-每留', 'IOS-七留',
  '安卓-激励每留', '安卓-激励七留'
]
const addStatus = ref('')

async function addToProfile(profileKey) {
  if (!batchResult.value) return
  try {
    const res = await addResultToProfile(profileKey, batchResult.value)
    addStatus.value = res.ok
      ? `✅ 已添加 ${res.count} 组到「${profileKey}」`
      : `❌ ${res.error}`
  } catch (e) {
    addStatus.value = `❌ ${e.message}`
  }
  setTimeout(() => addStatus.value = '', 4000)
}
</script>

<style scoped>
.view-container { max-width: 960px; }
.view-header { margin-bottom: 16px; }
.view-header h2 { font-size: 20px; font-weight: 700; margin-bottom: 4px; }
.view-desc { font-size: 13px; color: var(--c-dim); }

.tab-bar { display: flex; gap: 4px; margin-bottom: 16px; background: var(--c-surface); border-radius: var(--r-sm); padding: 3px; width: fit-content; }
.tab-btn { padding: 7px 20px; border: none; border-radius: 6px; font-size: 13px; font-weight: 600; font-family: var(--f-ui); color: var(--c-text-2); background: transparent; cursor: pointer; transition: all var(--transition-fast); }
.tab-btn:hover { background: var(--c-hover); }
.tab-btn.active { background: var(--c-card); color: var(--c-text); box-shadow: 0 1px 3px rgba(0,0,0,0.08); }

.field-label { display: block; font-size: 12px; font-weight: 600; color: var(--c-text-2); margin: 14px 0 6px; }
.input-area { width: 100%; padding: 10px 14px; border: 1px solid var(--c-border); border-radius: var(--r-sm); font-family: var(--f-mono); font-size: 12px; resize: vertical; background: var(--c-card); color: var(--c-text); outline: none; transition: border-color var(--transition-fast); }
.input-area:focus { border-color: var(--c-primary); }
.result-area { background: var(--c-surface); }

.params-row { display: flex; gap: 16px; margin-top: 14px; }
.param-item { display: flex; flex-direction: column; }
.param-label { font-size: 11px; font-weight: 600; color: var(--c-dim); margin-bottom: 4px; }
.param-input { width: 90px; padding: 6px 10px; border: 1px solid var(--c-border); border-radius: var(--r-sm); font-size: 13px; font-family: var(--f-ui); background: var(--c-card); color: var(--c-text); }

.btn-row { display: flex; gap: 8px; margin-top: 16px; }
.status-text { font-size: 12px; color: var(--c-text-2); margin-top: 10px; }

.add-to-config { margin-top: 16px; }
.add-btn-row { display: flex; flex-wrap: wrap; gap: 6px; }
.btn-outline-sm {
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
  background: var(--c-card);
  color: var(--c-text);
  cursor: pointer;
  font-family: var(--f-ui);
  transition: all var(--transition-fast);
}
.btn-outline-sm:hover {
  border-color: var(--c-primary);
  color: var(--c-primary);
  background: var(--c-surface);
}
.add-status {
  display: inline-block;
  font-size: 12px;
  margin-top: 8px;
}
.status-ok { color: var(--c-green); }
.status-err { color: var(--c-red); }
</style>
