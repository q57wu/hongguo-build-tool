# 红果搭建工具 - 快速参考指南

## 核心概念

### 6种配置 = 平台 × 留存 × 模式

```
┌─ 普通短剧（4种）
│  ├─ 安卓-每留    (1855367293890569, 红果通用, 0.6x)
│  ├─ 安卓-七留    (1855367293890569, 红果通用, 1.0x)
│  ├─ IOS-每留     (1859509275615367, IOS定向, 0.6x)
│  └─ IOS-七留     (1859509275615367, IOS定向, 1.0x)
│
└─ 激励视频（2种）
   ├─ 安卓-激励每留 (1855641147536460, 通用激励, 0.6x)
   └─ 安卓-激励七留 (1855641147536460, 通用激励, 1.0x)
```

---

## 文件映射速查

### 代码 (7894行)

| 功能 | 开始行 | 结束行 | 函数/类 |
|------|-------|-------|--------|
| 配置加载 | 116 | 250 | load_config, save_config |
| 配置迁移 | 375 | 424 | migrate_ids_txt_to_config |
| 字符串工具 | 657 | 846 | sanitize_link_text, is_valid_material_name |
| 浏览器交互 | 873 | 1200 | safe_click, wait_loading_gone, get_visible_layer |
| 步骤1-9 | 1198 | 2176 | step_select_strategy ... step_submit_and_close |
| 素材分页 | 1498 | 2094 | _get_material_total, _find_material_card_on_current_page |
| 激励搭建 | 2373 | 2945 | run_build_incentive, run_incentive_promo_chain |
| GUI: 剧名工具 | 3328 | 3930 | JuMingToolFrame |
| GUI: 设置 | 6077 | 7391 | SettingsFrame |
| GUI: 主窗口 | 7392 | 7876 | BuildApp |

### 配置文件

| 文件 | 大小 | 用途 |
|------|------|------|
| config.json | ~2MB | 主配置（账户/剧名/链接） |
| build_records.json | <1KB | 日构建统计 |
| material_history.json | <1KB | 素材使用追踪 |

---

## 快速操作指南

### 添加新剧名

```json
// config.json
{
  "common": {
    "drama_titles": [
      "既有剧名1",
      "既有剧名2",
      "新剧名"         ← 添加这里
    ]
  }
}
```

### 添加新账户 + 剧名 + 链接

```json
// config.json → profiles → "安卓-每留" → groups
{
  "groups": [
    {
      "account_ids": ["1234567890", "9876543210"],  // 新账户
      "dramas": [
        {
          "name": "新剧名",
          "click": "http://click.tracking.url",
          "show": "http://show.tracking.url",
          "video": "http://video.tracking.url",
          "material_ids": ["素材ID1", "素材ID2"]
        }
      ]
    }
  ]
}
```

### 激励配置特殊格式

```json
// 激励模式使用group_name + 统一链接
{
  "groups": [
    {
      "group_name": "组1",
      "account_ids": ["1855641147536460"],
      "click_url": "http://...",
      "show_url": "http://...",
      "play_url": "http://...",
      "dramas": []  // 激励不需要dramas
    }
  ]
}
```

---

## 关键类与方法速查

### 配置类

```python
# 读取
load_config()           # → dict
load_build_records()    # → dict (日统计)
load_material_history() # → list (素材历史)

# 写入
save_config(cfg)
save_build_records(records)
save_material_history(history)

# 处理
profile_groups_from_config(cfg, "安卓-每留")  # → [(account_ids, dramas)]
build_runtime_profile_config("安卓-每留")     # → dict (运行时配置)
sanitize_config_groups(groups)                # → cleaned_groups, changed
```

### 文本处理类

```python
# 链接
sanitize_link_text(text)            # 清理→URL
classify_link(url)                  # → "click"|"show"|"video"

# 剧名
is_valid_material_name(drama, material)  # → bool
extract_mmdd(name)                      # → "0430" or None

# 分隔
is_separator_line(text)             # → bool (检查===)
```

### 浏览器交互类

