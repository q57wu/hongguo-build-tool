<template>
  <div class="ap-page">
    <div class="ap-container">
      <!-- Header -->
      <div class="ap-header">
        <div class="ap-header-left">
          <h2 class="ap-title">🗂 {{ poolMode === 'incentive' ? '激励账户池' : '账户池' }}</h2>
          <p class="ap-desc">{{ poolMode === 'incentive' ? '管理激励推广专用的投放账户和素材账户' : '统一管理投放账户和素材账户，告别重复粘贴' }}</p>
        </div>
        <div class="ap-header-actions">
          <button class="ap-btn ap-btn-ghost" @click="showBatchImport = true">📋 批量导入</button>
          <button class="ap-btn ap-btn-ghost" @click="doImportFromConfig">📥 从配置导入</button>
          <button class="ap-btn ap-btn-primary" @click="openAddDialog">➕ 添加账户</button>
        </div>
      </div>

      <!-- Pool Mode Switcher -->
      <div class="ap-pool-switcher">
        <button
          class="ap-pool-btn"
          :class="{ active: poolMode === 'normal' }"
          @click="switchPoolMode('normal')"
        >📦 单本账户池</button>
        <button
          class="ap-pool-btn"
          :class="{ active: poolMode === 'incentive' }"
          @click="switchPoolMode('incentive')"
        >⚡ 激励账户池</button>
      </div>

      <!-- Tab Switcher -->
      <div class="ap-tab-bar">
        <button class="ap-tab" :class="{ active: activeTab === 'pool' }" @click="activeTab = 'pool'">🗂 账户池</button>
        <button class="ap-tab" :class="{ active: activeTab === 'logs' }" @click="switchToLogs">📝 分配日志</button>
      </div>

      <div v-if="activeTab === 'pool'">
      <!-- Stats Bar -->
      <div class="ap-stats-bar">
        <div class="ap-stat-item">
          <span class="ap-stat-value">{{ stats.total || 0 }}</span>
          <span class="ap-stat-label">总账户</span>
        </div>
        <div class="ap-stat-item">
          <span class="ap-stat-value ap-stat-media">{{ stats.media || 0 }}</span>
          <span class="ap-stat-label">投放账户</span>
        </div>
        <div class="ap-stat-item">
          <span class="ap-stat-value ap-stat-material">{{ stats.material || 0 }}</span>
          <span class="ap-stat-label">素材账户</span>
        </div>
        <div class="ap-stat-item">
          <span class="ap-stat-value ap-stat-ios">{{ stats.ios || 0 }}</span>
          <span class="ap-stat-label">IOS</span>
        </div>
        <div class="ap-stat-item">
          <span class="ap-stat-value ap-stat-android">{{ stats.android || 0 }}</span>
          <span class="ap-stat-label">安卓</span>
        </div>
        <div class="ap-stat-item">
          <span class="ap-stat-value ap-stat-rta">{{ stats.rta_set || 0 }}</span>
          <span class="ap-stat-label">已设RTA</span>
        </div>
      </div>

      <!-- Filter Bar -->
      <div class="ap-filter-bar">
        <div class="ap-filter-row-top">
          <div class="ap-type-tabs">
            <button
              v-for="tab in typeTabs"
              :key="tab.value"
              class="ap-type-tab"
              :class="{ active: filterType === tab.value }"
              @click="filterType = tab.value; onFilterChange()"
            >{{ tab.label }}</button>
          </div>
          <div class="ap-filter-controls">
            <select v-model="filterPlatform" class="ap-filter-select" @change="onFilterChange">
              <option value="">全部平台</option>
              <option value="IOS">IOS</option>
              <option value="安卓">安卓</option>
            </select>
            <select v-model="filterStrategy" class="ap-filter-select" @change="onFilterChange">
              <option value="">全部策略</option>
              <template v-if="poolMode === 'incentive'">
                <option value="激励每留">激励每留</option>
                <option value="激励七留">激励七留</option>
              </template>
              <template v-else>
                <option value="每留">每留</option>
                <option value="七留">七留</option>
              </template>
            </select>
            <select v-model="filterStatus" class="ap-filter-select" @change="onFilterChange">
              <option value="">全部状态</option>
              <option value="已设置">已设置</option>
            </select>
            <select v-if="allTags.length" v-model="filterTag" class="ap-filter-select" @change="onFilterChange">
              <option value="">全部标签</option>
              <option v-for="t in allTags" :key="t" :value="t">{{ t }}</option>
            </select>
            <input
              v-model="searchKeyword"
              class="ap-filter-input"
              placeholder="搜索账户ID / 名称 / 备注…"
              @input="onSearchDebounced"
            />
          </div>
        </div>
      </div>

      <!-- Bulk action bar (sticky top) -->
      <div v-if="accounts.length > 0" class="ap-bulk-top-bar">
        <div class="ap-bulk-top-left">
          <label class="ap-check-label">
            <input type="checkbox" v-model="selectAll" @change="toggleSelectAll" />
            <span>全选 ({{ accounts.length }})</span>
          </label>
          <span v-if="selectedIds.size > 0" class="ap-selected-count">已选 {{ selectedIds.size }} 项</span>
        </div>
        <div class="ap-bulk-top-right">
          <button v-if="selectedIds.size > 0" class="ap-btn ap-btn-sm ap-btn-danger" @click="deleteSelected">🗑 批量删除</button>
        </div>
      </div>

      <!-- Account Table -->
      <div class="ap-card ap-table-wrap">
        <div v-if="loading" class="ap-empty-hint">加载中…</div>
        <div v-else-if="!accounts.length" class="ap-empty-hint">
          {{ (searchKeyword || filterType || filterTag || filterPlatform || filterStrategy || filterStatus) ? '无匹配结果' : '暂无账户，点击右上角添加' }}
        </div>
        <table v-else class="ap-table">
          <thead>
            <tr>
              <th class="ap-col-check">
                <input type="checkbox" v-model="selectAll" @change="toggleSelectAll" />
              </th>
              <th>账户 ID</th>
              <th>账户名称</th>
              <th>策略</th>
              <th>标签</th>
              <th>最后使用</th>
              <th class="ap-col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="acc in pagedAccounts" :key="acc.id" :class="{ 'ap-row-selected': selectedIds.has(acc.id) }">
              <td class="ap-col-check">
                <input type="checkbox" :checked="selectedIds.has(acc.id)" @change="toggleSelect(acc.id)" />
              </td>
              <td class="ap-col-id">{{ acc.account_id }}</td>
              <td>{{ acc.name || '—' }}</td>
              <td>
                <span v-if="acc.strategy === '每留' || acc.strategy === '激励每留'" class="ap-badge ap-badge-meiliu">{{ acc.strategy }}</span>
                <span v-else-if="acc.strategy === '七留' || acc.strategy === '激励七留'" class="ap-badge ap-badge-qiliu">{{ acc.strategy }}</span>
                <span v-else class="ap-dim">—</span>
              </td>
              <td>
                <span v-for="tag in (acc.tags || [])" :key="tag" class="ap-tag-chip">{{ tag }}</span>
                <span v-if="!(acc.tags && acc.tags.length)" class="ap-dim">—</span>
              </td>
              <td class="ap-col-time">{{ acc.last_used || '—' }}</td>
              <td class="ap-col-actions">
                <button class="ap-btn-icon" title="编辑" @click="openEditDialog(acc)">✏️</button>
                <button class="ap-btn-icon ap-btn-icon-danger" title="删除" @click="deleteSingle(acc)">🗑</button>
              </td>
            </tr>
          </tbody>
        </table>
        <!-- Pagination -->
        <div v-if="totalCount > pageSize" class="ap-pagination">
          <button class="ap-page-btn" :disabled="currentPage <= 1" @click="currentPage = 1; loadData()">首页</button>
          <button class="ap-page-btn" :disabled="currentPage <= 1" @click="currentPage--; loadData()">上一页</button>
          <span class="ap-page-info">
            第 {{ currentPage }} / {{ totalPages }} 页
            <span class="ap-page-total">（共 {{ totalCount }} 条）</span>
          </span>
          <button class="ap-page-btn" :disabled="currentPage >= totalPages" @click="currentPage++; loadData()">下一页</button>
          <button class="ap-page-btn" :disabled="currentPage >= totalPages" @click="currentPage = totalPages; loadData()">末页</button>
          <select v-model.number="pageSize" class="ap-page-size-select" @change="currentPage = 1; loadData()">
            <option :value="30">30条/页</option>
            <option :value="50">50条/页</option>
            <option :value="100">100条/页</option>
            <option :value="200">200条/页</option>
          </select>
        </div>
      </div>

      <!-- Add/Edit Dialog -->
      <div v-if="showFormDialog" class="ap-modal-overlay" @click.self="showFormDialog = false">
        <div class="ap-modal-box">
          <h3>{{ editingId ? '编辑账户' : '添加账户' }}</h3>
          <div class="ap-form-field">
            <label>账户 ID <span class="ap-required">*</span></label>
            <input v-model="form.account_id" class="ap-text-input ap-wide" placeholder="输入账户ID" :disabled="!!editingId" />
          </div>
          <div class="ap-form-field">
            <label>类型 <span class="ap-required">*</span></label>
            <select v-model="form.type" class="ap-text-input ap-wide" :disabled="!!editingId">
              <option value="media">投放账户</option>
              <option value="material">素材账户</option>
            </select>
          </div>
          <div class="ap-form-field">
            <label>名称</label>
            <input v-model="form.name" class="ap-text-input ap-wide" placeholder="可选，方便识别" />
          </div>
          <div class="ap-form-field">
            <label>平台</label>
            <select v-model="form.platform" class="ap-text-input ap-wide">
              <option value="">请选择</option>
              <option value="IOS">IOS</option>
              <option value="安卓">安卓</option>
            </select>
          </div>
          <div class="ap-form-field">
            <label>分组</label>
            <input v-model="form.group_name" class="ap-text-input ap-wide" placeholder="可选分组名称" />
          </div>
          <div class="ap-form-field">
            <label>RTA状态</label>
            <select v-model="form.status" class="ap-text-input ap-wide">
              <option value="">未设置</option>
              <option value="已设置">已设置</option>
            </select>
          </div>
          <div class="ap-form-field">
            <label>策略</label>
            <select v-model="form.strategy" class="ap-text-input ap-wide">
              <option value="">请选择</option>
              <template v-if="poolMode === 'incentive'">
                <option value="激励每留">激励每留</option>
                <option value="激励七留">激励七留</option>
              </template>
              <template v-else>
                <option value="每留">每留</option>
                <option value="七留">七留</option>
              </template>
            </select>
          </div>
          <div class="ap-form-field">
            <label>标签</label>
            <input v-model="form.tags_input" class="ap-text-input ap-wide" placeholder="逗号分隔，如：安卓-每留,重点" />
          </div>
          <div class="ap-form-field">
            <label>备注</label>
            <input v-model="form.remark" class="ap-text-input ap-wide" placeholder="可选备注" />
          </div>
          <div class="ap-modal-actions">
            <button class="ap-btn ap-btn-ghost" @click="showFormDialog = false">取消</button>
            <button class="ap-btn ap-btn-primary" @click="submitForm">{{ editingId ? '保存' : '添加' }}</button>
          </div>
        </div>
      </div>

      <!-- Batch Import Dialog -->
      <div v-if="showBatchImport" class="ap-modal-overlay" @click.self="showBatchImport = false">
        <div class="ap-modal-box ap-modal-wide">
          <h3>📋 批量导入账户</h3>
          <p class="ap-batch-hint">粘贴从账户管理系统复制的 Tab 分隔数据，格式：账户名 → 账户ID → 负责人 → 分组 → RTA状态 → (空) → 策略</p>
          <div class="ap-form-field">
            <label>账户类型</label>
            <select v-model="batchType" class="ap-text-input ap-wide">
              <option value="media">投放账户</option>
              <option value="material">素材账户</option>
            </select>
          </div>
          <div class="ap-form-field">
            <label>标签（可选）</label>
            <input v-model="batchTags" class="ap-text-input ap-wide" placeholder="逗号分隔，如：安卓-每留,重点" />
          </div>
          <div class="ap-form-field">
            <label>粘贴原始数据</label>
            <textarea v-model="batchText" class="ap-input-area" rows="12" placeholder="粘贴 Tab 分隔的账户数据，每行一条记录"></textarea>
          </div>
          <div class="ap-modal-actions">
            <button class="ap-btn ap-btn-ghost" @click="showBatchImport = false">取消</button>
            <button class="ap-btn ap-btn-primary" @click="submitBatch">导入</button>
          </div>
        </div>
      </div>

      </div><!-- end v-show pool -->

      <!-- Assign Log Panel -->
      <div v-if="activeTab === 'logs'" class="ap-log-panel">
        <div class="ap-log-filters">
          <select v-model="logDateFilter" class="ap-filter-select" @change="loadLogs">
            <option value="">全部日期</option>
            <option v-for="d in logDates" :key="d" :value="d">{{ d }}</option>
          </select>
          <select v-model="logProfileFilter" class="ap-filter-select" @change="loadLogs">
            <option value="">全部配置</option>
            <option value="安卓-每留">安卓-每留</option>
            <option value="安卓-七留">安卓-七留</option>
            <option value="IOS-每留">IOS-每留</option>
            <option value="IOS-七留">IOS-七留</option>
            <option value="安卓-激励每留">安卓-激励每留</option>
            <option value="安卓-激励七留">安卓-激励七留</option>
          </select>
          <span class="ap-log-summary">共 {{ assignLogs.length }} 条记录</span>
        </div>

        <div v-if="logLoading" class="ap-empty-hint">加载中…</div>
        <div v-else-if="!assignLogs.length" class="ap-empty-hint">暂无分配记录</div>
        <div v-else class="ap-log-list">
          <div v-for="log in assignLogs" :key="log.id" class="ap-log-card">
            <div class="ap-log-card-header">
              <div class="ap-log-card-left">
                <span class="ap-log-time">{{ log.timestamp }}</span>
                <span class="ap-badge" :class="log.type === 'incentive' ? 'ap-badge-incentive' : 'ap-badge-normal'">
                  {{ log.type === 'incentive' ? '激励' : '普通' }}
                </span>
                <span class="ap-badge ap-badge-profile">{{ log.profile_key }}</span>
              </div>
              <div class="ap-log-card-right">
                <span class="ap-log-metric">{{ log.group_count }} 组</span>
                <span class="ap-log-metric">{{ log.total_accounts }} 个账户</span>
              </div>
            </div>
            <div class="ap-log-groups">
              <div v-for="g in log.groups" :key="g.group_index" class="ap-log-group">
                <div class="ap-log-group-title">
                  第 {{ g.group_index }} 组（{{ g.account_count }} 个账户）
                  <span v-if="g.group_name" class="ap-dim"> — {{ g.group_name }}</span>
                </div>
                <div class="ap-log-group-ids">
                  <span v-for="aid in g.account_ids" :key="aid" class="ap-log-aid">{{ aid }}</span>
                </div>
                <div v-if="g.drama_names && g.drama_names.length" class="ap-log-dramas">
                  剧名：{{ g.drama_names.join('、') }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Toast -->
      <div v-if="toast" class="ap-toast" :class="toast.type">{{ toast.message }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, watch } from 'vue'
import {
  getAccountPool, addPoolAccount, addPoolAccountsBatch,
  updatePoolAccount, deletePoolAccounts, importConfigToPool,
  parseAndImportAccounts, getAssignLogs, getAssignLogDates
} from '@/services/api'
import { useUiStore } from '@/stores/ui'

const uiStore = useUiStore()

const accounts = ref([])
const stats = ref({})
const allTags = ref([])
const loading = ref(false)
const toast = ref(null)

// Pool mode — sync with global work mode
const poolMode = ref(uiStore.workMode === 'incentive' ? 'incentive' : 'normal')

watch(() => uiStore.workMode, (newMode) => {
  const newPool = newMode === 'incentive' ? 'incentive' : 'normal'
  if (newPool !== poolMode.value) {
    poolMode.value = newPool
    currentPage.value = 1
    filterStrategy.value = ''
    loadData()
  }
})

// Filters
const filterType = ref('')
const filterTag = ref('')
const filterPlatform = ref('')
const filterStrategy = ref('')
const filterStatus = ref('')
const searchKeyword = ref('')
let searchTimer = null

// Pagination
const currentPage = ref(1)
const pageSize = ref(50)
const totalCount = ref(0)

// Tab & Assign Logs
const activeTab = ref('pool')
const assignLogs = ref([])
const logDates = ref([])
const logDateFilter = ref('')
const logProfileFilter = ref('')
const logLoading = ref(false)

const typeTabs = [
  { label: '全部', value: '' },
  { label: '投放账户', value: 'media' },
  { label: '素材账户', value: 'material' },
]

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))
const pagedAccounts = computed(() => accounts.value)

