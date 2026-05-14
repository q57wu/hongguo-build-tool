<template>
  <div class="view-container">
    <div class="view-header">
      <div class="header-row">
        <div>
          <h2>⚙️ 设置</h2>
          <p class="view-desc">配置管理与参数调整</p>
        </div>
        <div class="header-actions">
          <button class="btn btn-ghost" @click="loadConfig">🔄 重新加载</button>
          <button class="btn btn-primary" @click="saveAll">💾 保存全部</button>
        </div>
      </div>
    </div>

    <div class="settings-layout" v-if="config">
      <!-- 左侧 Profile 导航 -->
      <aside class="profile-nav">
        <div class="nav-section-title">选择投放方向</div>
        <div v-for="(cat, catIdx) in categories" :key="catIdx" class="nav-category">
          <div class="nav-cat-header">{{ cat.name }}</div>
          <button
            v-for="key in cat.keys"
            :key="key"
            class="nav-profile-btn"
            :class="{ active: currentKey === key }"
            @click="switchProfile(key)"
          >{{ key }}</button>
        </div>
      </aside>

      <!-- 右侧配置编辑区 -->
      <div class="config-area">
        <!-- 公共配置 -->
        <div class="card config-section">
          <h3 class="section-title">🌐 公共配置</h3>
          <div class="field-row">
            <label class="field-label-inline">CDP 端点</label>
            <input v-model="config.common.cdp_endpoint" class="text-input wide" />
          </div>
          <div class="field-row">
            <label class="field-label-inline">Chrome 路径</label>
            <input v-model="config.common.chrome_path" class="text-input wide" placeholder="留空则自动查找" />
          </div>
          <div class="field-row">
            <label class="field-label-inline">Chrome 数据目录</label>
            <input v-model="config.common.chrome_profile_dir" class="text-input wide" placeholder="留空则使用系统默认 Chrome 数据目录" />
          </div>
          <div class="field-row">
            <label class="field-label-inline">下载目录</label>
            <input v-model="config.common.download_dir" class="text-input wide" placeholder="留空则使用 ~/Downloads" />
          </div>
          <div class="field-row">
            <label class="field-label-inline">操作员名称</label>
            <input v-model="config.common.operator_name" class="text-input wide" placeholder="用于项目命名（默认 lzp）" />
          </div>
        </div>

        <!-- 配置备份 -->
        <div class="card config-section">
          <div class="section-head">
            <h3 class="section-title">💾 配置备份</h3>
            <button class="btn btn-ghost btn-sm" @click="loadBackups">🔄 刷新</button>
          </div>
          <p class="backup-desc">每次保存配置时自动创建备份，最多保留 10 个版本</p>
          <div v-if="!backups.length" class="empty-hint">暂无备份记录</div>
          <div v-else class="backup-list">
            <div v-for="b in backups" :key="b.filename" class="backup-item">
              <div class="backup-info">
                <span class="backup-time">{{ b.timestamp }}</span>
                <span class="backup-size">{{ b.size_kb }} KB</span>
              </div>
              <div class="backup-actions">
                <button class="btn btn-ghost btn-xs" @click="restoreBackup(b.filename)">恢复</button>
                <button class="btn btn-ghost btn-xs btn-danger-text" @click="deleteBackup(b.filename)">删除</button>
              </div>
            </div>
          </div>
        </div>

        <!-- 当前 Profile 配置 -->
        <div class="card config-section" v-if="currentProfile">
          <h3 class="section-title">📝 {{ currentKey }} 配置</h3>

          <div class="field-grid">
            <div class="field-item" v-for="(label, field) in fieldLabels" :key="field">
              <label class="field-label">{{ label }}</label>
              <input
                v-model="currentProfile[field]"
                class="text-input"
                :type="field === 'wait_scale' ? 'number' : 'text'"
                :step="field === 'wait_scale' ? '0.1' : undefined"
              />
            </div>
          </div>
        </div>

        <!-- Groups 管理 -->
        <div class="card config-section" v-if="currentProfile">
          <div class="section-head">
            <h3 class="section-title">📦 账户组 ({{ currentGroups.length }} 组)</h3>
            <div style="display:flex;gap:6px;">
              <button class="btn btn-ghost btn-sm" @click="addGroup">➕ 添加组</button>
            </div>
          </div>

          <div v-if="!currentGroups.length" class="empty-hint">暂无账户组，点击上方按钮添加</div>

          <div v-for="(group, gIdx) in currentGroups" :key="group.id ?? gIdx" class="group-card">
            <!-- 组头：可点击折叠 -->
            <div class="group-header" @click="toggleGroupCollapse(gIdx)">
              <span class="collapse-icon">{{ collapsedGroups.has(gIdx) ? '▶' : '▼' }}</span>
              <span class="group-title">组 {{ group.id }}{{ group.group_name ? ' — ' + group.group_name : '' }}</span>
              <span class="group-summary">
                {{ (group.account_ids || []).length }} 个账号{{ !isIncentiveProfile ? ` · ${(group.dramas || []).length} 部剧` : '' }}
              </span>
              <button class="btn btn-ghost btn-sm btn-danger-text" @click.stop="removeGroup(gIdx)">🗑 删除</button>
            </div>

            <!-- 组详情：可折叠 -->
            <div v-show="!collapsedGroups.has(gIdx)" class="group-body">
              <!-- 账户ID（通用） -->
              <div class="field-item">
                <label class="field-label">账户 ID（每行一个）</label>
                <textarea
                  :value="(group.account_ids || []).join('\n')"
                  @input="group.account_ids = $event.target.value.split('\n').map(s => s.trim()).filter(Boolean)"
                  class="input-area"
                  rows="3"
                  placeholder="每行一个账户ID"
                ></textarea>
              </div>

              <!-- 非激励：剧列表 + 素材ID -->
              <template v-if="!isIncentiveProfile">
                <div class="dramas-section">
                  <div class="dramas-head">
                    <label class="field-label" style="margin: 0;">短剧 ({{ (group.dramas || []).length }})</label>
                    <button class="btn btn-ghost btn-xs" @click="addDrama(group)">+ 添加</button>
                  </div>
                  <div v-for="(drama, dIdx) in (group.dramas || [])" :key="dIdx" class="drama-card-v">
                    <div class="drama-card-header">
                      <span class="drama-card-num">剧 {{ dIdx + 1 }}</span>
                      <span class="drama-card-name">{{ drama.name || '未命名' }}</span>
                      <button class="btn-icon btn-icon-danger" @click="removeDrama(group, dIdx)" title="删除此剧">✕</button>
                    </div>
                    <div class="drama-card-body">
                      <div class="drama-field">
                        <label class="drama-field-label">剧名 *</label>
                        <input v-model="drama.name" class="text-input" placeholder="输入剧名" />
                      </div>
                      <div class="drama-field">
                        <label class="drama-field-label">点击监测链接</label>
                        <input v-model="drama.click" class="text-input text-input-mono" placeholder="https://..." />
                      </div>
                      <div class="drama-field">
                        <label class="drama-field-label">展示监测链接</label>
                        <input v-model="drama.show" class="text-input text-input-mono" placeholder="https://..." />
                      </div>
                      <div class="drama-field">
                        <label class="drama-field-label">播放监测链接</label>
                        <input v-model="drama.video" class="text-input text-input-mono" placeholder="https://..." />
                      </div>
                      <div class="drama-field">
                        <label class="drama-field-label">素材 ID（每行一个）</label>
                        <textarea
                          :value="(drama.material_ids || []).join('\n')"
                          @input="drama.material_ids = $event.target.value.split('\n').map(s => s.trim()).filter(Boolean)"
                          class="input-area"
                          rows="2"
                          placeholder="每行一个素材ID"
                        ></textarea>
                      </div>
                    </div>
                  </div>
                </div>
              </template>

              <!-- 激励：链接字段 -->
              <template v-else>
                <div class="field-item">
                  <label class="field-label">组名</label>
                  <input v-model="group.group_name" class="text-input" placeholder="组名" />
                </div>
                <div class="field-item">
                  <label class="field-label">点击监测链接</label>
                  <input v-model="group.click_url" class="text-input" placeholder="https://..." />
                </div>
                <div class="field-item">
                  <label class="field-label">展示监测链接</label>
                  <input v-model="group.show_url" class="text-input" placeholder="https://..." />
                </div>
                <div class="field-item">
                  <label class="field-label">有效播放监测链接</label>
                  <input v-model="group.play_url" class="text-input" placeholder="https://..." />
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 保存提示 -->
    <div v-if="saveStatus" class="save-toast" :class="saveStatus.type">{{ saveStatus.message }}</div>

    <ConfirmDialog
      ref="deleteDialog"
      :title="deleteDialogTitle"
      :message="deleteDialogMessage"
      confirm-text="删除"
      :is-danger="true"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { getConfig, saveConfig as saveConfigApi, listConfigBackups, restoreConfigBackup, deleteConfigBackup } from '@/services/api'
