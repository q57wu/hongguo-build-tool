"""
backend/core/exceptions.py
业务异常类。
"""


class AccountsMissingError(Exception):
    """媒体账户在投放后台搜索不到时抛出。"""

    def __init__(self, missing_ids, found_count, input_count):
        self.missing_ids = list(missing_ids)
        self.found_count = found_count
        self.input_count = input_count
        super().__init__(
            f"媒体账户缺失: 输入 {input_count} 个，搜到 {found_count} 个，"
            f"缺失 {len(self.missing_ids)} 个: {self.missing_ids}"
        )


class BuildSubmitError(Exception):
    """提交审核关键步骤失败时抛出（如未出现"转为后台提交"按钮）。"""
    pass


class StopRequested(Exception):
    """搭建过程中被外部 stop_event 中断时抛出。"""
    pass


def check_stop(stop_event):
    """检测 stop_event 是否被设置，若是则抛出 StopRequested。"""
    if stop_event and stop_event.is_set():
        raise StopRequested()
