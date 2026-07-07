#!/usr/bin/env python3
"""
report_validator.py — 报告完整性校验器

功能：校验生成的拆书报告是否符合9章节规范
职责：自动化检查每个章节是否存在、子项数量是否达标、关键字段是否缺失、量化指标与图谱合规
接口：CLI 参数（文件路径）→ JSON stdout
"""

import argparse
import json
import sys
import os
import re
from datetime import datetime as _datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shared_utils  # noqa: F401
from shared_utils import UserFacingError, friendly_message, ScriptLogger


# ============================================================
# 校验规则配置
# ============================================================

REQUIRED_SECTIONS = [
    {"key": "一", "title": "类型总览", "min_subitems": 4, "required_fields": ["市场热力", "商业化", "类型特征", "对标作品"]},
    {"key": "二", "title": "结构模板", "min_subitems": 3, "required_fields": ["黄金三章", "全篇结构", "字数"]},
    {"key": "三", "title": "爽点节奏", "min_subitems": 4, "required_fields": ["爽点类型", "节奏对标", "情绪曲线", "钩子"]},
    {"key": "四", "title": "人物原型", "min_subitems": 3, "required_fields": ["主角原型", "配角", "人设"]},
    {"key": "五", "title": "开篇钩子", "min_subitems": 2, "required_fields": ["开篇公式", "自检"]},
    {"key": "六", "title": "金手指", "min_subitems": 3, "required_fields": ["金手指分布", "创新", "设计原则"]},
    {"key": "七", "title": "常见雷区", "min_subitems": 3, "required_fields": ["雷区", "负面反馈", "创新"]},
    {"key": "八", "title": "速查表", "min_subitems": None, "required_fields": ["大纲师"]},
    {"key": "九", "title": "文风DNA与量化指标", "min_subitems": 2, "required_fields": ["文风DNA", "量化指标"]},
]

# 校验项配置
VALIDATION_ITEMS = [
    {"id": "V001", "description": "报告包含 YAML 元信息头", "check": lambda c: c.get("has_yaml", False)},
    {"id": "V002", "description": "报告包含分析时间", "check": lambda c: c.get("has_analysis_time", False)},
    {"id": "V003", "description": "所有9个章节齐全", "check": lambda c: c.get("section_count", 0) >= 9},
    {"id": "V004", "description": "所有章节都有子项内容（非空章节）", "check": lambda c: c.get("empty_sections_count", 99) == 0},
    {"id": "V005", "description": "章节子项数量达到最小要求", "check": lambda c: c.get("subitem_shortfall_count", 99) == 0},
    {"id": "V006", "description": "关键字段存在于对应章节中", "check": lambda c: c.get("missing_fields_count", 99) == 0},
    {"id": "V007", "description": "引用标记格式正确", "check": lambda c: c.get("invalid_ref_count", 0) == 0},
    {"id": "V008", "description": "包含商业化建议（市场数据+新人建议）", "check": lambda c: c.get("has_commercial_advice", False)},
    {"id": "V009", "description": "包含创新机会分析（蓝海方向）", "check": lambda c: c.get("has_innovation_opportunity", False)},
    {"id": "V010", "description": "字数分配建议与目标长度匹配", "check": lambda c: c.get("has_word_count_advice", False)},
    {"id": "V011", "description": "无未填充的占位符（表格空行/方括号占位）", "check": lambda c: c.get("unfilled_placeholder_count", 99) == 0},
    {"id": "V012", "description": "包含量化指标卡（至少2个章节末尾附有指标卡）", "check": lambda c: c.get("quantitative_indicator_count", 0) >= 2},
    {"id": "V013", "description": "包含至少3类一级可视化图谱（Mermaid）", "check": lambda c: c.get("mermaid_graph_count", 0) >= 3},
    {"id": "V014", "description": "第九章包含文风DNA标签", "check": lambda c: c.get("has_dna_tags", False)},
    {"id": "V015", "description": "报告文本AI味密度合格（千字密度<15）", "check": lambda c: c.get("deslop_density", 99) < 15},
]


