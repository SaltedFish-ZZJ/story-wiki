"""
Story Wiki - 自定义异常层次
为不同类型的错误提供具体的异常类型，便于上层捕获和处理。
"""


class StoryWikiError(Exception):
    """项目基础异常，所有自定义异常的父类。"""

    def __init__(self, message: str = "", *, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


class APIError(StoryWikiError):
    """API 调用失败（网络错误、限流、服务端错误等）。"""

    def __init__(
        self,
        message: str = "API 调用失败",
        *,
        status_code: int | None = None,
        retry_after: float | None = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.status_code = status_code
        self.retry_after = retry_after


class ParseError(StoryWikiError):
    """AI 响应或 JSON 解析失败。"""

    def __init__(
        self,
        message: str = "响应解析失败",
        *,
        raw_response: str | None = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.raw_response = raw_response


class ValidationError(StoryWikiError):
    """输入数据校验失败。"""

    def __init__(
        self,
        message: str = "数据校验失败",
        *,
        field: str | None = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.field = field


class ConfigError(StoryWikiError):
    """配置缺失或不合法。"""


class FileOperationError(StoryWikiError):
    """文件读写操作失败。"""

    def __init__(
        self,
        message: str = "文件操作失败",
        *,
        file_path: str | None = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.file_path = file_path


class QualityCheckError(StoryWikiError):
    """质量检查流程中出现不可恢复的错误。"""
