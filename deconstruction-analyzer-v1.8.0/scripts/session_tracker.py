#!/usr/bin/env python3
"""
session_tracker.py — 拆书分析会话追踪器

功能：记录每次拆书分析的上下文，支持增量分析和迭代更新
职责：管理分析历史的读/写/查询，不涉及AI判断
接口：CLI 命令 → JSON stdout

用法：
  python session_tracker.py init --type "都市修仙" --project "/path/to/project"
  python session_tracker.py add --works "作品1" "作品2" "作品3"
  python session_tracker.py get
  python session_tracker.py list
  python session_tracker.py diff <session_id_old> <session_id_new>
"""

import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shared_utils  # noqa: F401
from shared_utils import UserFacingError, friendly_message, safe_write_json, ScriptLogger

# ============================================================
# 会话文件路径
# ============================================================

def _get_session_path(project_dir: str = None) -> str:
    """获取会话文件的路径"""
    if project_dir:
        base = project_dir
    else:
        base = os.environ.get("DECONSTRUCTION_PROJECT", os.getcwd())
    return os.path.join(base, "deconstruction_report", ".session_history.json")


def _load_history(project_dir: str = None) -> dict:
    """加载会话历史"""
    path = _get_session_path(project_dir)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            ScriptLogger.warning("会话历史文件格式异常，已重置")
        except (IOError, OSError) as e:
            ScriptLogger.warning(friendly_message(e))
    return {"sessions": [], "current_session_id": None, "project_type": None, "project_dir": project_dir or ""}


def _save_history(history: dict, project_dir: str = None) -> None:
    """保存会话历史"""
    path = _get_session_path(project_dir)
    try:
        safe_write_json(path, history, label="会话历史")
    except UserFacingError:
        raise


# ============================================================
# 命令
# ============================================================

def cmd_init(args):
    """初始化一个新的分析项目会话"""
    project_dir = args.get("project", "")
    type_name = args.get("type", "通用")

    history = _load_history(project_dir)
    history["project_type"] = type_name
    history["project_dir"] = project_dir

    # 创建新session（ID基于已有数量递增，避免重复）
    new_id = len(history["sessions"]) + 1
    session = {
        "session_id": new_id,
        "type": type_name,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "analyzed_works": [],
        "analysis_focus": "全面分析",
        "iterations": [],
    }
    history["sessions"].append(session)
    history["current_session_id"] = new_id
    _save_history(history, project_dir)

    return {"status": "ok", "session_id": new_id, "type": type_name, "message": f"初始化成功：{type_name}分析项目"}


def cmd_add(args):
    """在当前会话中添加分析过的作品"""
    project_dir = args.get("project", "")
    works = args.get("works", [])
    focus = args.get("focus", "全面分析")

    history = _load_history(project_dir)
    if not history["sessions"]:
        return {"status": "error", "message": "还没有开始过分析，请先告诉我项目目录和要拆的类型，我来帮你初始化"}

    session = history["sessions"][-1]
    session["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if focus:
        session["analysis_focus"] = focus

    for work in works:
        if work not in session["analyzed_works"]:
            session["analyzed_works"].append(work)

    # 记录迭代
    iteration = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "added_works": works,
        "focus": focus,
        "iteration_number": len(session["iterations"]) + 1,
    }
    session["iterations"].append(iteration)
    _save_history(history, project_dir)

    return {
        "status": "ok",
        "session_id": history["current_session_id"],
        "analyzed_works": session["analyzed_works"],
        "iterations": len(session["iterations"]),
        "message": f"已更新：累计分析{len(session['analyzed_works'])}部作品，第{len(session['iterations'])}轮迭代"
    }


def cmd_get(args):
    """获取当前会话的状态"""
    project_dir = args.get("project", "")
    history = _load_history(project_dir)

    if not history["sessions"]:
        return {"status": "error", "message": "还没有分析记录，先拆一次书吧"}

    session = history["sessions"][-1]
    return {
        "status": "ok",
        "session_id": session["session_id"],
        "type": session["type"],
        "analyzed_works": session["analyzed_works"],
        "analysis_focus": session["analysis_focus"],
        "iteration_count": len(session["iterations"]),
        "created_at": session["created_at"],
        "updated_at": session["updated_at"],
        "has_previous_sessions": len(history["sessions"]) > 1,
    }