import ConfirmDialog from '@/components/ConfirmDialog.vue'

const config = ref(null)
const currentKey = ref('')
const saveStatus = ref(null)
const deleteDialog = ref(null)
const deleteDialogTitle = ref('确认删除')
const deleteDialogMessage = ref('')
const backups = ref([])

// 判断当前是否激励配置
const isIncentiveProfile = computed(() => {
  return currentKey.value?.includes('激励')
})

// 组折叠状态
const collapsedGroups = ref(new Set())

function toggleGroupCollapse(idx) {
  const s = new Set(collapsedGroups.value)
  if (s.has(idx)) s.delete(idx)
  else s.add(idx)
  collapsedGroups.value = s
}

// 切换 profile 时重置折叠状态（全部折叠）
watch(currentKey, () => {
  if (currentProfile.value?.groups) {
    collapsedGroups.value = new Set(currentProfile.value.groups.map((_, i) => i))
  }
})

const categories = [
  { name: '短剧单本', keys: ['安卓-每留', '安卓-七留', 'IOS-每留', 'IOS-七留'] },
  { name: '短剧激励', keys: ['安卓-激励每留', '安卓-激励七留'] },
]

const fieldLabels = {
  strategy: '投放策略',
  material_account_id: '素材账号 ID',
  audience_keyword: '受众关键词',
  monitor_btn_text: '监控按钮文案',
  name_prefix: '命名前缀',
  wait_scale: '等待倍率',
}

