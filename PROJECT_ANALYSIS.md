# 红果搭建工具 - 完整项目分析

**项目名称**: 红果搭建工具 (Hongguo Build Console)  
**类型**: 自动化广告搭建工具  
**主要技术**: Tkinter/CustomTkinter GUI + Playwright 浏览器自动化  
**目标平台**: 安卓 & IOS + 短剧广告投放平台  
**版本**: v1.0

---

## 📋 目录结构

```
gui/
├── 红果搭建工具.py              # 主程序（7894行）
├── test_split.py                # 推广链拆分测试脚本
├── requirements.txt             # 依赖列表
├── config.json                  # 配置文件（包含账户、剧名、链接等）
├── config-副本20260429100742.json  # 配置备份
├── build_records.json           # 构建记录统计
├── material_history.json        # 素材使用历史
├── judan_cache.txt              # 巨单缓存
├── split_error.log              # 拆分错误日志
├── README.md                    # 项目说明
├── 使用说明.txt                  # 详细使用指南
├── LICENSE                      # MIT许可证
├── assets/
│   └── about_qr.jpg             # 二维码资源
├── output/                      # 输出目录（Excel统计表）
├── build/                       # PyInstaller构建文件
└── __pycache__/                 # Python缓存
```

---

## 🔧 依赖清单

```
playwright    # 浏览器自动化框架（Chromium）
openpyxl      # Excel读写
customtkinter # 现代化Tkinter界面库
```

**Python要求**: 3.10+

---

## 🏗️ 架构设计

### 1. 配置系统 (Config Management)

**核心文件**: `config.json`

```json
{
  "common": {
    "cdp_endpoint": "http://localhost:9222",    // Chrome DevTools Protocol 调试端口
    "drama_titles": [...]                       // 剧名库（支持快速查询）
  },
  "profiles": {
    "安卓-每留": {
      "strategy": "安卓-每留",
      "material_account_id": "1855367293890569",  // 素材账户ID
      "audience_keyword": "红果通用",             // 定向包关键词
      "monitor_btn_text": "选择分包和链接组",    // UI按钮文本（平台差异）
      "name_prefix": "安卓-站内-短剧-每留",      // 项目名前缀
      "wait_scale": 0.6,                         // 等待时间比例
      "groups": [...]                            // 账户/剧名/链接分组
    },
    // ... 其他3种配置（安卓-七留, IOS-每留, IOS-七留）
    // + 激励视频配置（安卓-激励每留, 安卓-激励七留）
  }
}
```

**配置层级**:
- `PROFILES` (内置默认)
  - ↓ 覆盖
- `config.json` (用户配置)
  - ↓ 合并
- `ALL_PROFILES` (运行时活跃配置)

---

### 2. 关键类型定义

#### 配置参数 (6种组合)

| 名称 | Platform | Retention | Material Account | Audience | Wait Scale | Mode |
|------|----------|-----------|------------------|----------|-----------|------|
| 安卓-每留 | 安卓 | 每留(0.6x) | 1855367293890569 | 红果通用 | 0.6 | Normal |
| 安卓-七留 | 安卓 | 七留(1.0x) | 1855367293890569 | 红果通用 | 1.0 | Normal |
| IOS-每留 | IOS | 每留(0.6x) | 1859509275615367 | IOS定向 | 0.6 | Normal |
| IOS-七留 | IOS | 七留(1.0x) | 1859509275615367 | IOS定向 | 1.0 | Normal |
| 安卓-激励每留 | 安卓 | 每留(0.6x) | 1855641147536460 | 通用激励 | 0.6 | Incentive |
| 安卓-激励七留 | 安卓 | 七留(1.0x) | 1855641147536460 | 通用激励 | 1.0 | Incentive |

#### 数据结构

```python
# 剧名数据格式
_empty_drama() = {
    "name": str,              # 短剧名
    "click": str,             # 点击监测链接
    "show": str,              # 展示监测链接
    "video": str,             # 视频播放监测链接
    "material_ids": [str]     # 素材ID列表
}

# 分组数据格式
_empty_group() = {
    "account_ids": [str],     # 投放账户ID（多个）
    "dramas": [drama],        # 该组内的剧名列表
    "group_name": str,        # 激励模式特有：组名
    "click_url": str,         # 激励模式特有：点击链接
    "show_url": str,          # 激励模式特有：展示链接
    "play_url": str           # 激励模式特有：播放链接
}
```

