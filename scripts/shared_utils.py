#!/usr/bin/env python3
"""
shared_utils.py — 共享工具函数

提供：
- ensure_utf8_stdout() UTF-8 编码处理
- _fuzzy_match_type() 模糊匹配
- UserFacingError / friendly_message / handle_exception 异常体系
- safe_read_text / safe_write_text / safe_write_json 文件安全读写
- with_retry 自动重试机制
- ScriptLogger 标准化日志
"""

import sys
import json
import time
import functools


def ensure_utf8_stdout():
    """强制 stdout/stderr 使用 UTF-8 编码，修复 Windows GBK 环境下 emoji 输出崩溃"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            try:
                stream.reconfigure(encoding='utf-8')
            except (ValueError, OSError):
                pass  # 流已关闭或不可重配置，跳过


# 模块加载时自动执行 UTF-8 编码配置
ensure_utf8_stdout()


# ══════════════════════════════════════════════════════════════
# 异常体系
# ══════════════════════════════════════════════════════════════

class UserFacingError(Exception):
    """携带通俗中文提示的异常，脚本应优先使用此类而非 Python 内置异常。

    用法：raise UserFacingError("文件未找到，请检查路径是否正确")
    """
    pass


def friendly_message(exc: Exception) -> str:
    """将 Python 异常翻译为通俗中文提示，避免暴露技术术语。

    - UserFacingError：直接返回其消息（已是通俗中文）
    - 其他异常：按类型映射，兜底给出通用中文提示
    """
    if isinstance(exc, UserFacingError):
        return str(exc)

    _MAP = {
        FileNotFoundError: "文件未找到，请检查路径是否正确",
        PermissionError: "没有文件访问权限，请检查文件是否被其他程序占用",
        IsADirectoryError: "指定路径是文件夹而非文件，请检查路径",
        UnicodeDecodeError: "文件编码无法识别，请确保文件是 UTF-8 格式保存",
        json.JSONDecodeError: "文件内容格式有误，无法解析，请检查文件是否损坏",
        ValueError: "输入内容有误，请检查后重试",
        TypeError: "输入类型不正确，请检查参数",
        KeyError: "缺少必要的数据项，请检查文件内容是否完整",
        IndexError: "数据索引超出范围，请检查文件内容是否完整",
        OSError: "文件操作失败，请检查磁盘空间和文件权限",
    }

    for exc_type, msg in _MAP.items():
        if isinstance(exc, exc_type):
            return msg

    return "操作未能完成，请检查输入文件和路径是否正确"


class ScriptLogger:
    """脚本日志管理器"""

    @staticmethod
    def info(message: str):
        print(f"[信息]  {message}", file=sys.stderr)

    @staticmethod
    def success(message: str):
        print(f"[成功] {message}", file=sys.stderr)

    @staticmethod
    def warning(message: str):
        print(f"[警告]  {message}", file=sys.stderr)

    @staticmethod
    def error(message: str):
        print(f"[错误] {message}", file=sys.stderr)


def handle_exception(func):
    """异常处理装饰器（用通俗中文提示记录日志后重新抛出，由 main() 统一捕获并优雅退出）"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            ScriptLogger.error(friendly_message(e))
            raise
    return wrapper


# ══════════════════════════════════════════════════════════════
# 文件安全读写
# ══════════════════════════════════════════════════════════════

def safe_read_text(path, min_chars: int = 0, max_chars: int = 0, label: str = "文件") -> str:
    """安全读取文本文件，统一处理编码错误、空文件和长度异常。

    Args:
        path: 文件路径（str 或 Path）
        min_chars: 最低字符数要求，0 表示不限制
        max_chars: 最大字符数警告阈值，0 表示不限制
        label: 文件用途描述（用于提示信息），如 "报告" "会话历史"

    Returns:
        文件文本内容

    Raises:
        UserFacingError: 文件不存在 / 编码错误 / 内容为空 / 内容过短
    """
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        raise UserFacingError(f"{label}不存在，请检查路径：{p}")
    # 自动重试读取：应对文件被瞬时锁定
    max_retries = 2
    text = None
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            text = p.read_text(encoding='utf-8')
            break
        except UnicodeDecodeError:
            raise UserFacingError(f"{label}编码无法识别，请确保是 UTF-8 格式：{p}")
        except PermissionError as e:
            last_exc = e
            if attempt < max_retries:
                ScriptLogger.warning(f"{label}读取被占用，1 秒后自动重试...")
                time.sleep(1.0)
            else:
                raise UserFacingError(f"{label}无法读取，可能被其他程序占用：{p}")
    if text is None:
        raise UserFacingError(f"{label}无法读取：{p}")
    text = text.strip()
    if not text:
        raise UserFacingError(f"{label}内容为空，请检查：{p}")
    if min_chars > 0 and len(text) < min_chars:
        raise UserFacingError(
            f"{label}内容太短（当前 {len(text)} 字，建议至少 {min_chars} 字），"
            f"检查结果可能不准确。建议补充内容后再试"
        )
    if max_chars > 0 and len(text) > max_chars:
        ScriptLogger.warning(f"{label}内容较长（{len(text)} 字），处理时间可能较久")
    return text


