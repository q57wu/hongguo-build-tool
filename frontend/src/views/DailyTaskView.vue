<template>
  <div class="page-container">
    <!-- 顶部：日期切换 + 进度 -->
    <header class="page-header">
      <div class="header-row">
        <div class="date-nav">
          <button class="btn-icon" @click="changeDate(-1)" title="前一天">◀</button>
          <h2 class="date-title">📋 {{ displayDate }}</h2>
          <button class="btn-icon" @click="changeDate(1)" title="后一天">▶</button>
          <button class="btn btn-ghost" @click="goToday" v-if="!isToday">回到今天</button>
        </div>
        <div class="progress-info">
          <span class="progress-text">{{ completedCount }} / {{ tasks.length }} 已完成</span>
        </div>
      </div>

      <!-- 进度条 -->
      <div class="progress-bar-track">
        <div
          class="progress-bar-fill"
          :style="{ width: progressPercent + '%' }"
        ></div>
      </div>
    </header>

    <!-- 解析区域 -->
    <section class="content-section parse-section">
      <div class="parse-card">
        <textarea
          v-model="rawText"
          class="parse-input"
          placeholder="粘贴原始任务文本到这里..."
          rows="5"
        ></textarea>
        <div class="parse-actions">
          <button
            class="btn btn-primary"
            @click="parseTasks"
            :disabled="!rawText.trim() || parsing"
          >
            {{ parsing ? '解析中...' : '🔍 解析任务' }}
          </button>
          <span v-if="parseError" class="parse-error">{{ parseError }}</span>
        </div>
        <div class="format-hint">
          <div class="format-hint-toggle" @click="showFormatExample = !showFormatExample">
            <span>{{ showFormatExample ? '▾' : '▸' }} 查看格式示例</span>
          </div>
          <div v-show="showFormatExample" class="format-example">
            <pre class="format-code">张三 安卓-每留 3部剧 每组3部 每组2户