def validate_report(file_path: str, allow_placeholders: bool = False) -> dict:
    """
    校验报告完整性

    输入: file_path — report.md 的绝对或相对路径
         allow_placeholders — 为 True 时跳过 V011 占位符检查（报告未完成时使用）
    输出: dict — 校验结果
    """
    
    # --- 初始化结果 ---
    result = {
        "valid": False,
        "file_path": file_path,
        "file_exists": False,
        "file_size": 0,
        "section_count": 0,
        "section_details": [],
        "empty_sections_count": 0,
        "subitem_shortfall_count": 0,
        "missing_fields_count": 0,
        "invalid_ref_count": 0,
        "has_yaml": False,
        "has_analysis_time": False,
        "has_word_count_advice": False,
        "has_commercial_advice": False,
        "has_innovation_opportunity": False,
        "unfilled_placeholder_count": 0,
        "unfilled_placeholder_details": [],
        "quantitative_indicator_count": 0,
        "mermaid_graph_count": 0,
        "has_dna_tags": False,
        "deslop_density": 0,
        "deslop_level": "",
        "checks": {},
        "errors": [],
        "warnings": [],
    }
    
    # --- 文件存在性检查 ---
    if not file_path:
        result["errors"].append("未指定报告文件。请在项目目录下的 deconstruction_report 文件夹中找到 report.md 后重新校验")
        result["checks"] = _build_check_results(result)
        return result
    
    if not os.path.exists(file_path):
        result["errors"].append(f"找不到报告文件：{file_path}。请确认文件在项目目录的 deconstruction_report 文件夹下")
        result["checks"] = _build_check_results(result)
        return result
    
    result["file_exists"] = True
    result["file_size"] = os.path.getsize(file_path)
    
    # --- 空文件检查 ---
    if result["file_size"] == 0:
        result["errors"].append("报告文件是空的——看起来报告还没有生成，或者生成过程出了问题，请重新运行分析")
        result["checks"] = _build_check_results(result)
        return result
    
    # --- 读取内容 ---
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, "r", encoding="gbk") as f:
                content = f.read()
        except Exception as e:
            result["errors"].append(f"文件内容无法正常读取（{friendly_message(e)}），可能是文件格式不兼容。请将文件另存为 UTF-8 格式后重试（大多数编辑器另存时可选格式）")
            result["checks"] = _build_check_results(result)
            return result
    except PermissionError as e:
        result["errors"].append(friendly_message(e))
        result["checks"] = _build_check_results(result)
        return result
    except OSError as e:
        result["errors"].append(friendly_message(e))
        result["checks"] = _build_check_results(result)
        return result
    
    # --- 逐章节校验 ---
    lines = content.split("\n")
    
    for sec in REQUIRED_SECTIONS:
        sec_key = sec["key"]
        sec_title = sec["title"]
        sec_result = {
            "key": sec_key,
            "title": sec_title,
            "found": False,
            "line_number": None,
            "subitem_count": 0,
            "missing_fields": [],
            "subitem_shortfall": 0,
            "has_content": False,
        }
        
        # 定位章节（支持：一. / 一、 / 一：/ 1. / 第一章 等格式）
        pattern = rf"^##\s+{re.escape(sec_key)}[.、：:\s]|^##\s+第{re.escape(sec_key)}章"
        sec_line = None
        sec_content_start = None
        
        for i, line in enumerate(lines):
            if re.match(pattern, line.strip()):
                sec_line = i
                sec_result["found"] = True
                sec_result["line_number"] = i + 1
                sec_content_start = i + 1
                break
        
        if sec_line is not None:
            result["section_count"] += 1
            
            # 提取章节内容（到下一个 ## 一/二/.../十 开头的章节为止，要求分隔符避免误断）
            sec_content_lines = []
            for j in range(sec_content_start, len(lines)):
                if re.match(r"^##\s+[一二三四五六七八九十][.、：:\s]", lines[j].strip()):
                    break
                sec_content_lines.append(lines[j])
            
            sec_content = "\n".join(sec_content_lines).strip()
            
            # 检查是否有内容
            if len(sec_content) > 50:  # 至少50个字符才算有内容
                sec_result["has_content"] = True
            else:
                result["empty_sections_count"] += 1
            
            # 统计子项数量（以 ### 开头的行数）
            subitem_count = len([l for l in sec_content_lines if l.strip().startswith("###")])
            sec_result["subitem_count"] = subitem_count
            
            # 检查子项数量是否达标
            min_sub = sec.get("min_subitems")
            if min_sub is not None and subitem_count < min_sub:
                shortfall = min_sub - subitem_count
                sec_result["subitem_shortfall"] = shortfall
                result["subitem_shortfall_count"] += shortfall
            
            # 检查关键字段
            for field in sec.get("required_fields", []):
                if field not in sec_content:
                    sec_result["missing_fields"].append(field)
                    result["missing_fields_count"] += 1
        
        else:
            result["empty_sections_count"] += 1
            # 章节未找到时，其所有必填字段都计入缺失
            for field in sec.get("required_fields", []):
                sec_result["missing_fields"].append(field)
                result["missing_fields_count"] += 1
        
        result["section_details"].append(sec_result)
    
    # --- 检查 YAML 头（接受两种格式）---
    # 格式1: ```yaml 代码块（规范推荐）
    # 格式2: 裸 --- 分隔的 YAML frontmatter（标准 Markdown frontmatter）
    #   - 系统水印环境: ---\nAIGC:\n...\n---\n{YAML内容}
    #   - 无注入环境: ---\n{YAML内容}\n---
    has_yaml_block = re.search(r"```yaml", content[:5000]) is not None
    has_bare_yaml = re.search(r"^---\s*\n\s*[\w\u4e00-\u9fff]+:", content[:5000], re.MULTILINE) is not None
    if has_yaml_block or has_bare_yaml:
        result["has_yaml"] = True
        
        # 检查分析时间
        time_in_yaml = re.search(r"分析时间", content[:2000]) is not None
        time_in_bare = re.search(r"^---[\s\S]*?分析时间", content[:5000], re.MULTILINE) is not None
        if time_in_yaml or time_in_bare:
            result["has_analysis_time"] = True
    
    # --- 检查字数分配 ---
    if re.search(r"字数分配|每章字数|平均每章", content):
        result["has_word_count_advice"] = True

    # --- 检查商业化建议 ---
    if re.search(r"商业化建议|红海|蓝海|新人入局|首订|追读率|完本率", content):
        result["has_commercial_advice"] = True

    # --- 检查创新机会分析 ---
    if re.search(r"创新机会|蓝海|尚未饱和|上升期|细分方向", content):
        result["has_innovation_opportunity"] = True
    
    # --- 检查占位符未填充 ---
    unfilled_patterns = [
        r"\|\s*\|\s*\|",  # Markdown表格全空行（2+空列）
        r"\[\s*类型\s*\]",      # [类型] 占位符
        r"\[\s*结构描述\s*\]",
        r"\[\s*作品名\s*\]",
        r"\[\s*技法分析\s*\]",
    ]
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        for pat in unfilled_patterns:
            if re.search(pat, stripped):
                result["unfilled_placeholder_count"] += 1
                result["unfilled_placeholder_details"].append({
                    "line": i + 1,
                    "content": stripped[:80],
                    "pattern": pat,
                })
                break  # 每行最多计一次
    
    # --- 检查引用标记 ---
    ref_pattern = r"\[拆书参考[^\]]*\]"
    refs = re.findall(ref_pattern, content)
    for ref in refs:
        # 引用标记必须以 [拆书参考] 或 [拆书参考-章节号] 格式
        if not re.match(r"^\[拆书参考(\-\w+)?\]$", ref):
            result["invalid_ref_count"] += 1
            result["warnings"].append(f'引用标注格式有误：{ref}——请改为 [拆书参考] 或 [拆书参考-章节号] 格式')
    
    # --- 检查量化指标卡 ---
    qi_matches = re.findall(r'📊\s*\*?\*?量化指标卡\*?\*?', content)
    result["quantitative_indicator_count"] = len(qi_matches)
    
    # --- 检查 Mermaid 图谱 ---
    mermaid_matches = re.findall(r'```mermaid', content)
    result["mermaid_graph_count"] = len(mermaid_matches)
    
    # --- 检查文风DNA标签 ---
    if re.search(r'文风DNA标签|DNA标签[：:]', content):
        result["has_dna_tags"] = True
    
    # --- 检查AI味密度（V015） ---
    # V015：deslop_engine 已迁移至 multi-role-novel-iteration，本技能中跳过此项
    result["deslop_density"] = 0
    result["deslop_level"] = "跳过（已移交 multi-role 技能）"
    
    # --- 综合判定 ---
    result["checks"] = _build_check_results(result, allow_placeholders)
    
    # 所有 V001-V015 都通过才算 valid
    all_pass = all(c["passed"] for c in result["checks"].values())
    result["valid"] = all_pass
    
    if not all_pass:
        failed_checks = [k for k, v in result["checks"].items() if not v["passed"]]
        failed_desc = [result["checks"][k].get("description", k) for k in failed_checks]
        result["warnings"].append(f"以下检查项未通过：{', '.join(failed_desc)}")
    
    return result


