<template>
  <div class="view-container">
    <div class="view-header">
      <div class="header-row">
        <div>
          <h2>📊 搭建记录</h2>
          <p class="view-desc">搭建统计与数据导出</p>
        </div>
        <div class="header-actions">
          <button class="btn btn-ghost" @click="exportCsv">📥 导出 CSV</button>
          <button class="btn btn-ghost" @click="refresh">🔄 刷新</button>
        </div>
      </div>
    </div>

    <!-- 标签栏 -->
    <div class="tab-bar">
      <button class="tab-btn" :class="{ active: activeTab === 'records' }" @click="activeTab = 'records'">搭建记录</button>
      <button class="tab-btn" :class="{ active: activeTab === 'assign' }" @click="activeTab = 'assign'">分配日志</button>
    </div>

    <!-- 搭建记录 Tab -->
    <template v-if="activeTab === 'records'">

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
      <div class="list-toolbar">
        <span class="toolbar-label">显示范围：</span>
        <select class="days-select" v-model="showDays">
          <option :value="7">7 天</option>
          <option :value="30">30 天</option>
          <option :value="0">全部</option>
        </select>
      </div>
      <div class="list-header">
        <span class="col-date">日期</span>
        <span class="col-num">账户数</span>
        <span class="col-num">项目数</span>
        <span class="col-action">操作</span>
      </div>
      <div class="list-body">
        <div v-if="!filteredRecords.length" class="list-empty">暂无基建记录</div>
        <template v-for="(item, idx) in filteredRecords" :key="item.date">
          <div
            class="list-row"
            :class="{ 'row-today': item.date === today, 'row-alt': idx % 2 === 1 }"
          >
            <span class="col-date" :class="{ 'text-primary': item.date === today }">
              📅 {{ item.date }}{{ item.date === today ? ' (今天)' : '' }}
            </span>
            <span class="col-num text-primary-num">{{ item.accounts }}</span>
            <span class="col-num text-green-num">{{ item.projects }}</span>
            <span class="col-action">
              <button class="btn-detail" @click="toggleDetail(item.date)">
                {{ expandedDate === item.date ? '收起' : '详情' }}
              </button>
            </span>
          </div>
          <!-- 详情面板 -->
          <div v-if="expandedDate === item.date" class="detail-panel">
            <div v-if="detailLoading" class="empty-hint">加载中...</div>
            <template v-else-if="dateDetails.length === 0">
              <div class="empty-hint">无详细记录</div>
            </template>
            <template v-else>
              <!-- 状态筛选 -->
              <div class="detail-toolbar">
                <button
                  v-for="f in statusFilters"
                  :key="f.value"
                  class="filter-btn"
                  :class="{ active: detailStatusFilter === f.value }"
                  @click="detailStatusFilter = f.value; detailPage = 1"
                >{{ f.label }}</button>
                <span class="detail-count">共 {{ filteredDetails.length }} 条</span>
              </div>
              <table class="detail-table">
                <thead><tr><th>时间</th><th>方向</th><th>账户</th><th>剧名</th><th>状态</th><th>备注</th></tr></thead>
                <tbody>
                  <tr v-for="d in pagedDetails" :key="d.timestamp + '_' + d.account_id" :class="'status-' + d.status">
                    <td>{{ formatTime(d.timestamp) }}</td>
                    <td>{{ d.profile }}</td>
                    <td class="mono">{{ d.account_id }}</td>
                    <td>{{ d.drama_name }}</td>
                    <td><span class="status-badge" :class="d.status">{{ statusText(d.status) }}</span></td>
                    <td><span class="detail-message" :title="d.message">{{ d.message }}</span></td>
                  </tr>
                </tbody>
              </table>
              <!-- 分页控件 -->
              <div v-if="detailTotalPages > 1" class="detail-pagination">
                <button class="page-btn" :disabled="detailPage <= 1" @click="detailPage--">‹ 上一页</button>
                <span class="page-info">{{ detailPage }} / {{ detailTotalPages }}</span>
                <button class="page-btn" :disabled="detailPage >= detailTotalPages" @click="detailPage++">下一页 ›</button>
              </div>
            </template>
          </div>
        </template>
      </div>
    </div>

    </template>

    <!-- 分配日志 Tab -->
    <div v-if="activeTab === 'assign'" class="assign-section">
      <!-- 筛选栏 -->
      <div class="assign-toolbar">
        <select v-model="assignDateFilter" class="filter-select" @change="loadAssignLogs">
          <option value="">全部日期</option>
          <option v-for="d in assignDates" :key="d" :value="d">{{ d }}</option>
        </select>
        <select v-model="assignProfileFilter" class="filter-select" @change="loadAssignLogs">
          <option value="">全部方向</option>
          <option value="安卓-每留">安卓-每留</option>
          <option value="安卓-七留">安卓-七留</option>
          <option value="IOS-每留">IOS-每留</option>
          <option value="IOS-七留">IOS-七留</option>
          <option value="安卓-激励每留">安卓-激励每留</option>
          <option value="安卓-激励七留">安卓-激励七留</option>
        </select>
        <span class="assign-summary">共 {{ assignLogs.length }} 条分配记录</span>
      </div>

      <!-- 账户使用统计表 -->
      <div class="card assign-card">
        <div v-if="assignLoading" class="empty-hint">加载中...</div>
        <div v-else-if="!accountUsageList.length" class="empty-hint">暂无分配记录</div>
        <template v-else>
          <table class="assign-table">
            <thead>
              <tr>
                <th>账户名称</th>
                <th>账户 ID</th>
                <th>策略</th>
                <th>累计分配次数</th>
                <th>最近分配日期</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in pagedUsageList" :key="item.account_id">
                <td>{{ item.name || '—' }}</td>
                <td class="mono">{{ item.account_id }}</td>
                <td>
                  <span v-if="item.strategy === '每留'" class="strategy-badge meiliu">每留</span>
                  <span v-else-if="item.strategy === '七留'" class="strategy-badge qiliu">七留</span>
                  <span v-else class="dim">—</span>
                </td>
                <td class="mono count-cell">
                  <span class="count-num">{{ item.count }}</span>
                  <span class="count-label">次</span>
                </td>
                <td class="mono">{{ item.last_date || '—' }}</td>
              </tr>
            </tbody>
          </table>
          <!-- 分页 -->
          <div v-if="usageTotalPages > 1" class="detail-pagination">
            <button class="page-btn" :disabled="usagePage <= 1" @click="usagePage--">‹ 上一页</button>
            <span class="page-info">{{ usagePage }} / {{ usageTotalPages }}</span>
            <button class="page-btn" :disabled="usagePage >= usageTotalPages" @click="usagePage++">下一页 ›</button>
          </div>
        </template>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { getBuildRecords, getBuildDetails, exportBuildCsv, getAssignLogs, getAssignLogDates } from '@/services/api'