---

## 💾 数据持久化

### 4个JSON文件

1. **config.json** - 主配置（账户、链接、剧名）
   - 格式检查、版本兼容处理
   - 支持增量编辑

2. **build_records.json** - 构建统计
   ```json
   {
     "2026-04-30": {
       "accounts": 15,    // 今日账户数
       "projects": 45     // 今日项目数
     }
   }
   ```

3. **material_history.json** - 素材使用追踪
   ```json
   [
     {"date": "0430", "name": "素材ID1"},
     {"date": "0430", "name": "素材ID2"}
   ]
   ```

4. **build_records.json** 
   - 每日构建统计

---

## 🎯 核心功能模块

### A. 短剧单本搭建 (Normal Build)

**流程**: 浏览器自动化 → 平台表单填充 → 素材选择 → 项目提交

**关键步骤** (按执行顺序):

1. **step_select_strategy()** 
   - 选择广告策略（平台下拉）

2. **step_select_media_accounts()** 
   - 多账户选择（通过弹窗列表）

3. **step_link_product()** 
   - 链接产品（选择短剧）
   - 支持模糊匹配剧名

4. **step_fill_monitor_links()** 
   - 填充3条监测链接（点击/展示/视频）
   - 自动分类URL类型

5. **step_select_audience_package()** 
   - 选择定向包（按关键词搜索）

6. **step_fill_project_name()** 
   - 填充项目名（前缀 + 剧名）

7. **step_fill_ad_name()** 
   - 填充广告名（时间 + 剧名）

8. **step_pick_media_materials()** 
   - 素材选择（2种模式）
   - **按ID模式**: 精确匹配素材
   - **按关键词模式**: 名称模糊搜索 + 自动分页

9. **step_submit_and_close()** 
   - 提交表单 + 关闭弹窗

**核心算法: 素材匹配**

```python
def is_valid_material_name(drama_name, material_name):
    """
    判断素材是否属于该剧
    规则:
    1. 提取剧名中的中文段
    2. 规范化素材名 (去标点、小写)
    3. 检查是否包含完整段落
    4. 支持续集识别 (第1部/第2部)
    """
```

---

### B. 激励视频搭建 (Incentive Build)

**流程**: 激励平台 → 链接管理 → 多页面轮询 → 素材推送

**3个独立子系统**:

#### 1. run_build_incentive()
- 基础搭建（激励素材账户）
- 流程与Normal相同，但账户固定

#### 2. run_incentive_promo_chain()
- 推广链轮询创建
- **循环流程**: 
  - 每轮创建指定数量项目
  - 重复N轮
  - 自动页面刷新

#### 3. run_incentive_push()
- 素材推送
- **读取规则**:
  ```javascript
  // 页面JS注入：提取素材列表
  const nodes = Array.from(document.querySelectorAll(tags.join(',')));
  // 标签: [data-module-id], [data-push-type], 等
  ```

---

## 🎨 GUI 模块架构

使用 **CustomTkinter** 构建现代化界面

### 颜色主题
```python
C_BG = "#f8fafc"              # 背景（亮蓝灰）
C_CARD = "#ffffff"            # 卡片
C_PRIMARY = "#3b82f6"         # 主蓝色
C_ACCENT = "#10b981"          # 强调绿色
C_TEXT = "#1e293b"            # 文字
C_DIM = "#94a3b8"             # 淡化
C_RED = "#ef4444"             # 错误红
```

### 11个主要类

| 类名 | 功能 |
|------|------|
| **BuildApp** | 主窗口（960x680，可扩展） |
| **JuMingToolFrame** | 剧名链接整理（2个TAB） |
| **PromotionChainToolFrame** | 推广链管理 |
| **PromotionSplitToolFrame** | 推广链拆分（按配置） |
| **IncentivePromotionSplitToolFrame** | 激励链拆分 |
| **SearchDramaMaterialPushToolFrame** | 素材搜索 & 推送 |
| **IncentivePromoChainToolFrame** | 激励推链 |
| **IncentivePushToolFrame** | 激励素材推送 |
| **IncentiveLinkToolFrame** | 激励链接管理 |
| **MaterialHistoryFrame** | 素材历史统计 |
| **BuildRecordFrame** | 构建记录统计 |
| **SettingsFrame** | 设置面板 |

