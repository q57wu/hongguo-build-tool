/**
 * 事件监听 composable：监听 Python 后端推送的自定义事件
 */
import { onMounted, onUnmounted } from 'vue'
import { useBuildStore } from '../stores/build'
import { useLogStore } from '../stores/log'

export function useBackendEvents() {
  const buildStore = useBuildStore()
  const logStore = useLogStore()

  function onLog(e) {
    logStore.append(e.detail)
  }

  function onBuildStatus(e) {
    buildStore.updateStatus(e.detail)
  }

  function onBuildProgress(e) {
    // 通过 updateStatus 统一更新，保持响应式追踪
    buildStore.updateStatus({ progress: e.detail })
  }

  onMounted(() => {
    window.addEventListener('honguo:log', onLog)
    window.addEventListener('honguo:build-status', onBuildStatus)
    window.addEventListener('honguo:build-progress', onBuildProgress)
  })

  onUnmounted(() => {
    window.removeEventListener('honguo:log', onLog)
    window.removeEventListener('honguo:build-status', onBuildStatus)
    window.removeEventListener('honguo:build-progress', onBuildProgress)
  })
}
