import { ref, onMounted, onUnmounted, nextTick } from 'vue'

export function useToolLogger(options = {}) {
  const logs = ref([])
  const running = ref(false)
  const logBox = ref(null)
  const autoScroll = ref(true)

  function onToolLog(e) {
    const msg = e.detail?.message || e.detail || ''
    logs.value.push(msg)
    if (options.onLog) options.onLog(msg, e)
    if (autoScroll.value) {
      nextTick(() => {
        if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
      })
    }
  }

  function onToolDone(e) {
    running.value = false
    if (options.onDone) options.onDone(e)
  }

  function onLogScroll() {
    if (!logBox.value) return
    const el = logBox.value
    autoScroll.value = el.scrollHeight - el.scrollTop - el.clientHeight < 40
  }

  onMounted(() => {
    window.addEventListener('honguo:tool-log', onToolLog)
    window.addEventListener('honguo:tool-done', onToolDone)
    if (logBox.value) logBox.value.addEventListener('scroll', onLogScroll)
  })

  onUnmounted(() => {
    window.removeEventListener('honguo:tool-log', onToolLog)
    window.removeEventListener('honguo:tool-done', onToolDone)
    if (logBox.value) logBox.value.removeEventListener('scroll', onLogScroll)
  })

  function bindLogBox(el) {
    logBox.value = el
    if (el) el.addEventListener('scroll', onLogScroll)
  }

  return { logs, running, logBox, autoScroll, bindLogBox }
}