### 主界面布局

```
┌─────────────────────────────────────────┐
│ 🍎 红果搭建工具        ⚙ 设置    ● 就绪│  ← Header (64px)
├─────────────────────────────────────────┤
│                                         │
│ ┌─ 构建配置 ────────────────────────┐  │
│ │ PLATFORM: [安卓] [IOS]           │  │
│ │ RETENTION: [每留] [七留]         │  │
│ │ MODE: [普通] [激励]              │  │
│ │                    [停止] [开始] │  │
│ └─────────────────────────────────────┘  │
│                                         │
│ ┌─ 运行日志 ─────────────────────────┐  │
│ │ ● ● ● build.log  [清空]         │  │
│ │                                   │  │
│ │ [彩色日志输出区 - 实时动态]       │  │
│ │                                   │  │
│ │                                   │  │
│ └─────────────────────────────────────┘  │
│ v1.0 · 安卓 + IOS · 七留 + 每留   Ready │  ← Footer (30px)
└─────────────────────────────────────────┘
```

---

## 🔄 浏览器自动化逻辑

### 关键函数库

**等待机制**:
```python
wait_loading_gone(popup, container)        # 等待加载器消失
wait_locator_ready(popup, locator)         # 等待元素可见
wait_idle(target, network=True)            # 等待网络空闲
wait_small(popup, ms=300)                  # 短暂延迟（平滑过渡）
```

**交互操作**:
```python
safe_click(popup, locator)                 # 安全点击（含重试）
safe_select_option(popup, trigger, text)   # 选择下拉菜单
click_top_confirm(popup, scope)            # 确认按钮（栈式管理）
```

**DOM查询**:
```python
get_visible_layer(popup)                   # 获取最上层弹窗
get_visible_drawer(popup)                  # 获取侧滑抽屉
scroll_wrap_to_bottom(popup, wrap)         # 滚动到底部
scroll_to_module(popup, wrap, module_id)   # 滚动到指定模块
```

**素材分页**:
```python
_get_material_total(pane)                  # 总页数
_get_active_material_page(pane)            # 当前页
_has_next_material_page(pane)              # 是否有下一页
_go_to_next_material_page(popup)           # 翻页
_find_material_card_on_current_page()      # 搜索素材
```

---

## 📊 辅助工具

### 1. 推广链拆分 (test_split.py)

**功能**: 处理 Excel 推广统计表
- **输入**: `推广链统计_*.xlsx`
- **分类**: 按配置分组（IOS-每留, IOS-七留, Android-每留, Android-七留）
- **输出**: `_processed.xlsx`
- **保留列**: [1, 7, 8, 9, 10, 11]（指定的关键数据列）

---

### 2. 剧名和素材匹配

**内置匹配引擎**:

```python
def _normalize_material_text(text):
    """
    规范化素材名
    - 去标点
    - 去空白
    - 转小写
    """

def _material_name_has_exact_drama_segment(drama, material):
    """
    检查素材是否包含剧名的完整中文段
    - 提取连续中文字符串
    - 逐段匹配
    """

def extract_mmdd(name):
    """从素材名提取日期标记 (MMDD)"""
```

---

## 📝 日志系统

**日志器设置**:
```python
def setup_logger(log_dir: Path):
    """
    创建标准化logger
    - 格式: [时间] [级别] 消息
    - 输出: 文件 + GUI同步
    - 颜色标签: success, error, warning, info
    """
```

**日志位置**:
- 每个配置的 `logs/` 目录
- 文件名: `搭建_YYYYMMDD_HHMMSS.log`

---

## ⚙️ 配置参数详解

### 平台差异

| 参数 | 安卓 | IOS |
|------|------|-----|
| 素材账户ID | 1855367293890569 | 1859509275615367 |
| 定向包关键词 | "红果通用" | "IOS定向" |
| 监测按钮 | "选择分包和链接组" | "选择链接组" |

### 留存差异

| 参数 | 七留 | 每留 |
|------|------|------|
| wait_scale | 1.0 | 0.6 |
| 含义 | 标准等待 | 加速等待 |

---

## 🔐 安全性 & 错误处理

**自定义异常**:
```python
class AccountsMissingError(Exception):
    """媒体账户缺失"""
    
class StopRequested(Exception):
    """用户停止请求"""
```

