<template>
  <div class="log-panel" :class="{ expanded: isExpanded }">
    <!-- 日志头部 -->
    <div class="log-header">
      <div class="log-title-group">
        <span class="log-title">运行日志</span>
        <span class="log-count" v-if="logStore.logs.length">{{ logStore.logs.length }} 条</span>
      </div>
      <div class="log-actions">
        <button class="log-btn" @click="copyLogs" title="复制">📋</button>
        <button class="log-btn" @click="logStore.clear()" title="清空">🗑️</button>
        <button class="log-btn" @click="isExpanded = !isExpanded"
                :aria-label="isExpanded ? '收起日志' : '展开日志'"
                :aria-pressed="isExpanded">
          {{ isExpanded ? '⬇️' : '⬆️' }}
        </button>
      </div>
    </div>

    <!-- 日志内容 -->
    <div class="log-body" ref="logBody">
      <div v-if="logStore.logs.length === 0" class="log-empty">
        <span class="log-empty-icon">📝</span>
        <span>等待运行日志...</span>
      </div>
      <div
        v-for="entry in logStore.logs"
        :key="entry.id"
        class="log-line"
        :class="[`log-${entry.level}`, isBanner(entry.message) ? 'log-banner' : '']"
      >
        <span class="log-time">{{ formatTime(entry.time) }}</span>
        <span class="log-msg">{{ entry.message }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useLogStore } from '../stores/log'

const logStore = useLogStore()
const logBody = ref(null)
const isExpanded = ref(false)
const autoScroll = ref(true)

// 检测用户是否手动上滑：如果滚动位置离底部超过 40px 则关闭自动滚动
function onScroll() {
  if (!logBody.value) return
  const el = logBody.value
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
  autoScroll.value = atBottom
}

onMounted(() => {
  if (logBody.value) {
    logBody.value.addEventListener('scroll', onScroll)
  }
})

onBeforeUnmount(() => {
  if (logBody.value) {
    logBody.value.removeEventListener('scroll', onScroll)
  }
})

// 自动滚动到底部
watch(() => logStore.logs.length, () => {
  if (autoScroll.value) {
    nextTick(() => {
      if (logBody.value) {
        logBody.value.scrollTop = logBody.value.scrollHeight
      }
    })
  }
})

function formatTime(ts) {
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString('zh-CN', { hour12: false })
}

// Banner 行识别（含 ╔ ╚ ┌ └ 框线字符，或以 🎬 📦 开头）
function isBanner(msg) {
  return /[╔╚╗╝┌└┐┘│║]/.test(msg) || /^[\s\n]*(🎬|📦)/.test(msg)
}

function copyLogs() {
  const text = logStore.logs.map(e => `[${formatTime(e.time)}] ${e.message}`).join('\n')
  navigator.clipboard.writeText(text)
}
</script>

<style scoped>
.log-panel {
  flex: 1;
  min-height: 200px;
  margin-top: 12px;
  background: var(--c-log-bg);
  border-radius: var(--r-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all 0.2s ease;
}

.log-panel.expanded {
  position: fixed;
  top: max(20px, env(safe-area-inset-top, 20px));
  left: 240px;
  right: 20px;
  bottom: 20px;
  z-index: 100;
  margin: 0;
  border-radius: var(--r-lg);
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  flex-shrink: 0;
}

.log-title-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.log-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-log-fg);
}

.log-count {
  font-size: 10px;
  color: var(--c-log-dim);
  background: rgba(255,255,255,0.06);
  padding: 2px 8px;
  border-radius: 10px;
}

.log-actions {
  display: flex;
  gap: 4px;
}

.log-btn {
  background: none;
  border: none;
  padding: 4px 6px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  opacity: 0.6;
  transition: opacity 0.15s;
}

.log-btn:hover {
  opacity: 1;
  background: rgba(255,255,255,0.06);
}

.log-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 16px;
  font-family: var(--f-mono);
  font-size: 12px;
  line-height: 1.7;
  user-select: text;
  -webkit-user-select: text;
  cursor: text;
}

.log-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--c-log-dim);
  font-family: var(--f-ui);
  gap: 8px;
}

.log-empty-icon {
  font-size: 28px;
  opacity: 0.4;
}

.log-line {
  display: flex;
  gap: 12px;
  padding: 1px 0;
}

.log-time {
  color: var(--c-log-dim);
  flex-shrink: 0;
  font-size: 11px;
}

.log-msg {
  color: var(--c-log-fg);
  word-break: break-all;
}

/* 日志级别颜色 */
.log-info .log-msg { color: var(--c-log-fg); }
.log-success .log-msg { color: var(--c-green); }
.log-warn .log-msg { color: var(--c-orange); }
.log-error .log-msg { color: var(--c-red); }

/* Banner 行（新组 / 新剧）醒目样式 */
.log-banner {
  margin-top: 6px;
  margin-bottom: 2px;
  white-space: pre;
}
.log-banner .log-msg {
  color: #7dd3fc;
  font-weight: 600;
  font-size: 12.5px;
  letter-spacing: 0.02em;
  white-space: pre;
}
.log-banner .log-time {
  opacity: 0;   /* banner 行时间戳不显示，不影响布局 */
  pointer-events: none;
  user-select: none;
}

/* 滚动条 */
.log-body::-webkit-scrollbar {
  width: 5px;
}
.log-body::-webkit-scrollbar-track {
  background: transparent;
}
.log-body::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.1);
  border-radius: 3px;
}
</style>