def safe_write_text(path, content: str, label: str = "文件") -> None:
    """安全写入文本文件，带自动重试和写入验证。

    Args:
        path: 文件路径（str 或 Path）
        content: 要写入的文本内容
        label: 文件用途描述

    Raises:
        UserFacingError: 写入失败（权限不足、磁盘满等）
    """
    from pathlib import Path
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        raise UserFacingError(f"{label}写入失败，无法创建目录，请检查权限：{p.parent}")
    except OSError as e:
        raise UserFacingError(f"{label}写入失败，无法创建目录：{p.parent}（{friendly_message(e)}）")

    @with_retry(max_retries=2, delay=1.0)
    def _write():
        try:
            p.write_text(content, encoding='utf-8')
        except PermissionError:
            raise UserFacingError(f"{label}写入失败，文件可能被其他程序占用：{p}")
        except OSError as e:
            raise UserFacingError(f"{label}写入失败，请检查磁盘空间和权限：{p}（{friendly_message(e)}）")

    _write()


def safe_write_json(path, data, label: str = "文件") -> None:
    """安全写入 JSON 文件，带自动重试。

    Args:
        path: 文件路径
        data: 要序列化的数据
        label: 文件用途描述

    Raises:
        UserFacingError: 写入失败
    """
    content = json.dumps(data, ensure_ascii=False, indent=2)
    safe_write_text(path, content, label)


# ══════════════════════════════════════════════════════════════
# 自动重试机制
# ══════════════════════════════════════════════════════════════

def with_retry(func=None, *, max_retries: int = 2, delay: float = 1.0,
               retry_on: tuple = (OSError, PermissionError, UnicodeDecodeError)):
    """为函数添加自动重试，应对文件锁定、编码等瞬时故障。

    用法1（装饰器）：@with_retry
    用法2（装饰器带参）：@with_retry(max_retries=3, delay=2.0)
    用法3（直接调用）：result = with_retry(some_func, max_retries=2)(arg1, arg2)
    """
    if func is not None and callable(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retry_on as e:
                    last_exc = e
                    if attempt < max_retries:
                        ScriptLogger.warning(
                            f"第 {attempt + 1} 次尝试失败（{friendly_message(e)}），"
                            f"{delay} 秒后自动重试..."
                        )
                        time.sleep(delay)
                    else:
                        raise
            raise last_exc  # unreachable, but keeps linters happy
        return wrapper

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except retry_on as e:
                    last_exc = e
                    if attempt < max_retries:
                        ScriptLogger.warning(
                            f"第 {attempt + 1} 次尝试失败（{friendly_message(e)}），"
                            f"{delay} 秒后自动重试..."
                        )
                        time.sleep(delay)
                    else:
                        raise
            raise last_exc
        return wrapper
    return decorator


# ══════════════════════════════════════════════════════════════
# 原有工具函数
# ══════════════════════════════════════════════════════════════

def _fuzzy_match_type(type_name: str, mapping: dict) -> tuple:
    """模糊匹配类型名称到映射表键，返回 (matched_key, template)"""
    if type_name in mapping:
        return type_name, mapping[type_name]
    for key in mapping:
        if key in type_name or type_name in key:
            return key, mapping[key]
    for key in mapping:
        for part in key.replace("/", " ").split():
            if len(part) >= 2 and part in type_name:
                return key, mapping[key]
        clean_key = key.replace("/", "")
        if clean_key in type_name or type_name in clean_key:
            return key, mapping[key]
        overlap = sum(1 for c in key if c != "/" and c in type_name)
        if overlap >= len(key.replace("/", "")) * 0.5 and overlap >= 2:
            return key, mapping[key]
    return None, None