def cmd_list(args):
    """列出所有会话"""
    project_dir = args.get("project", "")
    history = _load_history(project_dir)

    sessions_info = []
    for s in history["sessions"]:
        sessions_info.append({
            "session_id": s["session_id"],
            "type": s["type"],
            "analyzed_works_count": len(s["analyzed_works"]),
            "iterations": len(s["iterations"]),
            "created_at": s["created_at"],
        })

    return {
        "status": "ok",
        "current_session_id": history["current_session_id"],
        "total_sessions": len(history["sessions"]),
        "sessions": sessions_info,
    }


def cmd_diff(args):
    """对比两个会话的差异（增量分析用）"""
    project_dir = args.get("project", "")
    history = _load_history(project_dir)
    
    # 默认对比最后两个会话
    session_id_old = args.get("old")
    session_id_new = args.get("new")
    
    if session_id_old is None and len(history["sessions"]) >= 2:
        session_id_old = history["sessions"][-2]["session_id"]
    if session_id_new is None and len(history["sessions"]) >= 1:
        session_id_new = history["sessions"][-1]["session_id"]

    history = _load_history(project_dir)
    old_session = None
    new_session = None

    for s in history["sessions"]:
        if s["session_id"] == session_id_old:
            old_session = s
        if s["session_id"] == session_id_new:
            new_session = s

    if not old_session or not new_session:
        return {"status": "error", "message": f"找不到之前的分析记录，可能还没做完两次分析。当前已有的记录数：{len(history['sessions'])}"}

    old_works = set(old_session["analyzed_works"])
    new_works = set(new_session["analyzed_works"])

    return {
        "status": "ok",
        "old_session": session_id_old,
        "new_session": session_id_new,
        "added_works": list(new_works - old_works),
        "removed_works": list(old_works - new_works),
        "common_works": list(old_works & new_works),
        "focus_change": old_session["analysis_focus"] != new_session["analysis_focus"],
        "old_focus": old_session["analysis_focus"],
        "new_focus": new_session["analysis_focus"],
    }


# ============================================================
# CLI 入口
# ============================================================

COMMANDS = {
    "init": cmd_init,
    "add": cmd_add,
    "get": cmd_get,
    "list": cmd_list,
    "diff": cmd_diff,
}


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="拆书分析会话追踪器 — 记录分析上下文，支持增量分析和迭代更新",
        epilog="示例:\n"
               "  python session_tracker.py init --type '都市修仙' --project /path/to/project\n"
               "  python session_tracker.py add --works '作品1' '作品2'\n"
               "  python session_tracker.py get\n"
               "  python session_tracker.py list\n"
               "  python session_tracker.py diff --old 1 --new 2\n\n"
               "输入: 命令 + 参数\n"
               "输出: JSON stdout（会话状态/历史/差异）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    p_init = subparsers.add_parser("init", help="初始化新项目会话")
    p_init.add_argument("--type", "-t", default=None, help="分析类型")
    p_init.add_argument("--project", "-p", required=True, help="项目路径（必需）")

    p_add = subparsers.add_parser("add", help="添加分析作品")
    p_add.add_argument("--works", "-w", nargs="+", default=[], help="作品列表")
    p_add.add_argument("--focus", "-f", default=None, help="分析焦点")
    p_add.add_argument("--project", "-p", required=True, help="项目路径（必需）")

    p_get = subparsers.add_parser("get", help="获取当前会话状态")
    p_get.add_argument("--project", "-p", required=True, help="项目路径（必需）")

    p_list = subparsers.add_parser("list", help="列出所有会话")
    p_list.add_argument("--project", "-p", required=True, help="项目路径（必需）")

    p_diff = subparsers.add_parser("diff", help="对比两个会话差异")
    p_diff.add_argument("--old", type=int, default=None, help="旧会话ID")
    p_diff.add_argument("--new", type=int, default=None, help="新会话ID")
    p_diff.add_argument("--project", "-p", required=True, help="项目路径（必需）")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    params = {
        "project": getattr(args, "project", None),
        "type": getattr(args, "type", None),
        "works": getattr(args, "works", []),
        "focus": getattr(args, "focus", None),
        "old": getattr(args, "old", None),
        "new": getattr(args, "new", None),
    }

    try:
        result = COMMANDS[args.command](params)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result.get("status") == "ok" else 1)
    except UserFacingError as e:
        result = {"error": True, "error_message": friendly_message(e), "suggestion": "确认项目目录存在且可写入。如果反复出现问题，可以重新开始一次拆书分析"}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(2)
    except Exception as e:
        ScriptLogger.error(friendly_message(e))
        result = {"error": True, "error_message": friendly_message(e), "suggestion": "确认项目目录存在且完整。如果反复出现问题，可以重新开始一次拆书分析"}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(2)


if __name__ == "__main__":
    main()
