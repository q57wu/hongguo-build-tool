"""
backend/core/constants.py
常量、配置字典、工具类和异常类。
"""
import re
import sys
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
#  软件运行目录
# ═══════════════════════════════════════════════════════════════
def _app_dir() -> Path:
    """打包后返回 exe 所在目录，源码运行返回脚本所在目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # 本文件位于 backend/core/，向上两级到项目根
    return Path(__file__).resolve().parent.parent.parent


APP_DIR = _app_dir()

# ═══════════════════════════════════════════════════════════════
#  配置表：4 种组合的差异参数
# ═══════════════════════════════════════════════════════════════
_BASE_DIR = APP_DIR / "数据"

PROFILES = {
    "安卓-每留": dict(
        strategy="安卓-每留",
        material_account_id="1855367293890569",
        audience_keyword="红果通用",
        monitor_btn_text="选择分包和链接组",
        name_prefix="安卓-站内-短剧-每留",
        ids_file=_BASE_DIR / "安卓" / "搭建" / "每留" / "ids.txt",
        log_dir=_BASE_DIR / "安卓" / "搭建" / "每留" / "logs",
        wait_scale=0.6,
        incentive=False,
    ),
    "安卓-七留": dict(
        strategy="安卓-七留",
        material_account_id="1855367293890569",
        audience_keyword="红果通用",
        monitor_btn_text="选择分包和链接组",
        name_prefix="安卓-站内-短剧-七留",
        ids_file=_BASE_DIR / "安卓" / "搭建" / "七留" / "ids.txt",
        log_dir=_BASE_DIR / "安卓" / "搭建" / "七留" / "logs",
        wait_scale=1.0,
        incentive=False,
    ),
    "IOS-每留": dict(
        strategy="IOS-每留",
        material_account_id="1859509275615367",
        audience_keyword="IOS定向",
        monitor_btn_text="选择链接组",
        name_prefix="IOS-站内-短剧-每留",
        ids_file=_BASE_DIR / "IOS" / "每留" / "ids.txt",
        log_dir=_BASE_DIR / "IOS" / "每留" / "logs",
        wait_scale=0.6,
        incentive=False,
    ),
    "IOS-七留": dict(
        strategy="IOS-七留",
        material_account_id="1859509275615367",
        audience_keyword="IOS定向",
        monitor_btn_text="选择链接组",
        name_prefix="IOS-站内-短剧-七留",
        ids_file=_BASE_DIR / "IOS" / "七留" / "ids.txt",
        log_dir=_BASE_DIR / "IOS" / "七留" / "logs",
        wait_scale=1.0,
        incentive=False,
    ),
}

INCENTIVE_PROFILES = {
    "安卓-激励每留": dict(
        strategy="安卓-激励-每留",
        material_account_id="1855641147536460",
        audience_keyword="通用激励",
        monitor_btn_text="选择分包和链接组",
        name_prefix="安卓-站内-激励-每留",
        ids_file=_BASE_DIR / "激励" / "安卓搭建" / "激励每留" / "激励ids.txt",
        log_dir=_BASE_DIR / "激励" / "安卓搭建" / "激励每留" / "logs",
        wait_scale=0.6,
        build_mode="incentive",
        pages_per_round=3,
        push_account_id="1855641147536460",
        incentive=True,
    ),
    "安卓-激励七留": dict(
        strategy="安卓-激励-七留",
        material_account_id="1855641147536460",
        audience_keyword="通用激励",
        monitor_btn_text="选择分包和链接组",
        name_prefix="安卓-站内-激励-七留",
        ids_file=_BASE_DIR / "激励" / "安卓搭建" / "激励七留" / "激励ids.txt",
        log_dir=_BASE_DIR / "激励" / "安卓搭建" / "激励七留" / "logs",
        wait_scale=1.0,
        build_mode="incentive",
        pages_per_round=3,
        push_account_id="1855641147536460",
        incentive=True,
    ),
}

ALL_PROFILES = {**PROFILES, **INCENTIVE_PROFILES}

PROFILE_CATEGORIES = [
    ("短剧单本", list(PROFILES.keys())),
    ("短剧激励", list(INCENTIVE_PROFILES.keys())),
]

# ═══════════════════════════════════════════════════════════════
#  配置文件路径
# ═══════════════════════════════════════════════════════════════
CONFIG_FILE = APP_DIR / "config.json"
BUILD_RECORD_FILE = APP_DIR / "build_records.json"
MATERIAL_HISTORY_FILE = APP_DIR / "material_history.json"

# 仅保存到 config.json 的可编辑字段
PROFILE_EDITABLE_FIELDS = (
    "strategy",
    "material_account_id",
    "audience_keyword",
    "monitor_btn_text",
    "name_prefix",
    "wait_scale",
)

# ═══════════════════════════════════════════════════════════════
#  通用常量
# ═══════════════════════════════════════════════════════════════
TIMEOUT = 60_000
RE_CONFIRM = re.compile(r"确\s*定|确定|确\s*认|确认")
RE_MMDD = re.compile(r'(?<!\d)(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)')
TODAY_STR = datetime.now().strftime("%m%d")

# ═══════════════════════════════════════════════════════════════
#  等待时间（基准值，运行时乘以 wait_scale）
# ═══════════════════════════════════════════════════════════════
BASE_WAITS = dict(
    TINY=200, SHORT=300, MEDIUM=500, NORMAL=800,
    LONG=1000, LONGER=1200, EXTRA=1500, LOAD=2000,
    HEAVY=2500, SEARCH=4000,
)


class WaitTimes:
    def __init__(self, scale=1.0):
        for k, v in BASE_WAITS.items():
            setattr(self, k, max(80, int(v * scale)))


# ═══════════════════════════════════════════════════════════════
#  异常（已搬到 backend/core/exceptions.py，此处 re-export 保持向后兼容）
# ═══════════════════════════════════════════════════════════════
from backend.core.exceptions import (  # noqa: E402
    AccountsMissingError,
    StopRequested,
    BuildSubmitError,
    check_stop,
)


# ═══════════════════════════════════════════════════════════════
#  激励推广链常量（INCENTIVE_PROMO_*）
# ═══════════════════════════════════════════════════════════════
INCENTIVE_PROMO_DRAWER_SEL = ".arco-drawer.promotion_form_wrapper"
INCENTIVE_PROMO_NAME_INPUT = "#promotion_name_input"
INCENTIVE_PROMO_CONFIRM_BTN = ".arco-drawer:visible button:has-text('确定')"
INCENTIVE_PROMO_TIMEOUT = 10_000
INCENTIVE_PROMO_DRAWER_TIMEOUT = 15_000

# ═══════════════════════════════════════════════════════════════
#  激励素材推送常量（INCENTIVE_PUSH_*）
# ═══════════════════════════════════════════════════════════════
INCENTIVE_PUSH_TIMEOUT = 10_000
INCENTIVE_PUSH_WAIT_AFTER = 120_000
INCENTIVE_PUSH_BETWEEN = 2_000
INCENTIVE_PUSH_DIALOG_SEL = ".arco-drawer, .arco-modal"
INCENTIVE_PUSH_OPTION_SEL = ".arco-select-option"
INCENTIVE_PUSH_NEXT_BTN = ".arco-pagination-item-next"

# ═══════════════════════════════════════════════════════════════
#  推广链常量（PROMOTION_CHAIN_*）
# ═══════════════════════════════════════════════════════════════
PROMOTION_CHAIN_CDP = "http://127.0.0.1:9222"
PROMOTION_CHAIN_TIMEOUT = 20_000
PROMOTION_CHAIN_NAV_TIMEOUT = 15_000
PROMOTION_CHAIN_ELEMENT_TIMEOUT = 8_000
PROMOTION_CHAIN_SEARCH_DELAY = 800
PROMOTION_CHAIN_CLICK_DELAY = 200
PROMOTION_CHAIN_LIST_URL_PATTERN = re.compile(r"/short-play/list(?!/detail)")
PROMOTION_CHAIN_DETAIL_URL_PATTERN = re.compile(r"/short-play/list/detail")
PROMOTION_CHAIN_LIST_FRAG = "/short-play/list"
PROMOTION_CHAIN_DETAIL_FRAG = "/short-play/list/detail"
PROMOTION_CHAIN_MENU_SEL = "a[href='/sale/short-play/list']"
PROMOTION_CHAIN_QUERY_SEL = "#query_input"
PROMOTION_CHAIN_SEARCH_BTN = "button:has-text('搜索')"
PROMOTION_CHAIN_ROW_SEL = "tr.arco-table-tr.e2e-promotion-table-row:visible"
PROMOTION_CHAIN_BOOK_NAME_SEL = ".book_name_content"
PROMOTION_CHAIN_VIEW_DETAIL_SEL = "text=查看详情"
PROMOTION_CHAIN_GET_LINK_BTN = "button:has-text('获取短剧推广链')"
PROMOTION_CHAIN_PROMO_INPUT_SEL = "#promotion_name_input"
PROMOTION_CHAIN_IOS_RADIO_SEL = ".arco-radio"
PROMOTION_CHAIN_CONFIRM_SEL = (
    ".arco-modal:visible button:has-text('确定'), "
    ".arco-drawer:visible button:has-text('确定')"
)
PROMOTION_CHAIN_CONFIRM_FALLBACK = "button:has-text('确定')"
_PC_CLEAN_NAME_RE = re.compile(r"[^一-龥A-Za-z0-9]")
_PC_CHINESE_ONLY_RE = re.compile(r"[^一-龥]")
PROMOTION_CHAIN_TASKS = [
    ("安卓每留", "每留", False),
    ("安卓七留", "七留", False),
    ("iOS每留", "每留", True),
    ("iOS七留", "七留", True),
]