// Selection
const selectedIds = ref(new Set())
const selectAll = ref(false)

// Filter debounce
const filterTimer = ref(null)
function onFilterChange() {
  currentPage.value = 1
  clearTimeout(filterTimer.value)
  filterTimer.value = setTimeout(() => loadData(), 300)
}

function switchPoolMode(mode) {
  poolMode.value = mode
  uiStore.setWorkMode(mode === 'incentive' ? 'incentive' : 'normal')
  currentPage.value = 1
  filterStrategy.value = ''
  loadData()
}

// Form dialog
const showFormDialog = ref(false)
const editingId = ref('')
const form = reactive({
  account_id: '',
  type: 'media',
  name: '',
  platform: '',
  group_name: '',
  status: '',
  strategy: '',
  tags_input: '',
  remark: '',
})

// Batch import
const showBatchImport = ref(false)
const batchType = ref('media')
const batchTags = ref('')
const batchText = ref('')

function showToast(type, message) {
  toast.value = { type, message }
  setTimeout(() => { toast.value = null }, 3000)
}

async function loadData() {
  loading.value = true
  try {
    const res = await getAccountPool(filterType.value, searchKeyword.value, filterTag.value, filterPlatform.value, filterStrategy.value, filterStatus.value, currentPage.value, pageSize.value, poolMode.value)
    if (res?.ok) {
      accounts.value = res.items || res.accounts || []
      totalCount.value = res.total ?? accounts.value.length
      stats.value = res.stats || {}
      allTags.value = res.tags || []
    }
  } catch (e) {
    console.error('加载账户池失败:', e)
  } finally {
    loading.value = false
  }
  selectedIds.value = new Set()
  selectAll.value = false
}

