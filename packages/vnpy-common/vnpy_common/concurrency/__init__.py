"""跨模块共享并发设施。"""

from vnpy_common.concurrency.io_pool import get_io_executor, global_io_max_workers, shutdown_io_executor

__all__ = ["get_io_executor", "global_io_max_workers", "shutdown_io_executor"]