// ── Tab ─────────────────────────────────────────────────────────────────────
const activeTab = ref('records')

// ── 记录列表 ──────────────────────────────────────────────────────────────────
const records = ref({})
const showDays = ref(30)

const expandedDate = ref('')
const dateDetails = ref([])
const detailLoading = ref(false)
const detailCache = ref(new Map())

// ── 详情分页 ──────────────────────────────────────────────────────────────────
const detailPage = ref(1)
const detailPageSize = 30

// ── 详情状态筛选 ───────────────────────────────────────────────────────────────
const detailStatusFilter = ref('')
const statusFilters = [
  { value: '', label: '全部' },
  { value: 'success', label: '成功' },
  { value: 'failed', label: '失败' },
  { value: 'skipped', label: '跳过' },
]

// ── 今日 ──────────────────────────────────────────────────────────────────────
const today = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
})

// ── 排序 + 日期范围过滤 ────────────────────────────────────────────────────────
const sortedRecords = computed(() => {
  return Object.entries(records.value)
    .map(([date, data]) => ({ date, accounts: data.accounts || 0, projects: data.projects || 0 }))
    .sort((a, b) => b.date.localeCompare(a.date))
})

const filteredRecords = computed(() => {
  if (!showDays.value) return sortedRecords.value
  const cutoff = new Date()
  cutoff.setDate(cutoff.getDate() - showDays.value + 1)
  const cutoffStr = `${cutoff.getFullYear()}-${String(cutoff.getMonth()+1).padStart(2,'0')}-${String(cutoff.getDate()).padStart(2,'0')}`
  return sortedRecords.value.filter(item => item.date >= cutoffStr)
})

