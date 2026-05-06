# backend/core package
#
# 模块说明：
#   constants       — 常量、PROFILES、WaitTimes、异常类
#   config_io       — config.json / build_records / material_history 读写
#   data_parsers    — 纯数据解析函数（无 Playwright 依赖）
#   build_steps     — 单本搭建 step_xxx 函数 + run_build 入口
#   incentive_steps — 激励搭建 step_xxx 函数 + run_build_incentive 入口
#   promo_chain     — 推广链生成工具（_pc_xxx + run_promotion_chain）
#   incentive_tools — 激励推广链 & 素材推送（run_incentive_promo_chain / run_incentive_push）