function onSearchDebounced() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => loadData(), 300)
}

function toggleSelectAll() {
  if (selectAll.value) {
    selectedIds.value = new Set(accounts.value.map(a => a.id))
  } else {
    selectedIds.value = new Set()
  }
}

function toggleSelect(id) {
  const s = new Set(selectedIds.value)
  if (s.has(id)) s.delete(id); else s.add(id)
  selectedIds.value = s
  selectAll.value = s.size === accounts.value.length
}

function openAddDialog() {
  editingId.value = ''
  form.account_id = ''
  form.type = 'media'
  form.name = ''
  form.platform = ''
  form.group_name = ''
  form.status = ''
  form.strategy = ''
  form.tags_input = ''
  form.remark = ''
  showFormDialog.value = true
}

function openEditDialog(acc) {
  editingId.value = acc.id
  form.account_id = acc.account_id
  form.type = acc.type
  form.name = acc.name || ''
  form.platform = acc.platform || ''
  form.group_name = acc.group_name || ''
  form.status = acc.status || ''
  form.strategy = acc.strategy || ''
  form.tags_input = (acc.tags || []).join(', ')
  form.remark = acc.remark || ''
  showFormDialog.value = true
}

async function submitForm() {
  const tags = form.tags_input.split(/[,，]/).map(t => t.trim()).filter(Boolean)

  if (editingId.value) {
    // Update
    try {
      const res = await updatePoolAccount(editingId.value, {
        name: form.name,
        platform: form.platform,
        group_name: form.group_name,
        status: form.status,
        strategy: form.strategy,
        tags: tags,
        remark: form.remark,
      }, poolMode.value)
      if (res?.ok) {
        showToast('success', '✅ 账户已更新')
        showFormDialog.value = false
        // Optimistic update: patch the item in-place
        const idx = accounts.value.findIndex(a => a.id === editingId.value)
        if (idx !== -1) {
          accounts.value[idx] = {
            ...accounts.value[idx],
            name: form.name,
            platform: form.platform,
            group_name: form.group_name,
            status: form.status,
            strategy: form.strategy,
            tags: tags,
            remark: form.remark,
          }
        }
      } else {
        showToast('error', '❌ ' + (res?.error || '更新失败'))
      }
    } catch (e) {
      showToast('error', '❌ ' + e.message)
    }
  } else {
    // Add
    if (!form.account_id.trim()) {
      showToast('error', '❌ 账户ID不能为空')
      return
    }
    try {
      const res = await addPoolAccount(form.account_id, form.type, form.name, tags, form.remark, form.group_name, form.status, form.strategy, form.platform, poolMode.value)
      if (res?.ok) {
        showToast('success', '✅ 账户已添加')
        showFormDialog.value = false
        await loadData()
      } else {
        showToast('error', '❌ ' + (res?.error || '添加失败'))
      }
    } catch (e) {
      showToast('error', '❌ ' + e.message)
    }
  }
}