const currentProfile = computed(() => {
  if (!config.value || !currentKey.value) return null
  return config.value.profiles?.[currentKey.value] || null
})

const currentGroups = computed(() => {
  return currentProfile.value?.groups || []
})

async function loadConfig() {
  try {
    config.value = await getConfig()
    if (!currentKey.value && config.value?.profiles) {
      currentKey.value = Object.keys(config.value.profiles)[0] || ''
    }
    // 兼容旧数据：补全各 profile 中缺少 id 的 group
    if (config.value?.profiles) {
      for (const prof of Object.values(config.value.profiles)) {
        if (Array.isArray(prof.groups)) {
          prof.groups.forEach((g, idx) => {
            if (g.id == null) g.id = idx + 1
          })
        }
      }
    }
  } catch (e) {
    console.error('加载配置失败:', e)
  }
}

function switchProfile(key) {
  currentKey.value = key
}

function addGroup() {
  if (!currentProfile.value) return
  if (!currentProfile.value.groups) currentProfile.value.groups = []
  const existing = currentProfile.value.groups
  const newId = existing.length ? Math.max(...existing.map(g => g.id ?? 0)) + 1 : 1
  if (isIncentiveProfile.value) {
    existing.push({
      id: newId,
      account_ids: [],
      group_name: '',
      click_url: '',
      show_url: '',
      play_url: '',
    })
  } else {
    existing.push({
      id: newId,
      account_ids: [],
      group_name: '',
      dramas: [{ name: '', click: '', show: '', video: '', material_ids: [] }],
    })
  }
}

async function removeGroup(idx) {
  deleteDialogTitle.value = '确认删除'
  deleteDialogMessage.value = `确定要删除第 ${idx + 1} 组吗？该组的所有账户和剧名数据将被删除。`
  const confirmed = await deleteDialog.value?.show()
  if (!confirmed) return
  currentProfile.value.groups.splice(idx, 1)
  await saveAll()
}

function addDrama(group) {
  if (!group.dramas) group.dramas = []
  group.dramas.push({ name: '', click: '', show: '', video: '', material_ids: [] })
}

async function removeDrama(group, idx) {
  const drama = group.dramas[idx]
  const name = drama?.name || `第 ${idx + 1} 部剧`
  deleteDialogTitle.value = '确认删除'
  deleteDialogMessage.value = `确定要删除「${name}」吗？`
  const confirmed = await deleteDialog.value?.show()
  if (!confirmed) return
  group.dramas.splice(idx, 1)
}

