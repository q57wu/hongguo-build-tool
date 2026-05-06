/**
 * 前端 API 服务层 - 封装 pywebview.api 调用
 * 统一错误处理、API 就绪等待
 */

// 等待 pywebview API 就绪（单例 Promise，避免重复轮询）
let _apiReady = null
export async function waitForApi(maxRetries = 25, interval = 200) {
  if (_apiReady) return _apiReady
  _apiReady = new Promise(async (resolve) => {
    for (let i = 0; i < maxRetries; i++) {
      if (window.pywebview?.api) { resolve(true); return }
      await new Promise(r => setTimeout(r, interval))
    }
    resolve(false)
  })
  return _apiReady
}

// 重置 API 就绪状态（首次失败后允许重试）
export function resetApiReady() {
  _apiReady = null
}

// 统一调用包装
async function callApi(method, ...args) {
  const ready = await waitForApi()
  if (!ready) throw new Error('pywebview API 未就绪')
  if (typeof window.pywebview.api[method] !== 'function') {
    throw new Error(`API 方法 ${method} 不存在`)
  }
  return await window.pywebview.api[method](...args)
}

// ═══ 配置管理 ═══
export async function getConfig() {
  const res = await callApi('get_config')
  // 兼容新结构 {ok, data, error} 与旧结构（直接返回 cfg）
  if (res && typeof res === 'object' && 'ok' in res && 'data' in res) {
    return res.data || {}
  }
  return res
}

export async function getRawConfig() {
  return callApi('get_raw_config')
}

export async function saveConfig(cfg) {
  return callApi('save_config', cfg)
}

export async function getProfiles() {
  return callApi('get_profiles')
}

export async function getProfile(key) {
  return callApi('get_profile', key)
}

export async function updateProfile(key, data) {
  return callApi('update_profile', key, data)
}

// ═══ 浏览器管理 ═══
export async function checkBrowser() {
  return callApi('check_browser')
}

export async function launchBrowser() {
  return callApi('launch_browser')
}

// ═══ 搭建控制 ═══
export async function startBuild(profileKey, { parallel = false, maxWorkers = 3 } = {}) {
  return callApi('start_build', profileKey, parallel, maxWorkers)
}

export async function stopBuild() {
  return callApi('stop_build')
}

export async function getPendingBuild() {
  return callApi('get_pending_build')
}

export async function resumeBuild() {
  return callApi('resume_build')
}

export async function dismissPendingBuild() {
  return callApi('dismiss_pending_build')
}

// ═══ 工具操作 ═══
export async function batchAssign(accountIdsText, dramasText, idsPerGroup, dramasPerGroup, materialIdsText = '', spacing = 1) {
  return callApi('batch_assign', accountIdsText, dramasText, idsPerGroup, dramasPerGroup, materialIdsText, spacing)
}

export async function generatePromoChain(dramaNames, directions) {
  return callApi('generate_promo_chain', dramaNames, directions)
}

export async function stopPromoChain() {
  return callApi('stop_promo_chain')
}

export async function splitPromoLinks(mode = 'normal', dramaFilter = null) {
  return callApi('split_promo_links', mode, dramaFilter || [])
}

export async function splitIncentiveLinks() {
  return callApi('split_incentive_links')
}

export async function searchMaterialPush(dramaNamesText, accountId) {
  return callApi('search_material_push', dramaNamesText, accountId)
}

export async function stopMaterialPush() {
  return callApi('stop_material_push')
}

export async function crawlMaterialIds(dramaNames, minCost = 1000, minCount = 6) {
  return callApi('crawl_material_ids', dramaNames, minCost, minCount)
}

export async function stopCrawlMaterial() {
  return callApi('stop_crawl_material')
}

export async function generateIncentiveChain(params) {
  return callApi('generate_incentive_chain', params)
}

export async function stopIncentiveChain() {
  return callApi('stop_incentive_chain')
}

export async function startIncentivePush(accountId, config) {
  return callApi('start_incentive_push', accountId, config)
}

export async function stopIncentivePush() {
  return callApi('stop_incentive_push')
}

export async function processIncentiveLinks(params) {
  return callApi('process_incentive_links', params)
}

// ═══ 数据查询 ═══
export async function getBuildRecords() {
  const res = await callApi('get_build_records')
  if (res && typeof res === 'object' && 'ok' in res && 'data' in res) {
    return res.data || {}
  }
  return res
}

export async function getMaterialHistory() {
  return callApi('get_material_history')
}

export async function deleteMaterialHistory(index) {
  return callApi('delete_material_history', index)
}

export async function clearMaterialHistory() {
  return callApi('clear_material_history')
}

// ═══ 剧单管理 ═══
export async function getDramaTitles() {
  return callApi('get_drama_titles')
}

export async function appendDramaTitles(titles) {
  return callApi('append_drama_titles', titles)
}

export async function addResultToProfile(profileKey, resultText) {
  return callApi('add_result_to_profile', profileKey, resultText)
}

export async function addIncentiveResultToProfile(profileKey, resultText) {
  return callApi('add_incentive_result_to_profile', profileKey, resultText)
}

// ═══ RTA 工具 ═══
export async function rtaSet(dramaType, aadvids) {
  return callApi('rta_set', dramaType, aadvids)
}

export async function stopRtaSet() {
  return callApi('stop_rta_set')
}

export async function rtaCheck(dramaType, aadvids) {
  return callApi('rta_check', dramaType, aadvids)
}

export async function stopRtaCheck() {
  return callApi('stop_rta_check')
}