**关键校验**:
```python
def check_stop(stop_event):
    """检查停止信号，抛出异常中断"""
```

---

## 🚀 执行流程

### 启动序列

1. **程序加载** (main)
   ```python
   migrate_ids_txt_to_config()     # 迁移旧ids.txt→config.json
   init_data_dirs()                # 初始化日志目录
   app = BuildApp()
   ```

2. **配置初始化** (BuildApp.__init__)
   ```python
   load_config()                   # 读取config.json
   _build_ui()                     # 构建GUI
   _poll_log()                     # 启动日志轮询
   ```

3. **点击「开始搭建」**
   ```python
   _on_start() 
   → 获取profile_key (平台+留存+模式)
   → 启动后台线程 run_build() 或 run_build_incentive()
   → GUI解锁「停止」按钮
   ```

4. **后台构建线程**
   ```python
   run_build(profile_key)
   ├── 连接浏览器 (CDP端口 9222)
   ├── 遍历config.json中的groups
   │  ├── 遍历每个account_id
   │  │  ├── 遍历每个drama
   │  │  │  ├── 执行9个step函数
   │  │  │  └── 日志队列push log_callback
   │  │  └── wait_return_to_main_after_material()
   │  └── 继续下一group
   ├── 记录成功统计 record_build_success()
   └── 线程结束
   ```

5. **日志轮询** (_poll_log)
   ```python
   while True:
       try:
           msg = log_queue.get_nowait()
           self.log_text.insert(log, msg, tags=...)
       except queue.Empty:
           pass
   ```

---

## 📌 关键配置点

### Chrome DevTools Protocol (CDP)

**启动命令**:
```bash
chrome.exe --remote-debugging-port=9222
```

**配置**:
```json
"cdp_endpoint": "http://localhost:9222"
```

**用途**: 无头浏览器控制 + 调试协议通信

---

### 数据文件格式 (ids.txt - 已废弃，迁移至config.json)

**原始格式**:
```
账户ID1
账户ID2

剧名

点击监测链接
展示监测链接
视频播放监测链接

素材ID1 素材ID2 素材ID3

===

（下一组）
```

**激励格式**:
```
组1

账户ID1
账户ID2

http://... (click)
http://... (view)
http://... (effective_play)
```

---

## 🔧 扩展点

### 1. 新增平台配置

在 `PROFILES` 字典中添加:
```python
PROFILES["新平台-七留"] = dict(
    strategy="新平台-七留",
    material_account_id="...",
    audience_keyword="...",
    monitor_btn_text="...",
    name_prefix="...",
    ids_file=Path("..."),
    log_dir=Path("..."),
    wait_scale=1.0,
)
```

### 2. 新增GUI工具

继承 `ctk.CTkFrame`:
```python
class MyToolFrame(ctk.CTkFrame):
    def __init__(self, master, ...):
        super().__init__(master, fg_color=C_BG)
        self._build_ui()
```

### 3. 新增自动化步骤

```python
def step_xxx(popup, ..., logger, W):
    """
    popup: playwright Page object
    logger: logging.Logger
    W: WaitTimes instance
    """
    logger.info("执行步骤XXX")
    popup.click(selector)
    wait_loading_gone(popup, container)
```

---

## 📈 统计功能

### 构建记录
- 每日账户数 + 项目数
- 数据存储: `build_records.json`
- GUI查看: BuildRecordFrame

### 素材历史
- 追踪已用素材ID
- 记录使用日期
- GUI管理: MaterialHistoryFrame

---

## 🎓 总结

**这是一个功能完整的营销自动化工具**，特点:

✅ **配置驱动**: 无需代码修改即可支持新账户/剧名  
✅ **浏览器自动化**: 完全模拟用户操作，克服反爬  
✅ **现代化GUI**: CustomTkinter实现专业级界面  
✅ **多平台支持**: 2个系统 × 2个留存 × 2个模式 = 6+种配置  
✅ **容错机制**: 异常重试、加载检测、状态验证  
✅ **数据持久化**: JSON配置 + 统计记录 + 历史追踪  
✅ **可扩展架构**: 清晰的函数模块化，便于添加新功能

**当前大小**: 
- 代码: 7894行
- 依赖: 3个包 (playwright, openpyxl, customtkinter)
- 配置: JSON格式 (易于编辑 + 版本控制)

