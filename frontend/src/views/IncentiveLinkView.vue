<template>
  <div class="view-container">
    <div class="view-header">
      <h2>🔗 激励链接分配</h2>
      <p class="view-desc">分配激励链接到各账户组</p>
    </div>
    <div class="card">
      <label class="field-label">原始数据（Tab分隔：组标签 + 点击链接 + 展示链接 + 播放链接）</label>
      <textarea v-model="rawData" class="input-area" rows="5" placeholder="日期-组1-标签&#9;点击链接&#9;展示链接&#9;播放链接"></textarea>

      <label class="field-label">账户 ID（每行一个，支持 "ID\\t\\t短剧组XX" 格式）</label>
      <textarea v-model="accountIds" class="input-area" rows="5" placeholder="账户ID，每行一个"></textarea>

      <label class="field-label">素材 ID（可选，空格/换行分隔）</label>
      <textarea v-model="materialIds" class="input-area" rows="3" placeholder="素材ID"></textarea>

      <div class="params-row">
        <div class="param-item">
          <label class="param-label">每组账户数</label>
          <input v-model.number="idsPerGroup" type="number" class="param-input" min="1" />
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
        <button class="btn btn-primary" @click="process">🚀 开始分配</button>
        <button class="btn btn-ghost" @click="clearAll">🗑 清空</button>
      </div>

      <p v-if="status" class="status-text">{{ status }}</p>

      <label v-if="result" class="field-label">分配结果</label>
      <textarea v-if="result" :value="result" class="input-area result-area" rows="12" readonly></textarea>

      <div v-if="result" class="btn-row" style="margin-top: 8px;">
        <button class="btn btn-ghost" @click="copyResult">📋 复制结果</button>
      </div>

      <div v-if="result" class="add-to-config">
        <label class="field-label">添加到配置</label>
        <div class="add-btn-row">
          <button v-for="pk in incentiveProfileKeys" :key="pk"
                  class="btn btn-outline-sm"
                  @click="addToProfile(pk)">
            ➕ {{ pk }}
          </button>
        </div>
        <span v-if="addStatus" class="add-status" :class="addStatus.startsWith('✅') ? 'status-ok' : 'status-err'">{{ addStatus }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { processIncentiveLinks, addIncentiveResultToProfile } from '@/services/api'
import { useUiStore } from '@/stores/ui'

const uiStore = useUiStore()

const rawData = ref(localStorage.getItem('incentiveLink_rawData') || '')
const accountIds = ref(localStorage.getItem('incentiveLink_accountIds') || '')
const materialIds = ref(localStorage.getItem('incentiveLink_materialIds') || '')
const idsPerGroup = ref(parseInt(localStorage.getItem('incentiveLink_idsPerGroup')) || 6)
const _savedSpacing = localStorage.getItem('incentiveLink_spacing')
const spacing = ref(_savedSpacing !== null ? parseInt(_savedSpacing) : 1)

watch(rawData, (v) => localStorage.setItem('incentiveLink_rawData', v))
watch(accountIds, (v) => localStorage.setItem('incentiveLink_accountIds', v))
watch(materialIds, (v) => localStorage.setItem('incentiveLink_materialIds', v))
watch(idsPerGroup, (v) => { if (Number.isFinite(v) && v > 0) localStorage.setItem('incentiveLink_idsPerGroup', v) })
watch(spacing, (v) => { if (Number.isFinite(v) && v >= 0) localStorage.setItem('incentiveLink_spacing', v) })
const result = ref('')
const status = ref('')

async function process() {
  status.value = '处理中...'
  try {
    const res = await processIncentiveLinks({
      raw_data: rawData.value,
      account_ids: accountIds.value,
      material_ids: materialIds.value,
      ids_per_group: idsPerGroup.value,
      spacing: spacing.value,
    })
    if (res.ok) {
      result.value = res.result
      status.value = res.summary || '分配完成'
    } else {
      status.value = '❌ ' + (res.error || '处理失败')
    }
  } catch (e) {
    status.value = '❌ ' + e.message
  }
}

function clearAll() {
  rawData.value = ''; accountIds.value = ''; materialIds.value = ''
  result.value = ''; status.value = ''
  localStorage.removeItem('incentiveLink_rawData')
  localStorage.removeItem('incentiveLink_accountIds')
  localStorage.removeItem('incentiveLink_materialIds')
}

function copyResult() {
  navigator.clipboard.writeText(result.value)
  status.value = '✅ 已复制到剪贴板'
}

const incentiveProfileKeys = ['安卓-激励每留', '安卓-激励七留']
const addStatus = ref('')

async function addToProfile(profileKey) {
  if (!result.value) return
  try {
    const res = await addIncentiveResultToProfile(profileKey, result.value)
    addStatus.value = res.ok
      ? `✅ 已添加 ${res.count} 组到「${profileKey}」`
      : `❌ ${res.error}`
  } catch (e) {
    addStatus.value = `❌ ${e.message}`
  }
  setTimeout(() => addStatus.value = '', 4000)
}

onMounted(() => {
  const pending = uiStore.consumePendingLinkData()
  if (pending) {
    rawData.value = pending.rawData
  }
})
</script>

<style scoped>
.view-container { max-width: 960px; }
.view-header { margin-bottom: 16px; }
.view-header h2 { font-size: 20px; font-weight: 700; margin-bottom: 4px; }
.view-desc { font-size: 13px; color: var(--c-dim); }
.field-label { display: block; font-size: 12px; font-weight: 600; color: var(--c-text-2); margin: 14px 0 6px; }
.input-area { width: 100%; padding: 10px 14px; border: 1px solid var(--c-border); border-radius: var(--r-sm); font-family: var(--f-mono); font-size: 12px; resize: vertical; background: #fff; color: var(--c-text); outline: none; }
.input-area:focus { border-color: var(--c-primary); }
.result-area { background: var(--c-surface); }
.params-row { display: flex; gap: 16px; margin-top: 14px; }
.param-item { display: flex; flex-direction: column; }
.param-label { font-size: 11px; font-weight: 600; color: var(--c-dim); margin-bottom: 4px; }
.param-input { width: 90px; padding: 6px 10px; border: 1px solid var(--c-border); border-radius: var(--r-sm); font-size: 13px; font-family: var(--f-ui); background: #fff; }
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
