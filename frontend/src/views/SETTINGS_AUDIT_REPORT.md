# 红果搭建 - 前端 Views 文件设置项调查报告

## 概述
已扫描 D:\红果搭建\gui\frontend\src\views\ 下的所有 13 个 Vue 文件，以搜索关键设置项：
- `idsPerGroup` （每组账户数）
- `dramasPerGroup` （每组剧数）
- `spacing` （行间距）
- localStorage/sessionStorage 缓存逻辑

---

## 关键发现

### 1️⃣ **设置项使用分布**

| 页面文件 | idsPerGroup | dramasPerGroup | spacing | 默认值 | 缓存机制 |
|---------|-----------|---------------|--------|--------|---------|
| **IncentiveLinkView.vue** | ✅ | ❌ | ✅ | `idsPerGroup: 6, spacing: 1` | ❌ 无 |
| **JuMingView.vue** | ✅ | ✅ | ✅ | `idsPerGroup: 6, dramasPerGroup: 3, spacing: 1` | ❌ 无 |
| **IncentiveChainView.vue** | ❌ | ❌ | ❌ | - | ❌ 无 |
| **PromoChainView.vue** | ❌ | ❌ | ❌ | - | ❌ 无 |
| **IncentiveSplitView.vue** | ❌ | ❌ | ❌ | - | ❌ 无 |
| **PromoSplitView.vue** | ❌ | ❌ | ❌ | - | ❌ 无 |
| **CrawlMaterialView.vue** | ❌ | ❌ | ❌ | - | ❌ 无 |
| **MaterialPushView.vue** | ❌ | ❌ | ❌ | - | ❌ 无 |
| **IncentivePushView.vue** | ❌ | ❌ | ❌ | - | ❌ 无 |
| 其他 7 个文件 | ❌ | ❌ | ❌ | - | ❌ 无 |

### 2️⃣ **localStorage / sessionStorage 使用情况**

**搜索结果：❌ 完全没有使用**

在所有 13 个 .vue 文件中，**没有找到任何**：
- `localStorage`
- `sessionStorage`
- `缓存`、`persist`、`cache` 等相关逻辑

---

## 详细信息

### 📋 IncentiveLinkView.vue（激励链接分配）

**所在位置**：行 68-69

```javascript
const idsPerGroup = ref(6)      // 每组账户数，默认值：6
const spacing = ref(1)           // 行间距，默认值：1
```

**参数说明**：
- `idsPerGroup`：控制分配结果中每组包含多少个账户 ID
  - UI 选项：number input，最小值 1
  - 传递给后端：`ids_per_group`
  
- `spacing`：控制输出结果的行间距
  - UI 选项：下拉菜单，可选值 0, 1, 2, 3
  - 传递给后端：`spacing`

**使用方式**：
```javascript
// 处理函数 (行 77-83)
const res = await window.pywebview.api.process_incentive_links({
  ids_per_group: idsPerGroup.value,  // 6
  spacing: spacing.value,             // 1
})
```

---

### 📋 JuMingView.vue（剧名链接整理）

**所在位置**：行 104-106

```javascript
const idsPerGroup = ref(6)      // 每组ID数，默认值：6
const dramasPerGroup = ref(3)   // 每组剧数，默认值：3
const spacing = ref(1)           // 行间距，默认值：1
```

**参数说明**：
- `idsPerGroup`：每个账户组的数量
  - UI 标签："每组ID数"
  - number input，最小值 1
  
- `dramasPerGroup`：每个账户组对应的短剧数量
  - UI 标签："每组剧数"
  - number input，最小值 1
  
- `spacing`：输出行间距
  - UI 选项：下拉菜单 0/1/2/3

**使用方式**：
```javascript
// 批量分配函数 (行 114-118)
const res = await window.pywebview.api.batch_assign(
  accountIds.value,
  dramaData.value,
  idsPerGroup.value,      // 6
  dramasPerGroup.value,   // 3
  materialIds.value,
  spacing.value           // 1
)
```

---