function validateConfig() {
  if (!currentProfile.value) return '请先选择一个投放方向'

  const errors = []
  const p = currentProfile.value
  const key = currentKey.value

  // 检查关键字段
  if (!p.strategy?.trim()) errors.push('投放策略不能为空')
  if (!p.material_account_id?.trim()) errors.push('素材账号 ID 不能为空')
  if (!p.audience_keyword?.trim()) errors.push('受众关键词不能为空')

  // 检查账户组
  const groups = p.groups || []
  if (groups.length === 0) {
    errors.push('至少需要一个账户组')
  } else {
    groups.forEach((g, i) => {
      if (!g.account_ids || g.account_ids.length === 0) {
        errors.push(`组 ${g.id ?? i + 1}：缺少账户 ID`)
      }
      // 非激励模式：检查剧列表
      if (!key.includes('激励')) {
        const dramas = g.dramas || []
        if (dramas.length === 0) {
          errors.push(`组 ${g.id ?? i + 1}：至少需要一部剧`)
        } else {
          dramas.forEach((d, j) => {
            if (!d.name?.trim()) {
              errors.push(`组 ${g.id ?? i + 1} 剧 ${j + 1}：剧名不能为空`)
            }
          })
        }
      }
    })
  }

  return errors.length > 0 ? errors.join('\n') : null
}

async function saveAll() {
  if (!config.value) return

  // 验证当前 profile
  const validationError = validateConfig()
  if (validationError) {
    showSave('error', '❌ 配置校验失败:\n' + validationError)
    return
  }

  try {
    const res = await saveConfigApi(config.value)
    if (res.ok) {
      showSave('success', '✅ 配置已保存 — 可前往搭建控制台开始搭建')
      await loadBackups()
    } else {
      showSave('error', '❌ 保存失败: ' + res.error)
    }
  } catch (e) {
    showSave('error', '❌ ' + e.message)
  }
}

function showSave(type, message) {
  saveStatus.value = { type, message }
  // Errors stay longer so user can read all validation messages
  const duration = type === 'error' ? 8000 : 3000
  setTimeout(() => { saveStatus.value = null }, duration)
}

async function loadBackups() {
  try {
    const res = await listConfigBackups()
    if (res?.ok) {
      backups.value = res.backups || []
    }
  } catch (e) {
    console.error('加载备份列表失败:', e)
  }
}

async function restoreBackup(filename) {
  deleteDialogTitle.value = '确认恢复'
  deleteDialogMessage.value = `确定要从备份「${filename}」恢复配置吗？当前配置将被覆盖（会自动创建新备份）。`
  const confirmed = await deleteDialog.value?.show()
  if (!confirmed) return
  try {
    await restoreConfigBackup(filename)
    showSave('success', '✅ 配置已从备份恢复')
    await loadConfig()
    await loadBackups()
  } catch (e) {
    showSave('error', '❌ 恢复失败: ' + e.message)
  }
}

async function deleteBackup(filename) {
  deleteDialogTitle.value = '确认删除'
  deleteDialogMessage.value = `确定要删除备份「${filename}」吗？`
  const confirmed = await deleteDialog.value?.show()
  if (!confirmed) return
  try {
    await deleteConfigBackup(filename)
    showSave('success', '✅ 备份已删除')
    await loadBackups()
  } catch (e) {
    showSave('error', '❌ 删除失败: ' + e.message)
  }
}

onMounted(() => {
  loadConfig()
  loadBackups()
})
</script>

<style scoped>
/* ═══════════════════════════════════════════════════════
   Dark Industrial Console — SettingsView
   ═══════════════════════════════════════════════════════ */

.view-container {
  max-width: 1100px;
}

.view-header {
  margin-bottom: 16px;
}

.view-header h2 {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 4px;
  color: var(--c-text);
}

.view-desc {
  font-size: 13px;
  color: var(--c-dim);
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header-actions {
  display: flex;
  gap: 8px;
}

/* ── 布局 ─────────────────────────────────────────────── */
.settings-layout {
  display: flex;
  gap: 20px;
}

/* ── 左侧导航 ─────────────────────────────────────────── */
.profile-nav {
  width: 200px;
  flex-shrink: 0;
  border-right: 1px solid var(--c-border-s);
  padding-right: 16px;
}

.nav-section-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--c-dim);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 10px;
}