// ── 统计卡片 ──────────────────────────────────────────────────────────────────
const todayAccounts = computed(() => records.value[today.value]?.accounts || 0)
const todayProjects = computed(() => records.value[today.value]?.projects || 0)
const totalProjects = computed(() =>
  Object.values(records.value).reduce((sum, d) => sum + (d.projects || 0), 0)
)

// ── 详情筛选 + 分页 ────────────────────────────────────────────────────────────
const filteredDetails = computed(() => {
  if (!detailStatusFilter.value) return dateDetails.value
  return dateDetails.value.filter(d => d.status === detailStatusFilter.value)
})

const pagedDetails = computed(() => {
  const start = (detailPage.value - 1) * detailPageSize
  return filteredDetails.value.slice(start, start + detailPageSize)
})

const detailTotalPages = computed(() => Math.ceil(filteredDetails.value.length / detailPageSize))

// ── 数据加载 ──────────────────────────────────────────────────────────────────
async function loadRecords() {
  try { records.value = await getBuildRecords() } catch {}
}

async function toggleDetail(date) {
  if (expandedDate.value === date) {
    expandedDate.value = ''
    dateDetails.value = []
    return
  }
  expandedDate.value = date
  detailPage.value = 1
  detailStatusFilter.value = ''

  if (detailCache.value.has(date)) {
    dateDetails.value = detailCache.value.get(date)
    return
  }

  dateDetails.value = []
  detailLoading.value = true
  try {
    const data = await getBuildDetails(date)
    detailCache.value.set(date, data)
    dateDetails.value = data
  } catch {
    dateDetails.value = []
  } finally {
    detailLoading.value = false
  }
}

function refresh() {
  detailCache.value.clear()
  loadRecords()
}

