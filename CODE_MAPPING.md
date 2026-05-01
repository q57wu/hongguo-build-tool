# 红果搭建工具 - 完整代码映射

## 文件清单

| 文件 | 行数 | 功能 |
|------|------|------|
| 红果搭建工具.py | 7894 | 主程序（核心） |
| test_split.py | 82 | Excel拆分工具 |
| config.json | 2000+ | 配置库 |
| requirements.txt | 3 | 依赖 |
| 使用说明.txt | 130 | 用户手册 |
| README.md | 62 | 项目概览 |

---

## 主程序代码结构（7894行）

### 第一部分：导入 & 常量定义 (1-593行)

```python
# ── 导入 ──
import re, random, functools, time, logging, sys, os, threading, queue, json, webbrowser, subprocess, glob
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout, expect
import openpyxl
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import unicodedata

# ── 内置配置常数 ──
PROFILES = {
    "安卓-每留":   dict(strategy="安卓-每留", material_account_id="1855367293890569", ...),
    "安卓-七留":   dict(strategy="安卓-七留", material_account_id="1855367293890569", ...),
    "IOS-每留":    dict(strategy="IOS-每留", material_account_id="1859509275615367", ...),
    "IOS-七留":    dict(strategy="IOS-七留", material_account_id="1859509275615367", ...),
}

INCENTIVE_PROFILES = {
    "安卓-激励每留": dict(...),
    "安卓-激励七留": dict(...),
}

ALL_PROFILES = {**PROFILES, **INCENTIVE_PROFILES}

PROFILE_CATEGORIES = [
    ("短剧单本", list(PROFILES.keys())),
    ("短剧激励", list(INCENTIVE_PROFILES.keys())),
]

# ── 文件路径 ──
CONFIG_FILE = Path(__file__).parent / "config.json"
BUILD_RECORD_FILE = Path(__file__).parent / "build_records.json"
MATERIAL_HISTORY_FILE = Path(__file__).parent / "material_history.json"

# ── 主题颜色 ──
C_BG, C_CARD, C_PRIMARY, C_ACCENT, C_TEXT, C_TEXT_2, C_DIM, ...

# ── 异常类 ──
class WaitTimes:
    NORMAL = 5_000
    SHORT = 2_000
    LONG = 15_000
    
class AccountsMissingError(Exception):
    pass
    
class StopRequested(Exception):
    pass
```

---

### 第二部分：配置管理函数 (116-554行)

#### 默认值生成
```python
_profile_defaults(key: str) -> dict         # 生成配置默认值
_default_config() -> dict                   # 生成完整config.json骨架
_empty_drama() -> dict                      # 生成空剧名对象
_empty_group() -> dict                      # 生成空分组对象
```

#### 配置读写
```python
load_config() -> dict                       # 读取config.json + 字段校验
save_config(cfg: dict) -> None              # 写入config.json
load_build_records() -> dict                # 读取build_records.json
save_build_records(records: dict) -> None   # 写入build_records.json
load_material_history() -> list             # 读取material_history.json
save_material_history(history: list) -> None # 写入material_history.json
```

#### 配置处理
```python
add_material_history(names: list[str]) -> None      # 添加素材到历史
get_used_material_names() -> set                    # 获取已用素材集合
record_build_success(account_count, project_count)  # 记录今日统计

_parse_ids_txt_groups(ids_file: Path)               # [废弃] 解析ids.txt
_parse_incentive_ids_txt(ids_file: Path)            # [废弃] 解析激励ids.txt
migrate_ids_txt_to_config() -> bool                 # [迁移工具] ids.txt→config.json
sanitize_config_groups(groups)                      # 配置清理（去重/验证）
build_runtime_profile_config(profile_key) -> dict   # 构建运行时配置
profile_groups_from_config(cfg, profile_key)        # 从config.json提取groups
```

