<template>
  <div class="view-container">
    <div class="view-header">
      <div class="header-row">
        <div>
          <h2>📚 素材历史</h2>
          <p class="view-desc">查看最近使用的素材记录</p>
        </div>
        <div class="header-actions">
          <button class="btn btn-ghost" @click="loadHistory">🔄 刷新</button>
          <button class="btn btn-ghost" @click="clearHistory">🗑 清空记录</button>
        </div>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stat-row">
      <div class="stat-card">
        <div class="stat-value" style="color: var(--c-primary);">{{ history.length }}</div>
        <div class="stat-label">已使用素材</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--c-green);">{{ todayCount }}</div>
        <div class="stat-label">今日新增</div>
      </div>
    </div>

    <!-- 确认弹窗 -->
    <ConfirmDialog
      ref="confirmDialog"
      title="确认清空"
      message="确定要清空所有素材历史记录吗？此操作不可恢复。"
      confirm-text="清空"
      :is-danger="true"
    />

    <!-- 列表 -->
    <div class="card list-card">
      <div class="list-header">
        <span class="col-date">日期</span>
        <span class="col-name">素材名称</span>
      </div>
      <div class="list-body">
        <div v-if="!history.length" class="list-empty">暂无素材历史记录</div>
        <div
          v-for="(item, idx) in history"
          :key="idx"
          class="list-row"
          :class="{ 'row-today': item.date === todayTag, 'row-alt': idx % 2 === 1 }"
        >
          <span class="col-date" :class="{ 'text-primary': item.date === todayTag }">{{ item.date }}</span>
          <span class="col-name">{{ item.name }}</span>
          <button class="row-btn" @click="copyName(item.name)" title="复制">📋</button>
          <button class="row-btn" @click="deleteItem(idx)" title="删除">🗑️</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { getMaterialHistory, deleteMaterialHistory, clearMaterialHistory } from '@/services/api'

const confirmDialog = ref(null)

const history = ref([])

const todayTag = computed(() => {
  const d = new Date()
  return String(d.getMonth() + 1).padStart(2, '0') + String(d.getDate()).padStart(2, '0')
})

const todayCount = computed(() => history.value.filter(h => h.date === todayTag.value).length)

async function loadHistory() {
  try { history.value = await getMaterialHistory() } catch {}
}

async function deleteItem(index) {
  await deleteMaterialHistory(index)
  await loadHistory()
}

async function clearHistory() {
  const confirmed = await confirmDialog.value.show()
  if (!confirmed) return
  const res = await clearMaterialHistory()
  if (res.ok) {
    history.value = []
  }
}

function copyName(name) {
  navigator.clipboard.writeText(name)
}

onMounted(loadHistory)
</script>

<style scoped>
.view-container { max-width: 800px; }
.view-header { margin-bottom: 16px; }
.view-header h2 { font-size: 20px; font-weight: 700; margin-bottom: 4px; }
.view-desc { font-size: 13px; color: var(--c-dim); }
.header-row { display: flex; justify-content: space-between; align-items: flex-start; }
.header-actions { display: flex; gap: 8px; }

.stat-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }
.stat-card { background: var(--c-card); border: 1px solid var(--c-border); border-radius: var(--r-lg); padding: 18px 20px; text-align: center; }
.stat-value { font-size: 28px; font-weight: 800; font-family: var(--f-mono); }
.stat-label { font-size: 12px; color: var(--c-dim); margin-top: 4px; }

.list-card { padding: 0; overflow: hidden; }
.list-header { display: flex; padding: 10px 18px; border-bottom: 1px solid var(--c-border); font-size: 11px; font-weight: 700; color: var(--c-dim); text-transform: uppercase; }
.list-body { max-height: 480px; overflow-y: auto; }
.list-row { display: flex; align-items: center; padding: 8px 18px; font-size: 13px; transition: background var(--transition-fast); }
.list-row:hover { background: var(--c-hover); }
.row-alt { background: var(--c-surface); }
.row-alt:hover { background: var(--c-hover); }
.row-today { font-weight: 600; }
.col-date { width: 80px; flex-shrink: 0; font-family: var(--f-mono); font-weight: 600; font-size: 12px; color: var(--c-text-2); }
.col-name { flex: 1; color: var(--c-text); }
.text-primary { color: var(--c-primary); font-weight: 700; }
.row-btn { background: none; border: none; cursor: pointer; opacity: 0.3; padding: 2px 4px; font-size: 12px; transition: opacity var(--transition-fast); }
.list-row:hover .row-btn,
.list-row:focus-within .row-btn { opacity: 0.6; }
.row-btn:hover { opacity: 1 !important; }
.row-btn:focus, .row-btn:focus-visible { opacity: 1; outline: 2px solid var(--c-primary); outline-offset: 2px; }
.list-empty { padding: 40px; text-align: center; color: var(--c-dim); font-size: 13px; }
</style>