// ── CSV 导出 ──────────────────────────────────────────────────────────────────
async function exportCsv() {
  try {
    const res = await exportBuildCsv()
    if (!res?.ok || !res.csv) return
    const blob = new Blob(['﻿' + res.csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `搭建详情_${today.value}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch {}
}

// ── 工具函数 ──────────────────────────────────────────────────────────────────
function formatTime(ts) {
  if (!ts) return ''
  const t = ts.includes('T') ? ts.split('T')[1] : ts
  return t ? t.substring(0, 8) : ''
}

function statusText(status) {
  const map = { success: '成功', failed: '失败', skipped: '跳过' }
  return map[status] || status
}

onMounted(loadRecords)

// ── 分配日志 ─────────────────────────────────────────────────────────────────
const assignLogs = ref([])
const assignDates = ref([])
const assignDateFilter = ref('')
const assignProfileFilter = ref('')
const assignLoading = ref(false)
const usageCounts = ref({})
const accountMap = ref({})
const usagePage = ref(1)
const usagePageSize = 30

// 每个账户的使用统计列表（合并 accountMap + usageCounts + 最近日期）
const accountUsageList = computed(() => {
  // 从日志中提取每个账户的最近分配日期
  const lastDateMap = {}
  for (const log of assignLogs.value) {
    for (const aid of (log.all_account_ids || [])) {
      if (!lastDateMap[aid] || log.date > lastDateMap[aid]) {
        lastDateMap[aid] = log.date
      }
    }
  }

  // 合并所有有使用记录的账户
  const allIds = new Set([...Object.keys(usageCounts.value), ...Object.keys(lastDateMap)])
  const list = []
  for (const aid of allIds) {
    const info = accountMap.value[aid] || {}
    list.push({
      account_id: aid,
      name: info.name || '',
      strategy: info.strategy || '',
      platform: info.platform || '',
      count: usageCounts.value[aid] || 0,
      last_date: lastDateMap[aid] || '',
    })
  }
  // 按分配次数降序，再按最近日期降序
  list.sort((a, b) => b.count - a.count || b.last_date.localeCompare(a.last_date))
  return list
})

const pagedUsageList = computed(() => {
  const start = (usagePage.value - 1) * usagePageSize
  return accountUsageList.value.slice(start, start + usagePageSize)
})

const usageTotalPages = computed(() => Math.max(1, Math.ceil(accountUsageList.value.length / usagePageSize)))

async function loadAssignLogs() {
  assignLoading.value = true
  usagePage.value = 1
  try {
    const res = await getAssignLogs(assignDateFilter.value, assignProfileFilter.value)
    if (res?.ok) {
      assignLogs.value = res.logs || []
      usageCounts.value = res.usage_counts || {}
      accountMap.value = res.account_map || {}
    }
  } catch (e) {
    console.error('加载分配日志失败:', e)
  } finally {
    assignLoading.value = false
  }
}

async function loadAssignDates() {
  try {
    const res = await getAssignLogDates()
    if (res?.ok) {
      assignDates.value = res.dates || []
    }
  } catch {}
}

// 切换到分配日志 tab 时懒加载数据
watch(activeTab, (val) => {
  if (val === 'assign' && !assignLogs.value.length) {
    loadAssignDates()
    loadAssignLogs()
  }
})
</script>

<style scoped>
.view-container { max-width: 800px; }
.view-header { margin-bottom: 16px; }
.view-header h2 { font-size: 20px; font-weight: 700; margin-bottom: 4px; }
.view-desc { font-size: 13px; color: var(--c-dim); }
.header-row { display: flex; justify-content: space-between; align-items: flex-start; }
.header-actions { display: flex; gap: 8px; }

/* ── 标签栏 ── */
.tab-bar { display: flex; gap: 4px; margin-bottom: 16px; border-bottom: 1px solid var(--c-border); padding-bottom: 0; }
.tab-btn { background: none; border: none; border-bottom: 2px solid transparent; padding: 6px 16px; font-size: 13px; font-weight: 600; color: var(--c-dim); cursor: pointer; transition: all var(--transition-fast); margin-bottom: -1px; }
.tab-btn:hover { color: var(--c-text); }
.tab-btn.active { color: var(--c-primary); border-bottom-color: var(--c-primary); }

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

/* ── 列表工具栏 ── */
.list-toolbar { display: flex; align-items: center; gap: 8px; padding: 8px 18px; border-bottom: 1px solid var(--c-border-s); font-size: 12px; color: var(--c-dim); }
.toolbar-label { font-weight: 600; }
.days-select { font-size: 12px; padding: 2px 6px; border: 1px solid var(--c-border); border-radius: 4px; background: var(--c-surface); color: var(--c-text); cursor: pointer; }

.list-card { padding: 0; overflow: hidden; }
.list-header { display: flex; padding: 10px 18px; border-bottom: 1px solid var(--c-border); font-size: 11px; font-weight: 700; color: var(--c-dim); text-transform: uppercase; }
.list-body { max-height: 480px; overflow-y: auto; }
.list-row { display: flex; align-items: center; padding: 10px 18px; font-size: 13px; transition: background var(--transition-fast); }
.list-row:hover { background: var(--c-hover); }
.row-alt { background: var(--c-surface); }
.row-today { font-weight: 600; }
.col-date { flex: 1; font-family: var(--f-mono); font-weight: 600; color: var(--c-text); }
.col-num { width: 80px; text-align: center; font-family: var(--f-mono); font-weight: 700; }
.col-action { width: 60px; text-align: center; }
.text-primary { color: var(--c-primary); font-weight: 700; }
.text-primary-num { color: var(--c-primary); }
.text-green-num { color: var(--c-green); }
.list-empty { padding: 40px; text-align: center; color: var(--c-dim); font-size: 13px; }

.btn-detail { background: none; border: 1px solid var(--c-border); border-radius: 4px; padding: 2px 10px; font-size: 12px; color: var(--c-primary); cursor: pointer; transition: all var(--transition-fast); }
.btn-detail:hover { background: var(--c-primary); color: var(--c-bg); border-color: var(--c-primary); }

.detail-panel { padding: 12px 18px; border-top: 1px solid var(--c-border-s); background: var(--c-surface); }

/* ── 详情工具栏 ── */
.detail-toolbar { display: flex; align-items: center; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; }
.filter-btn { background: none; border: 1px solid var(--c-border); border-radius: 4px; padding: 2px 10px; font-size: 11px; color: var(--c-dim); cursor: pointer; transition: all var(--transition-fast); }
.filter-btn:hover { border-color: var(--c-primary); color: var(--c-primary); }
.filter-btn.active { background: var(--c-primary); color: var(--c-bg); border-color: var(--c-primary); font-weight: 600; }
.detail-count { margin-left: auto; font-size: 11px; color: var(--c-dim); }

.detail-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.detail-table th { text-align: left; padding: 6px 8px; font-weight: 600; color: var(--c-dim); border-bottom: 1px solid var(--c-border); }
.detail-table td { padding: 6px 8px; border-bottom: 1px solid var(--c-border-s); }
.status-badge { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.status-badge.success { background: var(--c-status-success-bg); color: var(--c-status-success-text); }
.status-badge.failed { background: var(--c-status-error-bg); color: var(--c-status-error-text); }
.status-badge.skipped { background: var(--c-status-warn-bg); color: var(--c-status-warn-text); }
.mono { font-family: var(--f-mono); }
.empty-hint { padding: 20px; text-align: center; color: var(--c-dim); font-size: 13px; }

/* ── 备注截断 ── */
.detail-message {
  display: block;
  max-width: 250px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

/* ── 分页 ── */
.detail-pagination { display: flex; align-items: center; justify-content: center; gap: 12px; padding: 8px 0 2px; }
.page-btn { background: none; border: 1px solid var(--c-border); border-radius: 4px; padding: 3px 12px; font-size: 12px; color: var(--c-primary); cursor: pointer; transition: all var(--transition-fast); }
.page-btn:hover:not(:disabled) { background: var(--c-primary); color: var(--c-bg); border-color: var(--c-primary); }
.page-btn:disabled { opacity: 0.4; cursor: default; }
.page-info { font-size: 12px; color: var(--c-dim); font-family: var(--f-mono); }

/* ── 分配日志占位 ── */
.assign-placeholder { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 80px 20px; gap: 12px; }
.placeholder-icon { font-size: 48px; }
.placeholder-title { font-size: 18px; font-weight: 700; color: var(--c-text); }
.placeholder-desc { font-size: 13px; color: var(--c-dim); }

/* ── 分配日志 ── */
.assign-section { margin-top: 4px; }
.assign-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.filter-select { font-size: 12px; padding: 4px 8px; border: 1px solid var(--c-border); border-radius: 4px; background: var(--c-surface); color: var(--c-text); cursor: pointer; }
.assign-summary { margin-left: auto; font-size: 12px; color: var(--c-dim); }
.assign-card { padding: 0; overflow: hidden; }
.assign-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.assign-table th { text-align: left; padding: 8px 10px; font-weight: 600; color: var(--c-dim); border-bottom: 1px solid var(--c-border); font-size: 11px; }
.assign-table td { padding: 8px 10px; border-bottom: 1px solid var(--c-border-s); }
.assign-table tr:hover { background: var(--c-hover); }
.strategy-badge { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.strategy-badge.meiliu { background: #e8f5e9; color: #2e7d32; }
.strategy-badge.qiliu { background: #e3f2fd; color: #1565c0; }
.count-cell { font-weight: 700; }
.count-num { color: var(--c-primary); font-size: 14px; }
.count-label { color: var(--c-dim); font-size: 11px; margin-left: 2px; }
.dim { color: var(--c-dim); }
</style>
