import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { startBuild as startBuildApi, stopBuild as stopBuildApi } from '@/services/api'

export const useBuildStore = defineStore('build', () => {
  // 状态
  const status = ref('idle') // idle | running | stopping | completed | error
  const profile = ref(null)
  const progress = ref({ step: 0, total: 0, message: '' })
  const error = ref(null)

  // 上次搭建使用的剧名清单（用于推广链分割过滤）
  const lastDramaNames = ref([])

  // 计算属性
  const isRunning = computed(() => status.value === 'running')
  const isStopping = computed(() => status.value === 'stopping')
  const canStart = computed(() => status.value === 'idle' || status.value === 'completed' || status.value === 'error')

  // 操作
  async function startBuild(profileKey, { parallel = false, maxWorkers = 3 } = {}) {
    const res = await startBuildApi(profileKey, { parallel, maxWorkers })
    if (res.ok) {
      status.value = 'running'
      profile.value = profileKey
      error.value = null
    }
    return res
  }

  async function stopBuild() {
    await stopBuildApi()
    status.value = 'stopping'
  }

  function updateStatus(data) {
    if (data.status) status.value = data.status
    if (data.progress) progress.value = data.progress
    if (data.message) {
      error.value = data.message
      // 把错误信息也放到 progress 中以便状态栏显示
      progress.value = { ...progress.value, message: data.message }
    }
    if (data.status === 'completed' || data.status === 'error') {
      profile.value = null
    }
  }

  /** 记录本次搭建的剧名清单（由搭建页在提交时调用） */
  function setLastDramaNames(names) {
    lastDramaNames.value = names.filter(n => n && n.trim())
  }

  function reset() {
    status.value = 'idle'
    profile.value = null
    progress.value = { step: 0, total: 0, message: '' }
    error.value = null
  }

  return {
    status, profile, progress, error,
    isRunning, isStopping, canStart,
    lastDramaNames,
    startBuild, stopBuild, updateStatus, reset, setLastDramaNames,
  }
})