#### 数据解析
```python
_parse_single_group(raw_text, logger)           # 从纯文本解析一个分组
_parse_clean_format(text)                       # 解析"净格式"（标准布局）
_parse_raw_format(text)                         # 解析"原始格式"（token式）
```

---

### 第三部分：工具函数 (554-900行)

#### 初始化
```python
def init_data_dirs():
    """创建所有配置的logs目录"""
```

#### 日志
```python
def setup_logger(log_dir: Path):
    """创建logger"""

def check_stop(stop_event):
    """检查停止信号"""
```

#### 字符串处理
```python
def fmt_duration(seconds: float) -> str:
    """格式化时长 (秒→"1h 23m 45s")"""

def is_separator_line(text: str) -> bool:
    """判断是否为分隔符 (===, ─── etc)"""

def sanitize_link_text(text: str) -> str:
    """清理链接 (去首尾空白、提取http://...行)"""

def normalize_link(text: str) -> str:
    """规范化链接"""

def classify_link(url: str) -> str:
    """分类链接 ("click"/"show"/"video")"""
```

#### 素材名匹配
```python
def _compile_sequel_pattern(drama_name: str):
    """编译续集正则 (第N部)"""

def _normalize_material_text(text: str) -> str:
    """规范化素材名"""

def _material_name_has_exact_drama_segment(drama_name, material_name) -> bool:
    """检查素材是否包含剧名完整段落"""

def is_valid_material_name(drama_name, material_name) -> bool:
    """判断素材是否属于该剧"""

def extract_mmdd(name: str):
    """从名称提取日期标记"""
```

#### 格式检测
```python
def _is_url_line(line: str) -> bool:
def _clean_plain_line(line: str) -> str:
def _is_material_ids_line(line: str) -> bool:
```

---

### 第四部分：数据读取 (847-930行)

```python
def read_data(id_file: Path, logger):
    """从文件读取数据，返回 [(account_ids, [drama_dicts])]"""
```

---

### 第五部分：浏览器交互库 (873-1200行)

#### 基础操作
```python
def safe_click(popup, locator, *, timeout=5000, retries=3, desc="", logger=None, W=None):
    """安全点击（含重试 + 加载等待）"""

def _locator_count(locator):
    """获取定位器匹配的元素个数"""

def wait_loading_gone(popup, container, *, timeout=30000):
    """等待加载器消失"""

def wait_locator_ready(popup, locator, *, timeout=5000, desc="", W=None):
    """等待元素可见"""

def wait_idle(target, *, mask_timeout=8000, network=False):
    """等待页面空闲"""

def wait_small(popup, ms=300):
    """短暂延迟"""
```

#### 页面查询
```python
def _safe_page_title(page):
    """安全获取页面标题"""

def _safe_page_url(page):
    """安全获取页面URL"""

def _is_browser_internal_page(url) -> bool:
    """判断是否为内部页面"""

def select_build_page(context, logger):
    """选择投放平台页面"""
```

#### 弹窗处理
```python
def get_visible_layer(popup, *, desc="弹窗", timeout=15000, logger=None, W=None):
    """获取最上层弹窗"""

def get_visible_drawer(popup):
    """获取侧滑抽屉"""

def scroll_wrap_to_bottom(popup, wrap, W):
    """滚动容器到底部"""

def scroll_to_module(popup, wrap, module_id, W):
    """滚动到指定模块"""
```

#### 确认按钮
```python
def click_top_confirm(popup, scope=None, *, desc="确认按钮", timeout=5000, wait_close=False, logger=None, W=None):
    """点击最上层确认按钮（栈式管理）"""

def _visible_confirm_count(popup):
    """计算可见确认按钮数"""

def _click_confirm_button_hard(popup, button, *, desc, logger=None, W=None):
    """硬点击确认按钮（多种尝试）"""

def click_optional_confirm(popup, *, desc="可选确认按钮", timeout=6000, logger=None, W=None):
    """点击可选的确认按钮"""
```