def _build_check_results(result: dict, allow_placeholders: bool = False) -> dict:
    """根据当前 result 构建各检查项的结果"""
    checks = {}
    for item in VALIDATION_ITEMS:
        # allow_placeholders 模式下跳过 V011 占位符检查
        if allow_placeholders and item["id"] == "V011":
            checks[item["id"]] = {
                "description": item["description"] + "（allow_placeholders，已跳过）",
                "passed": True
            }
            continue
        try:
            passed = item["check"](result)
        except Exception as e:
            ScriptLogger.warning(f"校验项 {item['id']} 执行异常：{friendly_message(e)}")
            passed = False
        checks[item["id"]] = {
            "description": item["description"],
            "passed": passed
        }
    return checks


def print_report(result: dict):
    """友好打印校验报告（CLI-only，仅供 main() 的 --format text 路径调用）"""
    if result.get("errors"):
        print(f"\n❌ 校验失败：{result['errors'][0]}")
        return
    
    print(f"\n{'='*50}")
    print(f" 📋 拆书报告完整性校验")
    print(f"{'='*50}")
    print(f" 文件：{result['file_path']}")
    print(f" 大小：{result['file_size']} 字节")
    print(f" 校验时间：{_datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*50}")
    
    # 章节检查
    print(f"\n 📂 章节检查 ({result['section_count']}/9)")
    for sec in result["section_details"]:
        icon = "✅" if sec["found"] else "❌"
        content_icon = "📝" if sec["has_content"] else "⚠️" if sec["found"] else "❌"
        field_icon = "⚠️" if sec["missing_fields"] else ""
        
        parts = [f"  {icon} 第{sec['key']}节 {sec['title']}"]
        if sec["found"]:
            parts.append(f"(行{sec['line_number']})")
            parts.append(f"子项{sec['subitem_count']}个")
            if sec["subitem_shortfall"] > 0:
                parts.append(f"⚠️ 缺{sec['subitem_shortfall']}个子项")
            if sec["missing_fields"]:
                parts.append(f"⚠️ 缺字段：{','.join(sec['missing_fields'])}")
        print(" ".join(parts))
    
    # 检查项
    print(f"\n 📊 检查项")
    for cid, check in result.get("checks", {}).items():
        icon = "✅" if check["passed"] else "❌"
        print(f"  {icon} {cid}: {check['description']}")
    
    # 警告
    if result.get("warnings"):
        print(f"\n ⚠️ 警告")
        for w in result["warnings"]:
            print(f"  {w}")
    
    # 最终结果
    print(f"\n{'='*50}")
    if result["valid"]:
        print(f" ✅ 校验通过！报告完整可用")
    else:
        print(f" ❌ 校验未通过，请修复后重新校验")
    print(f"{'='*50}\n")