async function submitBatch() {
  const rawText = batchText.value.trim()
  if (!rawText) {
    showToast('error', '❌ 请粘贴账户数据')
    return
  }
  const tags = batchTags.value.split(/[,，]/).map(t => t.trim()).filter(Boolean)
  try {
    const res = await parseAndImportAccounts(rawText, batchType.value, tags, poolMode.value)
    if (res?.ok) {
      showToast('success', `✅ 导入完成：新增 ${res.added}，跳过重复 ${res.skipped}`)
      showBatchImport.value = false
      batchText.value = ''
      await loadData()
    } else {
      showToast('error', '❌ ' + (res?.error || '导入失败'))
    }
  } catch (e) {
    showToast('error', '❌ ' + e.message)
  }
}

async function doImportFromConfig() {
  try {
    const res = await importConfigToPool(poolMode.value)
    if (res?.ok) {
      showToast('success', `✅ 从配置导入完成：新增 ${res.added}，跳过重复 ${res.skipped}`)
      await loadData()
    } else {
      showToast('error', '❌ ' + (res?.error || '导入失败'))
    }
  } catch (e) {
    showToast('error', '❌ ' + e.message)
  }
}

async function deleteSingle(acc) {
  if (!confirm(`确定删除账户 ${acc.account_id} 吗？`)) return
  try {
    const res = await deletePoolAccounts([acc.id], poolMode.value)
    if (res?.ok) {
      showToast('success', '✅ 已删除')
      // Optimistic update: remove from local list
      accounts.value = accounts.value.filter(a => a.id !== acc.id)
      totalCount.value = Math.max(0, totalCount.value - 1)
      selectedIds.value.delete(acc.id)
    }
  } catch (e) {
    showToast('error', '❌ ' + e.message)
  }
}