.nav-category {
  margin-bottom: 16px;
}

.nav-cat-header {
  font-size: 12px;
  font-weight: 700;
  color: var(--c-dim);
  margin-bottom: 4px;
  padding: 4px 10px;
}

.nav-profile-btn {
  display: block;
  width: 100%;
  text-align: left;
  padding: 8px 14px;
  border: 1px solid transparent;
  border-radius: var(--r-sm);
  font-size: 13px;
  font-family: var(--f-ui);
  color: var(--c-text-2);
  background: transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nav-profile-btn:hover {
  background: var(--c-hover);
  color: var(--c-text);
}

.nav-profile-btn.active {
  background: rgba(240, 165, 0, 0.12);
  color: #f0a500;
  border: 1px solid rgba(240, 165, 0, 0.2);
  box-shadow: 0 0 8px rgba(240, 165, 0, 0.15);
}

/* ── 右侧配置区 ───────────────────────────────────────── */
.config-area {
  flex: 1;
  min-width: 0;
}

.config-section {
  margin-bottom: 16px;
  background: var(--c-card);
}

.section-title {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 14px;
  color: var(--c-text);
}

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.section-head .section-title {
  margin-bottom: 0;
}

/* ── 字段 ──────────────────────────────────────────────── */
.field-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.field-label-inline {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-2);
  white-space: nowrap;
}

.field-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-2);
  margin-bottom: 4px;
}

.field-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

@media (max-width: 768px) {
  .field-grid { grid-template-columns: 1fr; }
  .settings-layout { flex-direction: column; }
  .profile-nav { width: 100%; border-right: none; border-bottom: 1px solid var(--c-border-s); padding-right: 0; padding-bottom: 16px; }
}

.field-item {
  display: flex;
  flex-direction: column;
}

/* ── 输入框 — 深色表面 ─────────────────────────────────── */
.text-input {
  padding: 7px 12px;
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
  font-family: var(--f-mono);
  font-size: 12px;
  background: var(--c-surface);
  color: var(--c-text);
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.text-input:focus {
  border-color: var(--c-accent);
  box-shadow: 0 0 0 3px rgba(240, 165, 0, 0.08);
}

.text-input.wide {
  flex: 1;
}

.input-area {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
  font-family: var(--f-mono);
  font-size: 12px;
  resize: vertical;
  background: var(--c-surface);
  color: var(--c-text);
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.input-area:focus {
  border-color: var(--c-accent);
  box-shadow: 0 0 0 3px rgba(240, 165, 0, 0.08);
}

/* ── Groups ────────────────────────────────────────────── */
.group-card {
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  margin-bottom: 12px;
  overflow: hidden;
  background: var(--c-card);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.group-card:hover {
  box-shadow: var(--shadow-sm);
}

.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: var(--c-surface);
  border-bottom: 1px solid var(--c-border-s);
  cursor: pointer;
  user-select: none;
  transition: background var(--transition-fast);
}

.group-header:hover {
  background: var(--c-hover);
}

.collapse-icon {
  font-size: 10px;
  color: var(--c-dim);
  width: 14px;
  flex-shrink: 0;
}

.group-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--c-text);
}

.group-summary {
  font-size: 11px;
  color: var(--c-dim);
  margin-left: auto;
  margin-right: 8px;
}

.group-body {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.dramas-section {
  margin-top: 4px;
}

.dramas-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

/* ── 剧信息卡片（纵向布局） ──────────────────────────── */
.drama-card-v {
  border: 1px solid var(--c-border-s);
  border-radius: var(--r-md);
  margin-bottom: 10px;
  overflow: hidden;
  background: var(--c-card);
  transition: all 0.2s ease;
}

.drama-card-v:hover {
  border-color: var(--c-border);
  box-shadow: var(--shadow-sm);
}

.drama-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--c-surface);
  border-bottom: 1px solid var(--c-border-s);
}

.drama-card-num {
  font-size: 11px;
  font-weight: 700;
  color: var(--c-dim);
  white-space: nowrap;
}

.drama-card-name {
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.drama-card-body {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.drama-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.drama-field-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--c-text-2);
}

.text-input-mono {
  font-family: var(--f-mono);
  font-size: 11px;
}

