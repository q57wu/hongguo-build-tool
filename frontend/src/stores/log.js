import { defineStore } from 'pinia'
import { ref, nextTick } from 'vue'

export const useLogStore = defineStore('log', () => {
  const logs = ref([])
  const maxLogs = 2000
  let buffer = []
  let timer = null

  function append(entry) {
    buffer.push({
      id: Date.now() + Math.random(),
      message: entry.message,
      level: entry.level || 'info',
      time: entry.time || Date.now() / 1000,
    })

    // 50ms 聚合渲染，防止高频日志卡顿
    if (!timer) {
      timer = setTimeout(() => {
        logs.value.push(...buffer)
        // 超出上限则截断
        if (logs.value.length > maxLogs) {
          logs.value = logs.value.slice(-maxLogs)
        }
        buffer = []
        timer = null
      }, 50)
    }
  }

  function clear() {
    logs.value = []
    buffer = []
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  // 组件卸载或 store 销毁时：刷新未提交的缓冲，避免内存泄漏
  function flushBuffer() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
    if (buffer.length) {
      logs.value.push(...buffer)
      if (logs.value.length > maxLogs) {
        logs.value = logs.value.slice(-maxLogs)
      }
      buffer = []
    }
  }

  return { logs, append, clear, flushBuffer }
})