李四 IOS-七留 2部剧</pre>
            <p class="format-note">每行一条任务：操作人 + 投放方向 + 参数。支持灵活格式，系统会自动识别关键信息。</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 手动添加 -->
    <section class="content-section manual-section">
      <button class="btn btn-outline" @click="showManual = !showManual">
        {{ showManual ? '收起' : '➕ 手动添加任务' }}
      </button>

      <div v-if="showManual" class="manual-form">
        <div class="form-row">
          <label class="form-label">搭建类型</label>
          <select v-model="manualForm.profile_key" class="form-select">
            <option value="">请选择</option>
            <option value="安卓-每留">安卓-每留</option>
            <option value="安卓-七留">安卓-七留</option>
            <option value="IOS-每留">IOS-每留</option>
            <option value="IOS-七留">IOS-七留</option>
            <option value="安卓-激励每留">安卓-激励每留</option>
            <option value="安卓-激励七留">安卓-激励七留</option>
          </select>
        </div>

        <div class="form-row">
          <label class="form-label">负责人</label>
          <input v-model="manualForm.person" class="form-input" placeholder="选填" />
        </div>

        <div class="form-row-group">
          <div class="form-row">
            <label class="form-label">剧数量</label>
            <input v-model.number="manualForm.drama_count" type="number" class="form-input" min="1" placeholder="如 12" />
          </div>
          <div class="form-row">
            <label class="form-label">每组几部</label>
            <input v-model.number="manualForm.dramas_per_group" type="number" class="form-input" min="1" placeholder="如 3" />
          </div>
          <div class="form-row">
            <label class="form-label">每组账户</label>
            <input v-model.number="manualForm.accounts_per_group" type="number" class="form-input" min="1" placeholder="如 5" />
          </div>
        </div>

        <button class="btn btn-primary" @click="addManualTask" :disabled="!manualForm.profile_key || !manualForm.drama_count">
          添加任务
        </button>
      </div>
    </section>

    <!-- 任务列表 -->
    <section class="content-section task-section">
      <div v-if="loading" class="loading-hint">加载中...</div>

      <div v-else-if="!tasks.length" class="empty-state">
        <div class="empty-icon">📭</div>
        <div class="empty-title">暂无任务</div>
        <div class="empty-desc">粘贴原始文本解析任务，或手动添加</div>
      </div>

      <TransitionGroup v-else name="task" tag="div" class="task-list">
        <div
          v-for="task in tasks"
          :key="task.id"
          class="task-card"
          :class="{ 'task-done': task.done }"
        >
          <div class="task-main">
            <label class="task-checkbox-label">
              <input
                type="checkbox"
                :checked="task.done"
                @change="toggleTask(task)"
                class="task-checkbox"
              />
              <span class="checkmark"></span>
            </label>

            <div class="task-body">
              <div class="task-top-row">
                <span v-if="task.person" class="person-tag">{{ task.person }}</span>
                <span class="task-title">{{ task.title }}</span>
                <button v-if="task.profile_key" class="go-build-btn" @click="goToBuild(task)" title="点击跳转到搭建控制台">
                  🚀 去搭建 →
                </button>
              </div>

              <!-- 结构化参数标签 -->
              <div v-if="hasParams(task)" class="task-params">
                <span v-if="task.params?.drama_count" class="param-tag param-drama">
                  📺 {{ task.params.drama_count }}部剧
                </span>
                <span v-if="task.params?.dramas_per_group" class="param-tag param-group">
                  📦 {{ task.params.dramas_per_group }}部/组
                </span>
                <span v-if="task.params?.accounts_per_group" class="param-tag param-account">
                  👤 {{ task.params.accounts_per_group }}账户/组
                </span>
                <span v-if="task.params?.material_count" class="param-tag param-material">
                  🎬 {{ task.params.material_count }}条素材
                </span>
                <span v-if="task.params?.ads_per_material" class="param-tag param-ad">
                  📢 {{ task.params.ads_per_material }}广告/素材
                </span>
                <span v-if="task.params?.test_days" class="param-tag param-days">
                  📅 测试{{ task.params.test_days }}天
                </span>
                <span v-if="task.params?.daily_budget" class="param-tag param-budget">
                  💰 日预算{{ task.params.daily_budget }}
                </span>
              </div>

              <!-- 搭建进度 -->
              <div v-if="task.build_count > 0 || task.build_total > 0" class="task-build-progress">
                <span class="build-progress-label">⚡ 搭建进度</span>
                <span class="build-progress-count">{{ task.build_count || 0 }} / {{ task.build_total || '?' }}</span>
                <div v-if="task.build_total > 0" class="mini-progress-track">
                  <div class="mini-progress-fill" :style="{ width: Math.min(100, ((task.build_count || 0) / task.build_total) * 100) + '%' }"></div>
                </div>
              </div>
            </div>

            <button
              class="btn-delete"
              @click="deleteTask(task)"
              title="删除任务"
            >✕</button>
          </div>
        </div>
      </TransitionGroup>

      <!-- 公共备注 -->
      <div v-if="publicNote" class="note-card">
        <div class="note-label">📝 公共备注</div>
        <div class="note-content">{{ publicNote }}</div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useUiStore } from '../stores/ui'

// ─── 日期相关 ───
const currentDate = ref(formatDate(new Date()))

