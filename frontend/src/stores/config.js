import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getConfig as getConfigApi, saveConfig as saveConfigApi } from '@/services/api'

export const useConfigStore = defineStore('config', () => {
  const config = ref(null)
  const loading = ref(false)

  async function loadConfig() {
    loading.value = true
    try {
      config.value = await getConfigApi()
    } catch (e) {
      console.error('加载配置失败:', e)
    } finally {
      loading.value = false
    }
  }

  async function saveConfig(cfg) {
    const res = await saveConfigApi(cfg)
    if (res.ok) {
      config.value = cfg
    }
    return res
  }

  function getProfiles() {
    if (!config.value) return []
    return Object.keys(config.value.profiles || {})
  }

  return { config, loading, loadConfig, saveConfig, getProfiles }
})