#### 下拉菜单
```python
def safe_select_option(popup, trigger_locator, option_text, *, desc="", logger=None, W=None):
    """安全选择下拉菜单"""
```

---

### 第六部分：自动化步骤函数 (1198-2176行)

#### 标准搭建流程
```
step_select_strategy()          # 步骤1：选择策略
step_select_media_accounts()    # 步骤2：选择账户
step_link_product()             # 步骤3：链接产品/剧名
step_fill_monitor_links()       # 步骤4：填充监测链接
step_select_audience_package()  # 步骤5：选择定向包
step_fill_project_name()        # 步骤6：填充项目名
step_fill_ad_name()             # 步骤7：填充广告名
step_pick_media_materials()     # 步骤8：选择素材（含分页）
step_submit_and_close()         # 步骤9：提交 + 关闭
```

#### 素材选择子系统
```python
_get_material_pager(pane)               # 获取分页器
_get_material_total(pane)               # 获取总页数
_get_active_material_page(pane)         # 获取当前页
_has_next_material_page(pane)           # 是否有下一页
_go_to_next_material_page(popup, pane)  # 翻到下一页
_go_to_material_page(popup, pane, page_no)  # 翻到指定页
_find_material_card_on_current_page()   # 搜索素材卡片
_open_material_dialog()                 # 打开素材选择弹窗
_configure_material_filters()           # 配置过滤条件
_collect_material_candidates()          # 收集候选素材
_select_and_submit_materials()          # 选择 + 提交
_pick_materials_by_keyword()            # 按关键词选择
_pick_materials_by_ids()                # 按ID精确选择
```

#### 运行函数
```python
def run_build(profile_key: str, log_callback=None, stop_event=None):
    """
    执行完整搭建流程
    
    流程:
    1. 连接浏览器 (CDP)
    2. 遍历groups
    3. 遍历account_ids
    4. 遍历dramas
    5. 执行9个步骤
    6. 记录统计
    """

def wait_return_to_main_after_material(popup, logger, W):
    """等待返回主页面"""
```

---

### 第七部分：激励模式搭建 (2373-2945行)

#### 激励搭建步骤
```python
step_link_product_incentive()           # 激励版：链接产品
step_fill_monitor_links_incentive()     # 激励版：填充链接
step_fill_project_name_incentive()      # 激励版：填充项目名
step_fill_ad_name_incentive()           # 激励版：填充广告名
step_pick_materials_by_page()           # 激励版：按页面选择素材
```

#### 激励运行函数
```python
def run_build_incentive(profile_key: str, log_callback=None, stop_event=None):
    """激励版完整搭建"""

def _incentive_promo_run_once():
    """一轮推链"""

def run_incentive_promo_chain(count, suffix, log_func, stop_event):
    """循环推链N轮"""

def _incentive_push_read_pages(page):
    """读取素材页面（JS注入）"""

def run_incentive_push(account_id, log_func, stop_event):
    """推送素材"""
```

---

### 第八部分：GUI类系统 (3104-7391行)

#### 12个GUI类

1. **JuMingToolFrame** (3328-3930行)
   - 剧名链接整理工具
   - 2个TAB: 批量分配 + 剧单管理
   - 输入格式转换 + 配置批量导入

2. **PromotionChainToolFrame** (3931-4070行)
   - 推广链管理工具
   - 搜索 + 过滤 + 导出

3. **PromotionSplitToolFrame** (4071-4349行)
   - 推广链拆分工具
   - 按配置分组Excel

4. **IncentivePromotionSplitToolFrame** (4350-4602行)
   - 激励推广链拆分

5. **SearchDramaMaterialPushToolFrame** (4603-5311行)
   - 素材搜索 + 推送

6. **IncentivePromoChainToolFrame** (5312-5449行)
   - 激励推链管理

7. **IncentivePushToolFrame** (5450-5572行)
   - 激励素材推送