```python
# 点击
safe_click(popup, locator, timeout=5000, retries=3)
safe_select_option(popup, trigger, option_text)

# 等待
wait_loading_gone(popup, container)
wait_locator_ready(popup, locator)
wait_idle(popup)
wait_small(popup, ms=300)

# 查询
get_visible_layer(popup)            # → element (最上层弹窗)
get_visible_drawer(popup)           # → element (侧滑)
_visible_confirm_count(popup)       # → int

# 滚动
scroll_wrap_to_bottom(popup, wrap)
scroll_to_module(popup, wrap, module_id)
```

### 搭建函数

```python
# 标准流程（9个步骤）
step_select_strategy(popup, cfg, logger, W)
step_select_media_accounts(popup, ids, cfg, logger, W)
step_link_product(popup, drama_name, cfg, logger, W)
step_fill_monitor_links(popup, drama, cfg, logger, W)
step_select_audience_package(popup, cfg, logger, W)
step_fill_project_name(popup, drama_name, cfg, logger, W)
step_fill_ad_name(popup, drama_name, cfg, logger, W)
step_pick_media_materials(popup, drama_name, material_ids, cfg, logger, W)
step_submit_and_close(popup, page, logger, W)

# 运行
run_build(profile_key, log_callback, stop_event)
```

### 素材选择

```python
# 分页
_get_material_total(pane)           # → int (总页数)
_get_active_material_page(pane)     # → int (当前页)
_has_next_material_page(pane)       # → bool
_go_to_next_material_page(popup, pane)
_go_to_material_page(popup, pane, page_no)

# 搜索
_find_material_card_on_current_page(popup, material_dlg, pane, material_name)
_collect_material_candidates(popup, material_dlg, pane, drama_name)

# 选择
_pick_materials_by_keyword(popup, drama_name, cfg, logger, W)
_pick_materials_by_ids(popup, drama_name, material_ids, cfg, logger, W)
```

### GUI类

```python
BuildApp()                          # 主窗口
  ├─ _build_ui()                    # 构建界面
  ├─ _on_start()                    # 点击开始
  ├─ _on_stop()                     # 点击停止
  ├─ _on_mode_changed()             # 切换模式
  ├─ _poll_log()                    # 日志轮询
  └─ _open_settings()               # 打开设置

SettingsFrame()                     # 设置面板
  ├─ _build_tab_profiles()          # 配置TAB
  ├─ _load_profile_data()           # 加载配置
  ├─ _save_profile_data()           # 保存配置
  └─ ... (7个其他TAB)

JuMingToolFrame()                   # 剧名工具
  ├─ _build_batch_tab()             # 批量分配TAB
  ├─ _build_titles_tab()            # 剧单管理TAB
  ├─ _batch_process()               # 执行分配
  └─ _add_to_profile()              # 添加到配置
```

---

## 配置编辑示例

### 场景：新增一个账户搭建

```
1. 打开工具 → 点击⚙设置
2. 选择 [短剧单本] → [安卓-每留]
3. 滚到「分组数据」章节
4. 点「➕ 新增分组」
5. 填入:
   - 账户ID: 1234567890
   - 剧名: "我的新剧"
   - 点击链接: http://...
   - 展示链接: http://...
   - 视频链接: http://...
   - 素材ID: 素材1 素材2 素材3
6. 点「💾 保存」
7. 返回主界面
8. 选择 [安卓] [每留] [普通]
9. 点「▶ 开始搭建」
```

### 场景：批量导入多个账户

```
1. 打开设置 → [剧名链接整理工具]
2. 切换 [批量分配] TAB
3. 填入:
   账户ID: 1234567890
         9876543210
         1111111111
   
   短剧数据: 我的新剧
            http://click.url
            http://show.url
            http://video.url
            
            另一部剧
            http://click.url
            http://show.url
            http://video.url
   
4. 点「🚀 批量分配」
5. 点「➕ 到安卓-每留」
6. 确认导入
```

---

## 常见问题排查

### 问题1：「搭建失败」

```
排查步骤:
1. 确认Chrome已启动: chrome.exe --remote-debugging-port=9222
2. 确认账户ID正确（10位+数字）
3. 查看日志，找到具体失败步骤
4. 检查剧名是否在平台存在
5. 检查监测链接格式是否正确
```

### 问题2：「素材找不到」

