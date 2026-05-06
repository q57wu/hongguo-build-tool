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
            <label class="field-label-inline">下载目录</label>
            <input v-model="config.common.download_dir" class="text-input wide" placeholder="留空则使用 ~/Downloads" />
          </div>
          <div class="field-row">
            <label class="field-label-inline">操作员名称</label>
            <input v-model="config.common.operator_name" class="text-input wide" placeholder="用于项目命名（默认 lzp）" />
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
            <button class="btn btn-ghost btn-sm" @click="addGroup">➕ 添加组</button>
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
                  <div v-for="(drama, dIdx) in (group.dramas || [])" :key="dIdx" class="drama-card">
                    <div class="drama-row">
                      <input v-model="drama.name" class="text-input drama-input" placeholder="剧名" />
                      <input v-model="drama.click" class="text-input drama-input" placeholder="点击链接" />
                      <input v-model="drama.show" class="text-input drama-input" placeholder="展示链接" />
                      <input v-model="drama.video" class="text-input drama-input" placeholder="播放链接" />
                      <button class="btn-icon" @click="removeDrama(group, dIdx)" title="删除">✕</button>
                    </div>
                    <div class="field-row material-row">
                      <label class="field-label material-label">素材ID（每行一个）</label>
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

    <!-- 加载中 -->
    <div v-else class="loading">加载配置中...</div>

    <!-- 保存提示 -->
    <div v-if="saveStatus" class="save-toast" :class="saveStatus.type">{{ saveStatus.message }}</div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { getConfig, saveConfig as saveConfigApi } from '@/services/api'

const config = ref(null)
const currentKey = ref('')
const saveStatus = ref(null)

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
  if (!confirm('确定要删除该组吗？')) return
  currentProfile.value.groups.splice(idx, 1)
  await saveAll()
}

function addDrama(group) {
  if (!group.dramas) group.dramas = []
  group.dramas.push({ name: '', click: '', show: '', video: '', material_ids: [] })
}

function removeDrama(group, idx) {
  group.dramas.splice(idx, 1)
}

async function saveAll() {
  if (!config.value) return
  try {
    const res = await saveConfigApi(config.value)
    if (res.ok) {
      showSave('success', '✅ 配置已保存')
    } else {
      showSave('error', '❌ 保存失败: ' + res.error)
    }
  } catch (e) {
    showSave('error', '❌ ' + e.message)
  }
}

function showSave(type, message) {
  saveStatus.value = { type, message }
  setTimeout(() => { saveStatus.value = null }, 3000)
}

onMounted(loadConfig)
</script>

<style scoped>
.view-container { max-width: 1100px; }
.view-header { margin-bottom: 16px; }
.view-header h2 { font-size: 20px; font-weight: 700; margin-bottom: 4px; }
.view-desc { font-size: 13px; color: var(--c-dim); }
.header-row { display: flex; justify-content: space-between; align-items: flex-start; }
.header-actions { display: flex; gap: 8px; }

/* 布局 */
.settings-layout { display: flex; gap: 20px; }

/* 左侧导航 */
.profile-nav { width: 200px; flex-shrink: 0; }
.nav-section-title { font-size: 11px; font-weight: 700; color: var(--c-dim); text-transform: uppercase; margin-bottom: 10px; }
.nav-category { margin-bottom: 16px; }
.nav-cat-header { font-size: 12px; font-weight: 700; color: var(--c-text-2); margin-bottom: 4px; padding: 4px 10px; }
.nav-profile-btn { display: block; width: 100%; text-align: left; padding: 8px 14px; border: none; border-radius: var(--r-sm); font-size: 13px; font-family: var(--f-ui); color: var(--c-text-2); background: transparent; cursor: pointer; transition: all var(--transition-fast); margin-bottom: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.nav-profile-btn:hover { background: var(--c-hover); color: var(--c-text); }
.nav-profile-btn.active { background: var(--c-primary); color: #fff; }

/* 右侧配置区 */
.config-area { flex: 1; min-width: 0; }
.config-section { margin-bottom: 16px; }
.section-title { font-size: 14px; font-weight: 700; margin-bottom: 14px; }
.section-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.section-head .section-title { margin-bottom: 0; }

/* 字段 */
.field-row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.field-label-inline { font-size: 13px; font-weight: 600; color: var(--c-text-2); white-space: nowrap; }
.field-label { display: block; font-size: 12px; font-weight: 600; color: var(--c-text-2); margin-bottom: 4px; }
.field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

@media (max-width: 768px) {
  .field-grid { grid-template-columns: 1fr; }
  .settings-layout { flex-direction: column; }
  .profile-nav { width: 100%; }
}
.field-item { display: flex; flex-direction: column; }

.text-input { padding: 7px 12px; border: 1px solid var(--c-border); border-radius: var(--r-sm); font-family: var(--f-mono); font-size: 12px; background: var(--c-card); color: var(--c-text); outline: none; transition: border-color var(--transition-fast); }
.text-input:focus { border-color: var(--c-primary); }
.text-input.wide { flex: 1; }
.input-area { width: 100%; padding: 8px 12px; border: 1px solid var(--c-border); border-radius: var(--r-sm); font-family: var(--f-mono); font-size: 12px; resize: vertical; background: var(--c-card); color: var(--c-text); outline: none; }

/* Groups */
.group-card { border: 1px solid var(--c-border); border-radius: var(--r-md); margin-bottom: 12px; overflow: hidden; }
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
.group-header:hover { background: var(--c-hover); }
.collapse-icon { font-size: 10px; color: var(--c-dim); width: 14px; flex-shrink: 0; }
.group-title { font-size: 13px; font-weight: 700; color: var(--c-text); }
.group-summary { font-size: 11px; color: var(--c-dim); margin-left: auto; margin-right: 8px; }
.group-body { padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }

.dramas-section { margin-top: 4px; }
.dramas-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.drama-card { border: 1px solid var(--c-border-s); border-radius: var(--r-sm); padding: 8px; margin-bottom: 8px; }
.drama-row { display: flex; gap: 6px; align-items: center; margin-bottom: 6px; }
.material-row { display: flex; gap: 8px; align-items: flex-start; margin: 0; }
.material-label { white-space: nowrap; margin-top: 6px; flex-shrink: 0; }
.material-row .input-area { flex: 1; }
.drama-input { flex: 1; min-width: 0; font-size: 11px; padding: 5px 8px; }

.btn-sm { padding: 4px 10px; font-size: 11px; }
.btn-xs { padding: 2px 8px; font-size: 11px; background: none; border: 1px solid var(--c-border); border-radius: var(--r-sm); cursor: pointer; color: var(--c-text-2); }
.btn-xs:hover { background: var(--c-hover); }
.btn-icon { background: none; border: none; cursor: pointer; color: var(--c-dim); font-size: 14px; padding: 2px 4px; }
.btn-icon:hover { color: var(--c-red); }
.btn-danger-text { color: var(--c-red) !important; }
.empty-hint { text-align: center; padding: 20px; color: var(--c-dim); font-size: 13px; }

.loading { text-align: center; padding: 40px; color: var(--c-dim); }

/* 保存提示 */
.save-toast { position: fixed; bottom: 24px; right: 24px; padding: 10px 20px; border-radius: var(--r-sm); font-size: 13px; font-weight: 600; z-index: 1000; animation: slideUp 0.2s ease; }
.save-toast.success { background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; }
.save-toast.error { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
@keyframes slideUp { from { transform: translateY(10px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
</style>