8. **IncentiveLinkToolFrame** (5573-5827行)
   - 激励链接管理

9. **MaterialHistoryFrame** (5828-5952行)
   - 素材历史统计

10. **BuildRecordFrame** (5953-6076行)
    - 构建记录统计

11. **SettingsFrame** (6077-7391行)
    - 完整设置面板
    - 平台配置编辑
    - 账户/剧名/链接管理

12. **BuildApp** (7392-7876行)
    - 主应用窗口
    - 核心交互逻辑
    - 线程管理 + 日志同步

---

### 第九部分：主程序入口 (7877-7894行)

```python
if __name__ == "__main__":
    migrate_ids_txt_to_config()
    init_data_dirs()
    app = BuildApp()
    app.mainloop()
```

---

## 核心算法精解

### 算法1：素材名匹配

```python
def is_valid_material_name(drama_name: str, material_name: str) -> bool:
    """
    目标: 判断素材是否属于该剧
    
    流程:
    1. drama_name="天下第一纨绔"
       → _normalize_material_text()
       → 提取连续中文："天下第一纨绔"
       → segments = ["天下第一纨绔"]
    
    2. material_name="天下第一纨绔_20260501_素材A"
       → 规范化→"天下第一纨绔_20260501_素材a"
       → _material_name_has_exact_drama_segment()
       → 检查是否包含完整"天下第一纨绔"
       → 返回True
    
    3. 特殊:续集识别
       drama_name="云渺1：我修仙多年强亿点怎么了"
       material_name="云渺2：..."
       → 提取pattern:"第\d+部|第\d+季"
       → 同时验证基础名称匹配
    """
```

### 算法2：素材分页浏览

```python
def _pick_materials_by_ids(popup, drama_name, material_ids, cfg, logger, W):
    """
    目标: 精确选择指定素材ID
    
    流程:
    for material_id in material_ids:
        1. current_page = _get_active_material_page(pane)
        2. found = _find_material_card_on_current_page(material_id)
        
        3. if not found:
            # 搜索所有页面
            total = _get_material_total(pane)
            for page in range(total):
                _go_to_material_page(page)
                found = _find_material_card_on_current_page(material_id)
                if found:
                    break
        
        4. if found:
            safe_click(found_card)  # 选择素材
            wait_loading_gone()
        else:
            logger.error(f"素材 {material_id} 不存在")
    
    5. click_top_confirm()  # 提交选择
    """
```

### 算法3：确认按钮栈式管理

```python
def click_top_confirm(popup, scope=None, *, wait_close=False, ...):
    """
    目标: 点击最上层确认按钮（嵌套弹窗支持）
    
    关键: 不同弹窗可能有多个确认按钮，需要确定"最上层"
    
    实现:
    1. 获取scope范围（或全页面）
    2. 统计可见的确认按钮
       count = _visible_confirm_count(popup)
    3. 根据count选择策略:
       - count == 1: 直接点击
       - count > 1: 查找position最右下的（栈顶）
    4. 点击目标按钮
    5. wait_close=True时，等待按钮消失确认成功
    """
```

### 算法4：推广链拆分（Excel处理）

```python
def classify_row(row):
    """
    从Excel行分类配置
    
    输入行: [ID, 投放名, 平台, 页, ...]
    输出: "IOS-每留" or "Android-七留" or None
    
    规则:
    1. 检查第4列(页)是否包含"激励"→返回None
    2. 检查第2列(名)包含"每留"→_每留
    3. 检查第2列(名)包含"七留"→_七留  
    4. 提取第3列(平台) as OS
    5. 返回 f"{OS}-{retention}"
    """
```

---

## 关键数据流

### 数据流1：配置加载