```
排查步骤:
1. 确认素材ID在平台上可见
2. 检查素材名是否包含完整剧名
3. 如果用关键词搜索，确认搜索过滤条件
4. 查看material_history.json，检查该素材是否曾被使用
```

### 问题3：「账户不存在」

```
排查步骤:
1. 检查账户ID是否正确
2. 确认账户在投放平台上是否真实存在
3. 检查是否被禁用/削减
4. 查看step_select_media_accounts的日志
```

---

## 日志颜色含义

| 颜色 | 含义 | 标签 |
|------|------|------|
| 🟢 绿 | 成功 | success |
| 🔴 红 | 错误 | error |
| 🟡 黄 | 警告 | warning |
| ⚪ 白 | 信息 | info |
| 🔵 暗 | 分隔 | separator |

---

## Chrome DevTools Protocol (CDP)

### 启动方式

```bash
# 标准启动
chrome.exe --remote-debugging-port=9222

# 或通过快捷方式属性
目标: "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
```

### 验证连接

```bash
# 查询CDP信息
curl http://localhost:9222/json/version

# 响应示例
{
  "Browser": "Chrome/125.0.0.0",
  "Protocol-Version": "1.3",
  "User-Agent": "...",
  "V8-Version": "12.5.0.0"
}
```

### 配置修改

```json
// config.json
{
  "common": {
    "cdp_endpoint": "http://localhost:9222"  ← 修改这里（如需换端口）
  }
}
```

---

## 时间等待机制

### WaitTimes常量

```python
NORMAL = 5_000      # 标准操作（5秒）
SHORT = 2_000       # 快速反应（2秒）
LONG = 15_000       # 长等待（15秒）
```

### wait_scale倍数

```
每留 (0.6x): 等待时间缩短 → 加速流程
七留 (1.0x): 标准等待    → 稳定流程

实际等待 = TIMEOUT × wait_scale
```

---

## 数据结构速查

### Drama（剧名数据）

```python
{
    "name": "天下第一纨绔",
    "click": "http://...",          # 点击监测
    "show": "http://...",           # 展示监测
    "video": "http://...",          # 视频监测
    "material_ids": ["ID1", "ID2"]
}
```

### Group（分组数据）

```python
{
    "account_ids": ["1234567890", "9876543210"],  # 多账户
    "dramas": [drama_1, drama_2, ...],            # 多剧
    "group_name": "组1",                          # 激励特有
    "click_url": "http://...",                    # 激励特有
    "show_url": "http://...",                     # 激励特有
    "play_url": "http://..."                      # 激励特有
}
```

### Config

```python
{
    "common": {
        "cdp_endpoint": "http://localhost:9222",
        "drama_titles": ["剧1", "剧2", ...]
    },
    "profiles": {
        "安卓-每留": {
            "strategy": "安卓-每留",
            "material_account_id": "1855367293890569",
            "audience_keyword": "红果通用",
            "monitor_btn_text": "选择分包和链接组",
            "name_prefix": "安卓-站内-短剧-每留",
            "wait_scale": 0.6,
            "groups": [group_1, group_2, ...]
        },
        // ... 其他5个配置
    }
}
```

---

## 执行流快速版

```
用户点击「开始搭建」
  ↓
_on_start()
  ├─ 获取配置: platform+retention+mode → "安卓-每留"
  ├─ 加载groups: load_config() → profile_groups_from_config()
  ├─ 启动线程: run_build("安卓-每留", log_callback, stop_event)
  └─ GUI响应: 禁用启动 + 启用停止
    ↓
后台线程run_build()
  ├─ FOR group IN groups:
  │  ├─ FOR account_id IN group.account_ids:
  │  │  ├─ 打开浏览器标签
  │  │  ├─ FOR drama IN group.dramas:
  │  │  │  ├─ 执行9个step_*()函数
  │  │  │  │  (select_strategy → submit_and_close)
  │  │  │  └─ log_callback(成功消息)
  │  │  └─ 关闭标签
  │  └─ END account
  │
  ├─ record_build_success()
  └─ 线程终止
    ↓
_poll_log()（后台不断轮询）
  ├─ log_queue.get() → 获取日志消息
  ├─ self.log_text.insert() → 显示到GUI
  └─ 每100ms检查一次
    ↓
日志区实时刷新，用户看到彩色日志流动
```