### ⚙️ 其他页面的配置

#### IncentiveChainView.vue（激励推广链生成）
- **参数**：`count`（执行次数）, `suffix`（方向后缀）
- **默认值**：`count: 10, suffix: '每留'`
- **没有** idsPerGroup / spacing 等相关配置

#### PromoChainView.vue（推广链生成）
- **参数**：`dramaNames`（剧名）, `taskOptions`（方向复选框）
- **没有** 数据分组配置

#### IncentiveSplitView.vue / PromoSplitView.vue（链接分割）
- **功能**：处理已有数据的拆分
- **没有** 参数化的分组配置，使用预定义的分组逻辑

#### CrawlMaterialView.vue（爬取素材）
- **参数**：`minCost`（最低消耗），`minCount`（最少集数）
- **没有** 账户分组配置

#### MaterialPushView.vue（素材推送）
- **参数**：`platform`（平台）, `accountId`（广告账户）
- **没有** 分组配置

---

## 🔍 缓存机制调查

### 搜索范围
✅ 已搜索关键词：
- `localStorage`
- `sessionStorage`
- `Storage`
- `缓存`
- `persist`

### 结论
**❌ 所有页面均不使用任何形式的客户端缓存**

说明：
1. **所有参数值都是易失的**（volatile）- 刷新页面即丢失
2. **没有持久化机制** - 用户每次使用需要重新输入参数
3. **后端可能有存储** - 设置项可能仅在前端临时存储，后端处理结果

---

## 💡 建议

### 如果需要缓存设置，可考虑添加：

**方案 A：localStorage（简单）**
```javascript
// 保存
localStorage.setItem('pageSettings', JSON.stringify({
  idsPerGroup: 6,
  dramasPerGroup: 3,
  spacing: 1
}))

// 恢复
const saved = localStorage.getItem('pageSettings')
if (saved) {
  const settings = JSON.parse(saved)
  idsPerGroup.value = settings.idsPerGroup
  dramasPerGroup.value = settings.dramasPerGroup
  spacing.value = settings.spacing
}
```

**方案 B：Pinia 状态管理（推荐）**
- 创建 `stores/settings.ts` 管理全局设置
- 配合 localStorage 实现持久化
- 支持跨页面共享配置

**方案 C：服务端配置**
- 后端保存用户偏好设置
- 页面加载时自动同步

---

## 📊 文件清单

| 文件名 | 文件大小 | 有设置项 | 有缓存 |
|-------|---------|---------|-------|
| IncentiveLinkView.vue | 6.1 KB | ✅ | ❌ |
| JuMingView.vue | 9.3 KB | ✅ | ❌ |
| IncentiveChainView.vue | 3.8 KB | ❌ | ❌ |
| PromoChainView.vue | 4.4 KB | ❌ | ❌ |
| IncentiveSplitView.vue | 4.5 KB | ❌ | ❌ |
| PromoSplitView.vue | 4.7 KB | ❌ | ❌ |
| CrawlMaterialView.vue | 5.9 KB | ❌ | ❌ |
| MaterialPushView.vue | 6.0 KB | ❌ | ❌ |
| IncentivePushView.vue | 3.7 KB | ❌ | ❌ |
| DashboardView.vue | 8.9 KB | ❌ | ❌ |
| HistoryView.vue | 4.6 KB | ❌ | ❌ |
| RecordsView.vue | 4.6 KB | ❌ | ❌ |
| SettingsView.vue | 15.4 KB | ❌ | ❌ |

---

## 总结

✅ **已找到的设置项**：
- `idsPerGroup` - 在 **IncentiveLinkView** 和 **JuMingView** 中使用
- `dramasPerGroup` - 仅在 **JuMingView** 中使用
- `spacing` - 在 **IncentiveLinkView** 和 **JuMingView** 中使用

❌ **缓存情况**：
- **没有任何页面使用 localStorage 或 sessionStorage**
- 所有设置都是单次会话内的临时值
- 刷新页面后参数值会重置为默认值

