<template>
  <div class="view-container">
    <div class="view-header">
      <div class="header-row">
        <div>
          <h2>📊 搭建记录</h2>
          <p class="view-desc">搭建统计与数据导出</p>
        </div>
        <div class="header-actions">
          <button class="btn btn-ghost" @click="loadRecords">🔄 刷新</button>
        </div>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stat-row">
      <div class="stat-card">
        <div class="stat-value" style="color: var(--c-primary);">{{ todayAccounts }}</div>
        <div class="stat-label">今日账户</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--c-green);">{{ todayProjects }}</div>
        <div class="stat-label">今日项目</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: var(--c-orange);">{{ totalProjects }}</div>
        <div class="stat-label">累计项目</div>
      </div>
    </div>

    <!-- 列表 -->
    <div class="card list-card">
      <div class="list-header">
        <span class="col-date">日期</span>
        <span class="col-num">账户数</span>
        <span class="col-num">项目数</span>
      </div>
      <div class="list-body">
        <div v-if="!sortedRecords.length" class="list-empty">暂无基建记录</div>
        <div
          v-for="(item, idx) in sortedRecords"
          :key="item.date"
          class="list-row"
          :class="{ 'row-today': item.date === today, 'row-alt': idx % 2 === 1 }"
        >
          <span class="col-date" :class="{ 'text-primary': item.date === today }">
            📅 {{ item.date }}{{ item.date === today ? ' (今天)' : '' }}
          </span>
          <span class="col-num text-primary-num">{{ item.accounts }}</span>
          <span class="col-num text-green-num">{{ item.projects }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getBuildRecords } from '@/services/api'

const records = ref({})

const today = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
})

const sortedRecords = computed(() => {
  return Object.entries(records.value)
    .map(([date, data]) => ({ date, accounts: data.accounts || 0, projects: data.projects || 0 }))
    .sort((a, b) => b.date.localeCompare(a.date))
})

const todayAccounts = computed(() => records.value[today.value]?.accounts || 0)
const todayProjects = computed(() => records.value[today.value]?.projects || 0)
const totalProjects = computed(() =>
  Object.values(records.value).reduce((sum, d) => sum + (d.projects || 0), 0)
)

async function loadRecords() {
  try { records.value = await getBuildRecords() } catch {}
}

onMounted(loadRecords)
</script>

<style scoped>
.view-container { max-width: 800px; }
.view-header { margin-bottom: 16px; }
.view-header h2 { font-size: 20px; font-weight: 700; margin-bottom: 4px; }
.view-desc { font-size: 13px; color: var(--c-dim); }
.header-row { display: flex; justify-content: space-between; align-items: flex-start; }
.header-actions { display: flex; gap: 8px; }

.stat-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 16px; }

@media (max-width: 1024px) {
  .stat-row { grid-template-columns: 1fr 1fr; }
}

@media (max-width: 600px) {
  .stat-row { grid-template-columns: 1fr; }
}
.stat-card { background: var(--c-card); border: 1px solid var(--c-border); border-radius: var(--r-lg); padding: 18px 20px; text-align: center; }
.stat-value { font-size: 28px; font-weight: 800; font-family: var(--f-mono); }
.stat-label { font-size: 12px; color: var(--c-dim); margin-top: 4px; }

.list-card { padding: 0; overflow: hidden; }
.list-header { display: flex; padding: 10px 18px; border-bottom: 1px solid var(--c-border); font-size: 11px; font-weight: 700; color: var(--c-dim); text-transform: uppercase; }
.list-body { max-height: 480px; overflow-y: auto; }
.list-row { display: flex; align-items: center; padding: 10px 18px; font-size: 13px; transition: background var(--transition-fast); }
.list-row:hover { background: var(--c-hover); }
.row-alt { background: var(--c-surface); }
.row-today { font-weight: 600; }
.col-date { flex: 1; font-family: var(--f-mono); font-weight: 600; color: var(--c-text); }
.col-num { width: 80px; text-align: center; font-family: var(--f-mono); font-weight: 700; }
.text-primary { color: var(--c-primary); font-weight: 700; }
.text-primary-num { color: var(--c-primary); }
.text-green-num { color: var(--c-green); }
.list-empty { padding: 40px; text-align: center; color: var(--c-dim); font-size: 13px; }
</style>
