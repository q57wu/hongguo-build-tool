import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUiStore = defineStore('ui', () => {
  // 工作台模式: 'normal' | 'incentive'
  const workMode = ref('normal')

  function setWorkMode(mode) {
    workMode.value = mode
  }

  function toggleMode() {
    workMode.value = workMode.value === 'normal' ? 'incentive' : 'normal'
  }

  // 推广链分割 → 链接分配 的待填数据
  // 格式: { rawData: string }，为 null 表示没有待填
  const pendingLinkData = ref(null)

  function setPendingLinkData(rawData, sourceKey) {
    pendingLinkData.value = { rawData, sourceKey: sourceKey || null }
  }

  function consumePendingLinkData() {
    const data = pendingLinkData.value
    pendingLinkData.value = null
    return data
  }

  // 素材爬取 → 素材推送 的待填剧名数据
  const pendingCrawlDramas = ref(null)

  function setPendingCrawlDramas(dramaNames) {
    pendingCrawlDramas.value = dramaNames
  }

  function consumePendingCrawlDramas() {
    const data = pendingCrawlDramas.value
    pendingCrawlDramas.value = null
    return data
  }

  return { workMode, setWorkMode, toggleMode, pendingLinkData, setPendingLinkData, consumePendingLinkData, pendingCrawlDramas, setPendingCrawlDramas, consumePendingCrawlDramas }
})