.btn-icon-danger:hover {
  color: var(--c-red) !important;
  background: rgba(239, 68, 68, 0.08);
  border-radius: 4px;
}

/* ── 按钮 ──────────────────────────────────────────────── */
.btn-sm {
  padding: 4px 10px;
  font-size: 11px;
}

.btn-xs {
  padding: 2px 8px;
  font-size: 11px;
  background: none;
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
  cursor: pointer;
  color: var(--c-text-2);
  transition: background var(--transition-fast), color var(--transition-fast);
}

.btn-xs:hover {
  background: var(--c-hover);
  color: var(--c-text);
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--c-dim);
  font-size: 14px;
  padding: 2px 4px;
}

.btn-icon:hover {
  color: var(--c-red);
}

.btn-danger-text {
  color: var(--c-red) !important;
}

.empty-hint {
  text-align: center;
  padding: 20px;
  color: var(--c-dim);
  font-size: 13px;
}

.loading {
  text-align: center;
  padding: 40px;
  color: var(--c-dim);
}

/* ── 保存提示 ──────────────────────────────────────────── */
.save-toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  padding: 10px 20px;
  border-radius: var(--r-sm);
  font-size: 13px;
  font-weight: 600;
  z-index: 1000;
  animation: slideUp 0.2s ease;
  white-space: pre-line;
  max-width: 480px;
}

.save-toast.success {
  background: var(--c-status-success-bg);
  color: var(--c-status-success-text);
  border: 1px solid var(--c-status-success-border);
}

.save-toast.error {
  background: var(--c-status-error-bg);
  color: var(--c-status-error-text);
  border: 1px solid var(--c-status-error-border);
}

@keyframes slideUp {
  from { transform: translateY(16px) scale(0.95); opacity: 0; }
  to   { transform: translateY(0) scale(1); opacity: 1; }
}

/* ── 配置备份 ──────────────────────────────────────────── */
.backup-desc {
  font-size: 12px;
  color: var(--c-dim);
  margin-bottom: 10px;
}

.backup-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.backup-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border: 1px solid var(--c-border-s);
  border-radius: var(--r-sm);
  font-size: 12px;
  background: var(--c-card);
  transition: background var(--transition-fast), border-color var(--transition-fast);
}

.backup-item:hover {
  background: var(--c-hover);
  border-color: var(--c-border);
}

.backup-info {
  display: flex;
  gap: 12px;
  align-items: center;
}

.backup-time {
  font-family: var(--f-mono);
  color: var(--c-text);
}

.backup-size {
  color: var(--c-dim);
}

.backup-actions {
  display: flex;
  gap: 4px;
}

/* ── 账户池选取弹窗 ──────────────────────────────────────── */
.pool-picker-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.pool-picker-modal {
  background: var(--c-card);
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  width: 480px;
  max-width: 90vw;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.2);
}

.pool-picker-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--c-border-s);
}

.pool-picker-header h3 {
  font-size: 15px;
  font-weight: 700;
  margin: 0;
  color: var(--c-text);
}

.pool-picker-body {
  padding: 20px;
}

.pool-picker-desc {
  font-size: 12px;
  color: var(--c-text-2);
  line-height: 1.6;
  margin-bottom: 16px;
}

.pool-picker-fields {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.pool-field label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-2);
  margin-bottom: 6px;
}

.pool-field-row {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.pool-field-row .seg-btn {
  padding: 5px 14px;
  font-size: 12px;
}

.pool-field-row .seg-btn.active {
  background: rgba(240, 165, 0, 0.12);
  color: #f0a500;
  border: 1px solid rgba(240, 165, 0, 0.2);
}

.pool-picker-summary {
  font-size: 13px;
  color: var(--c-text);
  padding: 10px 14px;
  background: var(--c-surface);
  border-radius: var(--r-sm);
  text-align: center;
}

.pool-picker-result {
  margin-top: 12px;
  padding: 10px 14px;
  border-radius: var(--r-sm);
  font-size: 12px;
  white-space: pre-line;
}

.pool-picker-result.success {
  background: var(--c-status-success-bg);
  color: var(--c-status-success-text);
}

.pool-picker-result.error {
  background: var(--c-status-error-bg);
  color: var(--c-status-error-text);
}

.pool-picker-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 14px 20px;
  border-top: 1px solid var(--c-border-s);
}
</style>