```
程序启动
↓
load_config()
  ├─ 读取config.json (UTF-8)
  ├─ 字段缺失?→使用_default_config()填充
  ├─ 递归验证groups:
  │  ├─ account_ids: [str] → 确保纯数字
  │  ├─ dramas: [drama_dict]
  │  │  ├─ name: str
  │  │  ├─ click/show/video: URL清理
  │  │  └─ material_ids: [str]
  │  └─ 去重 + 规范化
  ├─ common.drama_titles: 驱动剧名库
  └─ return cfg: dict
↓
build_runtime_profile_config(key)
  ├─ 从ALL_PROFILES[key]复制
  ├─ 覆盖用户config.json中的数据
  └─ return: 运行时配置
↓
profile_groups_from_config(cfg, key)
  ├─ 提取cfg["profiles"][key].get("groups")
  ├─ 返回: [(account_ids, dramas)] 或激励版本
```

### 数据流2：搭建执行

```
点击「开始搭建」
↓
_on_start()
  ├─ 检查是否已运行
  ├─ 获取profile_key="安卓-每留"(用户选择)
  ├─ 启动线程 run_build(profile_key, log_callback, stop_event)
  └─ GUI禁用起始按钮，启用停止按钮
↓
run_build(profile_key)
  ├─ 加载app config
  ├─ app_cfg = load_config()
  ├─ groups = profile_groups_from_config(app_cfg, profile_key)
  ├─ 连接浏览器 context = sync_playwright().start()
  │
  ├─ FOR group IN groups:
  │  ├─ account_ids = group[0]
  │  ├─ dramas = group[1]
  │  │
  │  ├─ FOR account_id IN account_ids:
  │  │  ├─ 打开投放平台新标签页
  │  │  │
  │  │  ├─ FOR drama IN dramas:
  │  │  │  ├─ step_select_strategy()
  │  │  │  ├─ step_select_media_accounts(account_id)
  │  │  │  ├─ step_link_product(drama_name)
  │  │  │  ├─ step_fill_monitor_links(drama)
  │  │  │  ├─ step_select_audience_package()
  │  │  │  ├─ step_fill_project_name(drama_name)
  │  │  │  ├─ step_fill_ad_name(drama_name)
  │  │  │  ├─ step_pick_media_materials(drama_name, material_ids)
  │  │  │  ├─ step_submit_and_close()
  │  │  │  ├─ add_material_history(drama.name)
  │  │  │  └─ log_callback(f"✓ {drama_name} 搭建完成")
  │  │  │
  │  │  └─ wait_return_to_main_after_material()
  │  │
  │  └─ END account
  │
  ├─ END group
  │
  ├─ record_build_success(total_accounts, total_projects)
  ├─ 关闭浏览器
  └─ return
↓
_poll_log() (后台)
  ├─ while True:
  │  ├─ msg = log_queue.get_nowait()
  │  ├─ self.log_text.insert("end", msg, tags=["success"|"error"|...])
  │  ├─ self.log_text.see("end")
  │  └─ self.after(100)  # 轮询间隔
  │
↓
点击「停止」
  └─ stop_event.set()
     → check_stop()抛出StopRequested异常
     → 线程立即终止
```

---

## 文件对应表

| 功能模块 | 源代码行 | 相关函数/类 |
|---------|---------|-----------|
| 配置系统 | 116-550 | load_config, save_config, profile_groups_from_config |
| 日志系统 | 625-665 | setup_logger, check_stop |
| 文本处理 | 657-846 | sanitize_link_text, is_valid_material_name |
| 浏览器API | 873-1200 | safe_click, wait_loading_gone, get_visible_layer |
| 搭建流程 | 1198-2176 | step_select_strategy ... step_submit_and_close |
| 激励流程 | 2373-2945 | run_build_incentive, run_incentive_promo_chain |
| GUI工具库 | 3328-5827 | JuMingToolFrame, PromotionChainToolFrame ... |
| 设置面板 | 6077-7391 | SettingsFrame (完整配置编辑) |
| 主窗口 | 7392-7876 | BuildApp (核心交互) |