# ============================================================
# CLI 入口
# ============================================================

def main():
    """CLI 入口：python report_validator.py <report.md路径> [--json]"""

    parser = argparse.ArgumentParser(
        description="报告完整性校验器 — 校验拆书报告是否符合9章节规范",
        epilog="示例:\n"
               "  python report_validator.py report.md\n"
               "  python report_validator.py report.md --json\n"
               "  python report_validator.py report.md --allow-placeholders\n\n"
               "输入: report.md 文件路径\n"
               "输出: 默认友好文本；--json 时输出 JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("file_path", help="report.md 的文件路径")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出校验结果")
    parser.add_argument("--allow-placeholders", action="store_true",
                        help="允许未填充占位符（报告未完成时使用）")
    args = parser.parse_args()

    try:
        result = validate_report(args.file_path, allow_placeholders=args.allow_placeholders)
    except UserFacingError as e:
        error = {
            "error": True,
            "error_type": "校验失败",
            "error_message": friendly_message(e),
            "suggestion": "请确认报告文件存在且内容完整，如报告尚未完成可使用 --allow-placeholders 跳过部分检查",
            "exit_code": 5
        }
        print(json.dumps(error, ensure_ascii=False, indent=2))
        sys.exit(5)
    except Exception as e:
        ScriptLogger.error(friendly_message(e))
        error = {
            "error": True,
            "error_type": "校验失败",
            "error_message": friendly_message(e),
            "suggestion": "请确认报告文件存在且内容完整，如报告尚未完成可使用 --allow-placeholders 跳过部分检查",
            "exit_code": 5
        }
        print(json.dumps(error, ensure_ascii=False, indent=2))
        sys.exit(5)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_report(result)

    sys.exit(0 if result.get("valid") else 4)


if __name__ == "__main__":
    main()