function formatDate(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const displayDate = computed(() => {
  const [y, m, d] = currentDate.value.split('-')
  const weekDays = ['日', '一', '二', '三', '四', '五', '六']
  const dt = new Date(+y, +m - 1, +d)
  return `${y}年${m}月${d}日 周${weekDays[dt.getDay()]}`
})

const isToday = computed(() => currentDate.value === formatDate(new Date()))

function changeDate(offset) {
  const [y, m, d] = currentDate.value.split('-').map(Number)
  const dt = new Date(y, m - 1, d + offset)
  currentDate.value = formatDate(dt)
}

function goToday() {
  currentDate.value = formatDate(new Date())
}

// ─── 任务数据 ───
const tasks = ref([])
const publicNote = ref('')
const loading = ref(false)
const rawText = ref('')
const showManual = ref(false)
const manualForm = ref({
  profile_key: '',
  person: '',
  drama_count: null,
  dramas_per_group: null,
  accounts_per_group: null,
})
const parsing = ref(false)
const parseError = ref('')
const showFormatExample = ref(false)
const router = useRouter()
const uiStore = useUiStore()

// ─── 跳转搭建 ───
function goToBuild(task) {
  if (!task.profile_key) return
  // 根据 profile_key 设置模式
  if (task.profile_key.includes('激励')) {
    uiStore.setWorkMode('incentive')
  } else {
    uiStore.setWorkMode('normal')
  }
  router.push({ path: '/', query: { profile: task.profile_key } })
}

// ─── 参数检测 ───
function hasParams(task) {
  return task.params && Object.keys(task.params).length > 0
}

// ─── 进度统计 ───
const completedCount = computed(() => tasks.value.filter(t => t.done).length)
const progressPercent = computed(() =>
  tasks.value.length ? Math.round((completedCount.value / tasks.value.length) * 100) : 0
)

// ─── API 调用 ───
async function loadTasks() {
  loading.value = true
  try {
    const res = await window.pywebview.api.get_daily_tasks(currentDate.value)
    if (res && res.ok) {
      tasks.value = (res.tasks || []).map(t => ({ ...t, _expanded: false }))
      publicNote.value = res.note || ''
    } else {
      tasks.value = []
      publicNote.value = ''
    }
  } catch (e) {
    console.error('加载任务失败', e)
    tasks.value = []
    publicNote.value = ''
  } finally {
    loading.value = false
  }
}

async function parseTasks() {
  parsing.value = true
  parseError.value = ''
  try {
    const res = await window.pywebview.api.parse_daily_tasks(rawText.value, currentDate.value)
    if (res && res.ok) {
      tasks.value = (res.tasks || []).map(t => ({ ...t, _expanded: false }))
      publicNote.value = res.note || ''
      rawText.value = ''
    } else {
      parseError.value = '解析失败：' + (res.error || '未知错误')
    }
  } catch (e) {
    parseError.value = '解析失败：' + (e.message || e)
  } finally {
    parsing.value = false
  }
}

async function addManualTask() {
  const f = manualForm.value
  if (!f.profile_key || !f.drama_count) return
  try {
    const res = await window.pywebview.api.add_manual_daily_task(currentDate.value, {
      profile_key: f.profile_key,
      person: f.person || '',
      title: f.profile_key,
      drama_count: f.drama_count || 0,
      dramas_per_group: f.dramas_per_group || 0,
      accounts_per_group: f.accounts_per_group || 0,
    })
    if (res && res.ok) {
      await loadTasks()
      // 重置表单
      manualForm.value = { profile_key: '', person: '', drama_count: null, dramas_per_group: null, accounts_per_group: null }
      showManual.value = false
    }
  } catch (e) {
    console.error('添加任务失败', e)
  }
}

async function toggleTask(task) {
  task.done = !task.done
  try {
    await window.pywebview.api.toggle_daily_task(currentDate.value, task.id)
  } catch (e) {
    task.done = !task.done
    console.error('切换状态失败', e)
  }
}

async function deleteTask(task) {
  const idx = tasks.value.findIndex(t => t.id === task.id)
  if (idx === -1) return
  tasks.value.splice(idx, 1)
  try {
    await window.pywebview.api.delete_daily_task(currentDate.value, task.id)
  } catch (e) {
    console.error('删除失败', e)
    loadTasks() // rollback by reloading
  }
}

// ─── 生命周期 & 监听 ───
onMounted(loadTasks)
watch(currentDate, loadTasks)

// 监听搭建事件，自动刷新任务列表
function onBuildEvent(e) {
  if (isToday.value) {
    loadTasks()
  }
}
onMounted(() => {
  window.addEventListener('honguo:build-status', onBuildEvent)
  window.addEventListener('honguo:drama-completed', onBuildEvent)
})
onUnmounted(() => {
  window.removeEventListener('honguo:build-status', onBuildEvent)
  window.removeEventListener('honguo:drama-completed', onBuildEvent)
})
</script>

<style scoped>
/* ══════════════════════════════════════════════
   Dark Industrial Console — DailyTaskView
   bg #0c1222 · card #fffdf8 · surface #edf4f7
   border #d8d1c4 · text #273142 · text-2 #657386
   dim #8b958f · accent var(--c-accent, #d88900) · primary #2d7aed
   green #00d48a · red #ff4757
   ══════════════════════════════════════════════ */

/* ── 页面容器 ── */
.page-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px 16px 48px;
  font-family: var(--f-ui, system-ui, sans-serif);
  color: var(--c-text, #273142);
}

/* ── 头部 ── */
.page-header {
  margin-bottom: 20px;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 10px;
}

.date-nav {
  display: flex;
  align-items: center;
  gap: 8px;
}

.date-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  white-space: nowrap;
  color: var(--c-text, #273142);
}

.btn-icon {
  background: var(--c-card, #fffdf8);
  border: 1px solid var(--c-border, #d8d1c4);
  border-radius: var(--r-sm, 6px);
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 12px;
  color: var(--c-text-2, #657386);
  transition: var(--transition-fast, .15s ease);
}
.btn-icon:hover {
  background: var(--c-surface, #edf4f7);
  border-color: var(--c-accent, var(--c-accent, #d88900));
  color: var(--c-accent, var(--c-accent, #d88900));
}

.progress-info {
  font-size: 14px;
  color: var(--c-text-2, #657386);
  font-weight: 500;
}

/* ── 进度条 ── */
.progress-bar-track {
  width: 100%;
  height: 6px;
  background: var(--c-border, #d8d1c4);
  border-radius: 3px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: var(--c-accent, var(--c-accent, #d88900));
  border-radius: 3px;
  transition: width 0.35s ease;
  min-width: 0;
}

/* ── 通用按钮 ── */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  border-radius: var(--r-sm, 6px);
  border: 1px solid var(--c-border, #d8d1c4);
  background: var(--c-card, #fffdf8);
  color: var(--c-text, #273142);
  font-size: 13px;
  cursor: pointer;
  transition: var(--transition-fast, .15s ease);
}
.btn:hover {
  background: var(--c-surface, #edf4f7);
  border-color: var(--c-text-2, #657386);
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--c-primary, #2d7aed);
  color: #fff;
  border-color: var(--c-primary, #2d7aed);
}
.btn-primary:hover:not(:disabled) {
  filter: brightness(1.12);
}

.btn-ghost {
  background: transparent;
  border-color: transparent;
  color: var(--c-accent, var(--c-accent, #d88900));
  font-size: 12px;
}
.btn-ghost:hover {
  background: rgba(216, 137, 0, 0.08);
}

/* ── 解析区 ── */
.parse-section {
  margin-bottom: 20px;
}

.parse-card {
  background: var(--c-card, #fffdf8);
  border: 1px solid var(--c-border, #d8d1c4);
  border-radius: 12px;
  padding: 16px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.parse-card:focus-within {
  border-color: var(--c-accent, var(--c-accent, #d88900));
  box-shadow: 0 0 0 3px rgba(216, 137, 0, 0.08);
}

.parse-input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid var(--c-border, #d8d1c4);
  border-radius: var(--r-sm, 6px);
  background: var(--c-surface, #edf4f7);
  color: var(--c-text, #273142);
  font-size: 13px;
  font-family: var(--f-ui, system-ui, sans-serif);
  resize: vertical;
  line-height: 1.5;
}
.parse-input::placeholder {
  color: var(--c-dim, #8b958f);
}
.parse-input:focus {
  outline: none;
  border-color: var(--c-accent, var(--c-accent, #d88900));
  box-shadow: 0 0 0 2px rgba(216, 137, 0, 0.15);
}

.parse-actions {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.parse-error {
  color: var(--c-red, #ff4757);
  font-size: 12px;
}

/* ── 手动添加 ── */
.manual-section {
  margin-bottom: 20px;
}

.btn-outline {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  border-radius: var(--r-sm, 6px);
  border: 1px dashed var(--c-border, #d8d1c4);
  background: transparent;
  color: var(--c-text-2, #657386);
  font-size: 13px;
  cursor: pointer;
  transition: var(--transition-fast, .15s ease);
}
.btn-outline:hover {
  border-color: var(--c-accent, var(--c-accent, #d88900));
  color: var(--c-accent, var(--c-accent, #d88900));
  background: rgba(216, 137, 0, 0.04);
}

.manual-form {
  margin-top: 12px;
  background: var(--c-card, #fffdf8);
  border: 1px solid var(--c-border, #d8d1c4);
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-row-group {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.form-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--c-text-2, #657386);
}

.form-select,
.form-input {
  padding: 7px 10px;
  border: 1px solid var(--c-border, #d8d1c4);
  border-radius: var(--r-sm, 6px);
  background: var(--c-surface, #edf4f7);
  color: var(--c-text, #273142);
  font-size: 13px;
  font-family: var(--f-ui, system-ui, sans-serif);
}
.form-select:focus,
.form-input:focus {
  outline: none;
  border-color: var(--c-accent, var(--c-accent, #d88900));
  box-shadow: 0 0 0 2px rgba(216, 137, 0, 0.15);
}

.form-input::placeholder {
  color: var(--c-dim, #8b958f);
}

/* ── 任务列表 ── */
.task-section {
  min-height: 120px;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.task-card {
  background: var(--c-card, #fffdf8);
  border: 1px solid var(--c-border-s, #e7dfd1);
  border-radius: 12px;
  padding: 14px 16px;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  border-left: 4px solid var(--c-accent, var(--c-accent, #d88900));
}
.task-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md, 0 10px 28px rgba(72, 58, 36, 0.09));
}

.task-card.task-done {
  opacity: 0.75;
  border-left-color: var(--c-green, #00d48a);
}
.task-card.task-done .task-title {
  text-decoration: line-through;
  text-decoration-color: var(--c-dim, #8b958f);
  color: var(--c-dim, #8b958f);
}
.task-card.task-done .person-tag {
  opacity: 0.6;
}

.task-main {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

/* ── 自定义 Checkbox ── */
.task-checkbox-label {
  position: relative;
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  margin-top: 2px;
  cursor: pointer;
}
.task-checkbox {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}
.checkmark {
  display: block;
  width: 20px;
  height: 20px;
  border: 2px solid var(--c-border, #d8d1c4);
  border-radius: 4px;
  transition: var(--transition-fast, .15s ease);
}
.task-checkbox:checked + .checkmark {
  background: var(--c-green, #00d48a);
  border-color: var(--c-green, #00d48a);
}
.task-checkbox:checked + .checkmark::after {
  content: '';
  display: block;
  width: 5px;
  height: 10px;
  border: solid #fff;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
  margin: 1px auto 0;
}

.task-checkbox-label:focus-within .checkmark {
  outline: 2px solid var(--c-accent, var(--c-accent, #d88900));
  outline-offset: 2px;
}

/* ── 任务内容 ── */
.task-body {
  flex: 1;
  min-width: 0;
}

.task-top-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.person-tag {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  background: rgba(216, 137, 0, 0.1);
  color: var(--c-accent, #d88900);
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}

/* ── 去搭建按钮 ── */
.go-build-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 12px;
  border-radius: 6px;
  border: 1px solid var(--c-accent, var(--c-accent, #d88900));
  background: rgba(216, 137, 0, 0.08);
  color: var(--c-accent, var(--c-accent, #d88900));
  font-size: 12px;
  font-weight: 600;
  font-family: var(--f-ui, system-ui, sans-serif);
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}
.go-build-btn:hover {
  background: var(--c-accent, var(--c-accent, #d88900));
  color: #fff;
  transform: translateX(2px);
}
.go-build-btn:active {
  transform: scale(0.95);
}

.task-title {
  font-weight: 600;
  font-size: 14px;
  line-height: 1.5;
  color: var(--c-text, #273142);
  transition: color 0.2s, text-decoration 0.2s;
}

/* ── 结构化参数标签 (dark-friendly) ── */
.task-params {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.param-tag {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}

.param-drama {
  background: rgba(59, 130, 246, 0.12);
  color: #60a5fa;
}

.param-group {
  background: rgba(168, 85, 247, 0.12);
  color: #c084fc;
}

.param-account {
  background: rgba(0, 212, 138, 0.12);
  color: #00d48a;
}

.param-material {
  background: rgba(249, 115, 22, 0.12);
  color: #fb923c;
}

.param-ad {
  background: rgba(236, 72, 153, 0.12);
  color: #f472b6;
}

.param-days {
  background: rgba(20, 184, 166, 0.12);
  color: #2dd4bf;
}

.param-budget {
  background: rgba(216, 137, 0, 0.12);
  color: var(--c-accent, #d88900);
}

/* ── 搭建进度 ── */
.task-build-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding: 4px 12px;
  background: rgba(216, 137, 0, 0.06);
  border-radius: 8px;
  font-size: 12px;
}

.build-progress-label {
  color: var(--c-text-2, #657386);
  font-weight: 500;
}

.build-progress-count {
  color: var(--c-accent, var(--c-accent, #d88900));
  font-weight: 700;
  font-size: 14px;
}

/* ── 迷你进度条 ── */
.mini-progress-track {
  flex: 1;
  max-width: 80px;
  height: 4px;
  background: var(--c-border, #d8d1c4);
  border-radius: 2px;
  overflow: hidden;
}
.mini-progress-fill {
  height: 100%;
  background: var(--c-accent, var(--c-accent, #d88900));
  border-radius: 2px;
  transition: width 0.35s ease;
  position: relative;
  overflow: hidden;
}
.mini-progress-fill::after {
  content: '';
  position: absolute; inset: 0;
  background: linear-gradient(90deg, transparent 30%, rgba(255,255,255,0.25) 50%, transparent 70%);
  background-size: 200% 100%;
  animation: shimmer 2s infinite;
}
@keyframes shimmer {
  0% { background-position: -200% center; }
  100% { background-position: 200% center; }
}

/* ── 删除按钮 ── */
.btn-delete {
  flex-shrink: 0;
  background: none;
  border: none;
  color: var(--c-dim, #8b958f);
  font-size: 16px;
  cursor: pointer;
  padding: 6px 8px;
  min-width: 32px;
  min-height: 32px;
  border-radius: 4px;
  transition: var(--transition-fast, .15s ease);
}
.btn-delete:hover {
  color: var(--c-red, #ff4757);
  background: rgba(255, 71, 87, 0.1);
}

/* ── 公共备注 ── */
.note-card {
  margin-top: 16px;
  background: var(--c-card, #fffdf8);
  border: 1px solid var(--c-border, #d8d1c4);
  border-radius: 12px;
  padding: 14px 16px;
}

.note-label {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
  color: var(--c-text, #273142);
}

.note-content {
  font-size: 13px;
  color: var(--c-text-2, #657386);
  line-height: 1.6;
  white-space: pre-wrap;
}

/* ── 空状态 & 加载 ── */
.loading-hint {
  text-align: center;
  padding: 40px 0;
  color: var(--c-dim, #8b958f);
  font-size: 14px;
}

.empty-state {
  text-align: center;
  padding: 48px 0;
}
.empty-icon {
  font-size: 40px;
  margin-bottom: 12px;
  opacity: 0.7;
}
.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--c-text-2, #657386);
  margin-bottom: 6px;
}
.empty-desc {
  font-size: 13px;
  color: var(--c-dim, #8b958f);
}

/* ── 列表过渡动画 ── */
.task-enter-active,
.task-leave-active {
  transition: all 0.25s ease;
}
.task-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}
.task-leave-to {
  opacity: 0;
  transform: translateX(30px);
}

.format-hint {
  margin-top: 10px;
}

.format-hint-toggle {
  font-size: 12px;
  color: var(--c-accent, var(--c-accent, #d88900));
  cursor: pointer;
  user-select: none;
  padding: 4px 0;
}

.format-hint-toggle:hover {
  text-decoration: underline;
}

.format-example {
  margin-top: 8px;
  border: 1px solid var(--c-border, #d8d1c4);
  border-radius: 6px;
  overflow: hidden;
}

.format-code {
  background: var(--c-log-bg, #0f172a);
  color: var(--c-log-fg, #e2e8f0);
  padding: 12px 14px;
  margin: 0;
  font-family: var(--f-mono);
  font-size: 12px;
  line-height: 1.8;
  white-space: pre-wrap;
}

.format-note {
  padding: 8px 14px;
  margin: 0;
  font-size: 12px;
  color: var(--c-dim, #8b958f);
  background: var(--c-surface, #edf4f7);
}
</style>