async function deleteSelected() {
  const ids = [...selectedIds.value]
  if (!ids.length) return
  if (!confirm(`确定删除选中的 ${ids.length} 个账户吗？`)) return
  try {
    const res = await deletePoolAccounts(ids, poolMode.value)
    if (res?.ok) {
      showToast('success', `✅ 已删除 ${ids.length} 个账户`)
      // Optimistic update: remove from local list
      const deletedSet = new Set(ids)
      accounts.value = accounts.value.filter(a => !deletedSet.has(a.id))
      totalCount.value = Math.max(0, totalCount.value - ids.length)
      selectedIds.value = new Set()
      selectAll.value = false
    }
  } catch (e) {
    showToast('error', '❌ ' + e.message)
  }
}

async function switchToLogs() {
  activeTab.value = 'logs'
  if (!logDates.value.length) {
    await loadLogDates()
  }
  if (!assignLogs.value.length) {
    await loadLogs()
  }
}

async function loadLogDates() {
  try {
    const res = await getAssignLogDates()
    if (res?.ok) {
      logDates.value = res.dates || []
    }
  } catch (e) {
    console.error('加载日志日期失败:', e)
  }
}

async function loadLogs() {
  logLoading.value = true
  try {
    const res = await getAssignLogs(logDateFilter.value, logProfileFilter.value)
    if (res?.ok) {
      assignLogs.value = res.logs || []
    }
  } catch (e) {
    console.error('加载分配日志失败:', e)
  } finally {
    logLoading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
/* ═══════════════════════════════════════════════
   AccountPoolView — Self-contained LIGHT theme
   No CSS variables from global dark theme used.
   ═══════════════════════════════════════════════ */

.ap-page {
  background: #f5f7fa;
  min-height: 100vh;
  padding: 24px;
  box-sizing: border-box;
}

.ap-container {
  max-width: 1200px;
  margin: 0 auto;
}

/* ── Header ── */
.ap-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.ap-title {
  font-size: 22px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0 0 4px 0;
}

.ap-desc {
  font-size: 13px;
  color: #999;
  margin: 0;
}

.ap-header-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

/* ── Buttons ── */
.ap-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: all 0.15s ease;
  white-space: nowrap;
  font-family: inherit;
}

.ap-btn-primary {
  background: #f0a500;
  color: #fff;
  border: 1px solid #f0a500;
}
.ap-btn-primary:hover {
  background: #d99400;
  border-color: #d99400;
}

.ap-btn-ghost {
  background: #fff;
  color: #555;
  border: 1px solid #e0e0e0;
}
.ap-btn-ghost:hover {
  background: #f8f9fb;
  border-color: #ccc;
  color: #333;
}

.ap-btn-sm {
  padding: 4px 10px;
  font-size: 11px;
}

.ap-btn-danger-text {
  color: #ef4444 !important;
}

/* ── Stats Bar ── */
.ap-stats-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.ap-stat-item {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 10px 18px;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.ap-stat-value {
  font-size: 22px;
  font-weight: 800;
  font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  color: #1a1a2e;
}

.ap-stat-media { color: #3b82f6; }
.ap-stat-material { color: #a855f7; }
.ap-stat-ios { color: #3b82f6; }
.ap-stat-android { color: #10b981; }
.ap-stat-rta { color: #10b981; }

.ap-stat-label {
  font-size: 12px;
  color: #999;
}

/* ── Filter Bar ── */
.ap-filter-bar {
  margin-bottom: 12px;
}

.ap-filter-row-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.ap-type-tabs {
  display: flex;
  gap: 2px;
  background: #f0f2f5;
  border-radius: 6px;
  padding: 3px;
  border: 1px solid #e8e8e8;
}

.ap-type-tab {
  padding: 6px 16px;
  border: none;
  border-radius: 5px;
  font-size: 12px;
  font-weight: 500;
  font-family: inherit;
  background: transparent;
  color: #666;
  cursor: pointer;
  transition: all 0.15s ease;
}
.ap-type-tab:hover {
  background: #fff;
  color: #333;
}
.ap-type-tab.active {
  background: #fff;
  color: #f0a500;
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.ap-filter-controls {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.ap-filter-select {
  padding: 6px 10px;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  font-size: 12px;
  background: #fff;
  color: #333;
  outline: none;
  font-family: inherit;
  cursor: pointer;
  transition: border-color 0.15s ease;
}
.ap-filter-select:focus {
  border-color: #f0a500;
}

.ap-filter-input {
  padding: 6px 12px;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  font-size: 12px;
  background: #fff;
  color: #333;
  outline: none;
  width: 240px;
  font-family: inherit;
  transition: border-color 0.15s ease;
}
.ap-filter-input:focus {
  border-color: #f0a500;
  box-shadow: 0 0 0 3px rgba(240, 165, 0, 0.08);
}

/* ── Bulk Top Bar ── */
.ap-bulk-top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  margin-bottom: 8px;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.ap-bulk-top-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.ap-check-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #555;
  cursor: pointer;
  user-select: none;
  font-weight: 500;
}

.ap-check-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: #f0a500;
}

.ap-selected-count {
  font-size: 12px;
  color: #f0a500;
  font-weight: 600;
}

.ap-bulk-top-right {
  display: flex;
  gap: 8px;
}

.ap-btn-danger {
  background: #fff;
  color: #ef4444;
  border: 1px solid #fecaca;
}
.ap-btn-danger:hover {
  background: #fef2f2;
  border-color: #ef4444;
}

/* ── Card ── */
.ap-card {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  overflow: hidden;
}

/* ── Table ── */
.ap-table-wrap {
  overflow-x: auto;
}

.ap-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.ap-table thead tr {
  background: #f8f9fb;
}

.ap-table th {
  padding: 10px 12px;
  text-align: left;
  font-size: 11px;
  font-weight: 700;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  border-bottom: 1px solid #e8e8e8;
  white-space: nowrap;
}

.ap-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #f0f0f0;
  color: #555;
  vertical-align: middle;
}

.ap-table tbody tr:hover {
  background: #fafbfc;
}

.ap-table tbody tr.ap-row-selected td {
  background: rgba(240, 165, 0, 0.04);
}

.ap-col-check {
  width: 36px;
  text-align: center;
}

.ap-col-id {
  font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  font-weight: 700;
  color: #1a1a2e !important;
}

.ap-col-remark {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ap-col-time {
  font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  font-size: 11px;
  color: #999 !important;
  white-space: nowrap;
}

.ap-col-actions {
  width: 80px;
  white-space: nowrap;
}

/* ── Badges ── */
.ap-badge {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.ap-badge-ios {
  background: rgba(59, 130, 246, 0.10);
  color: #3b82f6;
}

.ap-badge-android {
  background: rgba(16, 185, 129, 0.10);
  color: #10b981;
}

.ap-badge-rta {
  background: rgba(16, 185, 129, 0.10);
  color: #10b981;
}

.ap-badge-meiliu {
  background: rgba(245, 158, 11, 0.10);
  color: #f59e0b;
}

.ap-badge-qiliu {
  background: rgba(99, 102, 241, 0.10);
  color: #6366f1;
}

/* ── Tag chips ── */
.ap-tag-chip {
  display: inline-block;
  padding: 1px 7px;
  margin: 1px 2px;
  background: #f5f7fa;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  font-size: 10px;
  color: #555;
}

.ap-dim {
  color: #ccc;
}

/* ── Icon Buttons ── */
.ap-btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px 4px;
  font-size: 14px;
  color: #999;
  transition: color 0.15s ease;
}
.ap-btn-icon:hover {
  color: #333;
}
.ap-btn-icon-danger:hover {
  color: #ef4444 !important;
}

/* ── Bulk Bar (removed — replaced by top bar) ── */

/* ── Modal ── */
.ap-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
  animation: apFadeIn 0.15s ease;
}

.ap-modal-box {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 10px;
  padding: 24px;
  width: 440px;
  max-height: 85vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

.ap-modal-box.ap-modal-wide {
  width: 560px;
}

.ap-modal-box h3 {
  font-size: 17px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0 0 18px 0;
}

.ap-batch-hint {
  font-size: 12px;
  color: #999;
  margin: -10px 0 16px 0;
  line-height: 1.5;
}

.ap-form-field {
  margin-bottom: 14px;
}

.ap-form-field label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #555;
  margin-bottom: 5px;
}

.ap-required {
  color: #ef4444;
}

.ap-text-input {
  padding: 8px 12px;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  font-family: inherit;
  font-size: 13px;
  background: #fff;
  color: #333;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.ap-text-input:focus {
  border-color: #f0a500;
  box-shadow: 0 0 0 3px rgba(240, 165, 0, 0.08);
}

.ap-text-input:disabled {
  background: #f5f7fa;
  color: #999;
  cursor: not-allowed;
}

.ap-wide {
  width: 100%;
  box-sizing: border-box;
}

.ap-input-area {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  font-size: 12px;
  resize: vertical;
  background: #fff;
  color: #333;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.15s ease;
}
.ap-input-area:focus {
  border-color: #f0a500;
  box-shadow: 0 0 0 3px rgba(240, 165, 0, 0.08);
}

.ap-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}

.ap-empty-hint {
  text-align: center;
  padding: 48px 24px;
  color: #bbb;
  font-size: 13px;
}

/* ── Toast ── */
.ap-toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  z-index: 1000;
  animation: apSlideUp 0.2s ease;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.ap-toast.success {
  background: #ecfdf5;
  color: #059669;
  border: 1px solid #a7f3d0;
}

.ap-toast.error {
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
}

/* ── Animations ── */
@keyframes apSlideUp {
  from { transform: translateY(16px) scale(0.95); opacity: 0; }
  to { transform: translateY(0) scale(1); opacity: 1; }
}

@keyframes apFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .ap-page {
    padding: 12px;
  }
  .ap-stats-bar {
    flex-direction: column;
    gap: 8px;
  }
  .ap-filter-row-top {
    flex-direction: column;
    align-items: stretch;
  }
  .ap-filter-controls {
    flex-direction: column;
  }
  .ap-filter-input {
    width: 100%;
  }
  .ap-header {
    flex-direction: column;
    gap: 12px;
  }
  .ap-header-actions {
    flex-wrap: wrap;
  }
}
/* ── Pagination ── */
.ap-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #f0f0f0;
  background: #fafbfc;
}

.ap-page-btn {
  padding: 4px 12px;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background: #fff;
  color: #555;
  font-size: 12px;
  cursor: pointer;
  font-family: inherit;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.ap-page-btn:hover:not(:disabled) {
  border-color: #f0a500;
  background: #fffbf0;
  color: #d99400;
}
.ap-page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.ap-page-info {
  font-size: 12px;
  color: #666;
  font-weight: 500;
  padding: 0 8px;
}

.ap-page-total {
  color: #999;
  font-weight: 400;
}

.ap-page-size-select {
  padding: 4px 8px;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  font-size: 12px;
  background: #fff;
  color: #555;
  cursor: pointer;
  font-family: inherit;
  margin-left: 8px;
}

/* ── Pool Mode Switcher ── */
.ap-pool-switcher {
  display: flex;
  gap: 2px;
  background: #f0f2f5;
  border-radius: 8px;
  padding: 3px;
  margin-bottom: 16px;
  border: 1px solid #e8e8e8;
  width: fit-content;
}

.ap-pool-btn {
  padding: 8px 24px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  font-family: inherit;
  background: transparent;
  color: #666;
  cursor: pointer;
  transition: all 0.15s ease;
}
.ap-pool-btn:hover {
  background: #fff;
  color: #333;
}
.ap-pool-btn.active {
  background: #fff;
  color: #f0a500;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

/* ── Tab Bar ── */
.ap-tab-bar {
  display: flex;
  gap: 2px;
  background: #f0f2f5;
  border-radius: 8px;
  padding: 3px;
  margin-bottom: 16px;
  border: 1px solid #e8e8e8;
  width: fit-content;
}

.ap-tab {
  padding: 8px 20px;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  background: transparent;
  color: #666;
  cursor: pointer;
  transition: all 0.15s ease;
}
.ap-tab:hover {
  background: #fff;
  color: #333;
}
.ap-tab.active {
  background: #fff;
  color: #f0a500;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

/* ── Log Panel ── */
.ap-log-panel {
  margin-top: 4px;
}

.ap-log-filters {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.ap-log-summary {
  font-size: 12px;
  color: #999;
  margin-left: 8px;
}

.ap-log-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ap-log-card {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  transition: box-shadow 0.15s ease;
}
.ap-log-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.ap-log-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 8px;
}

.ap-log-card-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ap-log-card-right {
  display: flex;
  gap: 12px;
}

.ap-log-time {
  font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  font-size: 13px;
  font-weight: 600;
  color: #1a1a2e;
}

.ap-log-metric {
  font-size: 13px;
  font-weight: 700;
  color: #f0a500;
}

.ap-badge-normal {
  background: rgba(59, 130, 246, 0.10);
  color: #3b82f6;
}

.ap-badge-incentive {
  background: rgba(245, 158, 11, 0.10);
  color: #f59e0b;
}

.ap-badge-profile {
  background: rgba(99, 102, 241, 0.08);
  color: #6366f1;
}

.ap-log-groups {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ap-log-group {
  padding: 10px 12px;
  background: #f8f9fb;
  border-radius: 6px;
  border: 1px solid #f0f0f0;
}

.ap-log-group-title {
  font-size: 12px;
  font-weight: 600;
  color: #555;
  margin-bottom: 6px;
}

.ap-log-group-ids {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 4px;
}

.ap-log-aid {
  display: inline-block;
  padding: 2px 8px;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  font-size: 11px;
  color: #1a1a2e;
}

.ap-log-dramas {
  font-size: 11px;
  color: #999;
  margin-top: 4px;
}

</style>
