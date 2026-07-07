#!/usr/bin/env python3
"""
type_router.py — 网文类型路由引擎（已整合 intent_mapper 意图诊断功能）

功能：根据用户输入的类型描述，匹配三级分类树，返回路由配置（路径+权重+意图）
职责：确定性匹配算法，不涉及AI判断
接口：CLI参数 / JSON stdin 输入 → JSON stdout 输出

整合说明：
  - 已将 intent_mapper.map_intent() 吸收进 route() 流程
  - route() 返回结果新增 `intent` 字段（intent_id/label/icon/step3_focus/step5_focus/extra_output/analysis_weight_shift）
  - 当 intent.analysis_weight_shift 非 None 时，逐 key 覆盖大类默认 weights
"""

import argparse
import json
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))
import shared_utils  # noqa: F401
from shared_utils import UserFacingError, friendly_message, ScriptLogger
from taxonomy_data import (
    SYNONYM_MAP, TAXONOMY, TYPE_TO_WRITING_MODE, WEIGHT_MATRIX,
    REFERENCE_FILE_MAP, RHYTHM_PROFILE_MAP,
    OPENING_FORMULA_HINT_MAP, FORMULA_MAP, FORMULA_BY_WORDCOUNT,
)
from intent_mapper import map_intent, INTENT_MAP as _INTENT_MAP


def _build_intent_field(intent_result: dict) -> dict:
    """从 map_intent 输出构建 route() 的 intent 字段"""
    iid_key = intent_result["intent_id"]
    intent_data = _INTENT_MAP.get(iid_key, _INTENT_MAP["full"])
    return {
        "intent_id": intent_data["id"],
        "intent_label": intent_result["intent_label"],
        "intent_icon": intent_result["intent_icon"],
        "step3_focus": intent_result["strategy"]["step3_focus"],
        "step5_focus": intent_result["strategy"]["step5_focus"],
        "extra_output": intent_result["strategy"]["extra_output"],
        "analysis_weight_shift": intent_result["strategy"]["analysis_weight_shift"],
    }

def _tokenize(text: str) -> list:
    """将输入拆分为特征词（去停用词、标点）"""
    if not text or not text.strip():
        return []
    # 移除常见标点和空格，按中文字符分割
    clean = re.sub(r'[^\u4e00-\u9fff\w]', ' ', text)
    # 拆分为词（2~6字滑动窗口，兼顾中文词汇）
    words = clean.split()
    result = []
    for w in words:
        w = w.strip()
        if w and len(w) >= 1 and w not in ('的', '了', '是', '在', '有', '不', '我', '就', '这', '那', '也', '和', '与', '要', '会', '可', '以', '能', '对', '为', '之', '上', '下', '大', '小'):
            result.append(w)
    return result


def _keyword_score(item_keywords: list, tokens: list) -> int:
    """计算一组关键词与输入tokens的匹配分数（单向：关键词 ∈ token）"""
    if not item_keywords or not tokens:
        return 0
    score = 0
    for kw in item_keywords:
        for token in tokens:
            # 双向子串匹配，但单字符token不触发反向包含（避免"水"匹配"水平"）
            if kw in token:
                score += 1
            elif token in kw and len(token) >= 2:
                score += 1
    return score


def _find_best_match(parent, tokens, level=1):
    """
    递归匹配：在 parent 的 children 中找最佳匹配
    返回 (path, match_level)
      path: [(name, data), ...] 从当前level开始的所有匹配节点列表
      match_level: 最深匹配层级
    """
    children = parent.get("children", {})
    if not children:
        return [], level

    best_name = None
    best_data = None
    best_score = -1

    for cname, cdata in children.items():
        ckeywords = cdata.get("keywords", [])
        score = _keyword_score(ckeywords, tokens)
        if score > best_score:
            best_score = score
            best_name = cname
            best_data = cdata

    # 没匹配到任何子节点
    if best_score <= 0:
        return [], level

    # 在这个子节点下继续递归
    sub_path, sub_level = _find_best_match(best_data, tokens, level + 1)
    if sub_path:
        return [(best_name, best_data)] + sub_path, sub_level

    return [(best_name, best_data)], level


def _collect_all_extra_dims(node):
    """递归收集一个节点及其所有子节点的 extra_dimensions"""
    dims = set()
    dims.update(node.get("extra_dimensions", []))
    for child in node.get("children", {}).values():
        dims.update(_collect_all_extra_dims(child))
    return sorted(dims)


def _infer_thrillpoint_focus(weights: dict) -> list:
    """根据权重推断该类型侧重的爽点类别"""
    focus = []
    if weights.get("金手指", 3) >= 4:
        focus.append("升级类")
        focus.append("收获类")
    if weights.get("节奏", 3) >= 4:
        focus.append("打脸类")
        focus.append("逆袭类")
    if weights.get("人物", 3) >= 4:
        focus.append("情感类")
        focus.append("揭秘类")
    if weights.get("开篇", 3) >= 4:
        focus.append("逆袭类")
        focus.append("装逼类")
    if not focus:
        focus = ["逆袭类", "打脸类", "升级类"]
    # 去重保序
    seen = set()
    return [x for x in focus if not (x in seen or seen.add(x))]


def _default_result(query: str, desc_suffix: str) -> dict:
    """构造未匹配的默认路由结果"""
    intent_result = map_intent(query) if query else None
    if intent_result:
        intent_field = _build_intent_field(intent_result)
    else:
        intent_field = {
            "intent_id": "F",
            "intent_label": "全面分析",
            "intent_icon": "🔬",
            "step3_focus": "所有6维度",
            "step5_focus": "标准9章节",
            "extra_output": "完整报告",
            "analysis_weight_shift": None,
        }
    return {
        "matched": False,
        "query": query,
        "major_category": None,
        "minor_category": None,
        "sub_category": None,
        "path_ids": [],
        "path_names": [],
        "match_level": 0,
        "weights": {"结构": 3, "节奏": 3, "人物": 3, "金手指": 3, "开篇": 3, "雷区": 3},
        "extra_dimensions": [],
        "analysis_focus_description": f"通用分析（{desc_suffix}）",
        "cross_type_info": None,
        "writing_mode": "web",
        "error": None,
        "reference_files": ["素材-爽点库.md", "素材-问题诊断.md", "report-template.md", "genre-taxonomy.md"],
        "rhythm_profile": {"快慢": "中等", "密度": "中等", "张弛": "平衡", "紧缓": "交替"},
        "opening_formula_hint": {"推荐": ["A（冲突导入型）"], "避开": ["大段设定铺陈"]},
        "thrillpoint_focus": ["逆袭类", "打脸类", "升级类"],
        "intent": intent_field,
        "suggestion": f"未匹配到内置类型，将使用通用分析。如需更精准：1) 尝试更常见的类型表述（如'末世'而非'末日废土'）；2) 也可直接继续，通用分析仍可参考。",
    }


def route(query: str) -> dict:
    """
    主路由函数
    
    输入: query - 用户类型描述字符串
    输出: dict - 路由配置
    """
    # --- 空值/错值处理 ---
    if not query:
        return _default_result("", "未匹配到具体类型")

    # --- 分词 ---
    tokens = _tokenize(query)
    if not tokens:
        return _default_result(query, "输入内容无法识别")

    # --- 同义词扩展
    expanded_tokens = set(tokens)
    for token in tokens:
        if token in SYNONYM_MAP:
            for syn in SYNONYM_MAP[token]:
                expanded_tokens.add(syn)
    tokens = list(expanded_tokens)

    # --- 大类匹配 ---
    major_scores = {}
    for mname, mdata in TAXONOMY.items():
        score = _keyword_score(mdata.get("keywords", []), tokens)
        if score > 0:
            major_scores[mname] = score

    if not major_scores:
        return _default_result(query, f"未识别到已知类型：{query}")

    # --- 交叉类型检测（同时命中多个大类 + 关键词推断）---
    cross_type_info = None
    
    # 方式1：多大类同时命中
    if len(major_scores) >= 2:
        sorted_majors = sorted(major_scores.items(), key=lambda x: -x[1])
        top_major = sorted_majors[0][0]
        second_major = sorted_majors[1][0]
        
        if sorted_majors[1][1] >= 1:
            cross_type_info = {
                "primary": top_major,
                "secondary": second_major,
                "primary_score": sorted_majors[0][1],
                "secondary_score": sorted_majors[1][1],
                "all_matches": {k: v for k, v in sorted_majors}
            }
    
    # 方式2：关键词推断交叉（单大类命中但输入包含跨类关键词）
    CROSS_TYPE_KEYWORDS = {
        "伪人": "悬疑/推理",
        "伪人入侵": "悬疑/推理",
        "身份替换": "悬疑/推理",
        "信任博弈": "悬疑/推理",
        "推理": "悬疑/推理",
        "规则类恐怖": "悬疑/推理",
        "怪谈": "轻小说/二次元",
        "规则怪谈": "轻小说/二次元",
        "言情": "言情",
        "恋爱": "言情",
        "种田": "末世/废土",
        "囤货": "末世/废土",
    }
    best_major = max(major_scores, key=major_scores.get) if major_scores else None
    if best_major and not cross_type_info:
        # 对每个 token 做精确匹配 AND 子串包含匹配
        for token in tokens:
            for cross_kw, inferred_secondary in CROSS_TYPE_KEYWORDS.items():
                if cross_kw in token or token in cross_kw:
                    if inferred_secondary != best_major and inferred_secondary in TAXONOMY:
                        cross_type_info = {
                            "primary": best_major,
                            "secondary": inferred_secondary,
                            "primary_score": major_scores.get(best_major, 0),
                            "secondary_score": 0,
                            "source": "keyword_inference",
                            "inferred_from": cross_kw,
                            "all_matches": dict(major_scores)
                        }
                        break
            if cross_type_info:
                break

    # 选择分数最高的大类
    best_major = max(major_scores, key=major_scores.get)
    major_data = TAXONOMY[best_major]

    # --- 小类/子类递归匹配 ---
    path, match_level = _find_best_match(major_data, tokens, level=1)

    # 仅大类匹配时修正 match_level 为 0（schema: 0=大类,1=小类,2=子类）
    if not path:
        match_level = 0

    # 纯大类名称查询（用户只输入大类名，不指定小类）不下钻
    major_parts = [p.strip() for p in best_major.split("/")]
    query_normalized = query.strip().replace(" ", "").replace("/", "")
    major_normalized = best_major.replace(" ", "").replace("/", "")
    if query_normalized == major_normalized or query.strip() in major_parts:
        match_level = 0
        path = []

    # --- 构建结果 ---
    weights = WEIGHT_MATRIX.get(best_major, {"结构": 3, "节奏": 3, "人物": 3, "金手指": 3, "开篇": 3, "雷区": 3})
    
    path_ids = [major_data["id"]]
    path_names = [best_major]

    extra_dims = []

    if path:
        for name, data in path:
            path_ids.append(data["id"])
            path_names.append(name)

        # extra_dims 从最深层节点收集
        extra_dims = _collect_all_extra_dims(path[-1][1])

        # 3级分类树最深层级为2（index），>=2即为子类级匹配
        if match_level >= 2:
            match_desc = f"子类级匹配（{'.'.join(path_names)}）"
        else:
            match_desc = f"小类级匹配（{'.'.join(path_names)}）"
    else:
        match_desc = f"大类级匹配（{best_major}）"

    # --- 素材文件引用 ---
    reference_files = REFERENCE_FILE_MAP.get(best_major, [])
    # 问题诊断文件对所有类型通用
    if "素材-问题诊断.md" not in reference_files:
        reference_files.append("素材-问题诊断.md")
    # 报告模板和分类体系始终加载
    reference_files.extend(["report-template.md", "genre-taxonomy.md"])

    # --- 节奏特征 ---
    rhythm_profile = RHYTHM_PROFILE_MAP.get(best_major, {"快慢": "中等", "密度": "中等", "张弛": "平衡", "紧缓": "交替"})

    # --- 开篇公式推荐 ---
    opening_hint = OPENING_FORMULA_HINT_MAP.get(best_major, {"推荐": ["A（冲突导入型）"], "避开": ["大段设定铺陈"]})

    # --- 意图诊断（intent_mapper）---
    intent_result = map_intent(query)
    intent_field = _build_intent_field(intent_result)

    # --- intent 权重重写：analysis_weight_shift 逐 key 覆盖大类默认 weights ---
    weight_shift = intent_field["analysis_weight_shift"]
    if weight_shift is not None:
        for k, v in weight_shift.items():
            if k in weights:
                weights[k] = v

    # --- 爽点侧重（基于最终权重推断） ---
    thrillpoint_focus = _infer_thrillpoint_focus(weights)

    # --- 写作模式（合规模式，与 multi-role Phase 3 对齐）---
    # 玄幻/末世/都市/游戏/历史/轻小说等网文主流类型默认 web 模式
    # 科幻、悬疑、言情有专属模式（更严格的禁止词和合规规则）
    writing_mode = TYPE_TO_WRITING_MODE.get(best_major, "web")

    return {
        "matched": True,
        "query": query,
        "major_category": best_major,
        "minor_category": path_names[1] if len(path_names) > 1 else None,
        "sub_category": path_names[2] if len(path_names) > 2 else None,
        "path_ids": path_ids,
        "path_names": path_names,
        "match_level": match_level,
        "weights": weights,
        "extra_dimensions": extra_dims,
        "analysis_focus_description": match_desc,
        "cross_type_info": cross_type_info,
        "writing_mode": writing_mode,
        "error": None,
        "reference_files": reference_files,
        "rhythm_profile": rhythm_profile,
        "opening_formula_hint": opening_hint,
        "formula": FORMULA_MAP.get(best_major, {}),
        "formula_by_wordcount": FORMULA_BY_WORDCOUNT.get(best_major, {}),
        "thrillpoint_focus": thrillpoint_focus,
        "intent": intent_field,
    }


# ============================================================
# CLI 入口
# ============================================================

def main():
    """CLI 入口：支持两种调用方式"""

    parser = argparse.ArgumentParser(
        description="网文类型路由引擎 — 根据用户输入匹配三级分类树，返回路由配置",
        epilog="示例:\n"
               "  python type_router.py '末世重生囤货'\n"
               "  python type_router.py '都市修仙'\n"
               "  echo '{\"query\": \"末世重生\"}' | python type_router.py\n\n"
               "输入: CLI查询词 或 stdin JSON {\"query\": \"...\"}\n"
               "输出: JSON stdout（路由配置: 路径+权重+维度+素材引用+写作模式）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("query", nargs="?", default=None,
                        help="类型查询词，如 '末世重生囤货'（也可通过 stdin 传入 JSON）")
    args = parser.parse_args()

    # --- 入口检测：优先级 CLI参数 > stdin JSON > 无输入（报错） ---
    query = None
    input_method = None

    if args.query:
        query = args.query
        input_method = "cli_arg"
    else:
        try:
            raw = sys.stdin.read().lstrip('\ufeff').strip()
            if raw:
                data = json.loads(raw)
                query = data.get("query", "")
                input_method = "stdin_json"
        except json.JSONDecodeError:
            input_method = "stdin_invalid_json"
        except EOFError:
            input_method = "stdin_no_input"

    # --- 输入清洗：去特殊字符、过短输入友好提示 ---
    if query:
        import re as _re
        query = query.strip()
        # 移除控制字符和零宽字符
        query = _re.sub(r'[\x00-\x1f\x7f\u200b-\u200f\u2028-\u202f\ufeff]', '', query)

    # --- 无有效输入 → 报错退出 ---
    if not query:
        error_response = {
            "error": True,
            "error_type": "未输入",
            "error_message": "请告诉我你想分析什么类型的小说，比如：'末世重生'、'都市修仙'、'悬疑推理'",
            "suggestion": "试试说：帮我拆一下都市修仙类",
            "usage": "python type_router.py '末世重生囤货'",
            "matched": False,
            "query": None
        }
        print(json.dumps(error_response, ensure_ascii=False, indent=2))
        sys.exit(1)

    # --- 输入过短 → 补充提示 ---
    if len(query) <= 1:
        error_response = {
            "error": True,
            "error_type": "输入太短",
            "error_message": f"你输入的「{query}」太短了，没法准确匹配类型",
            "suggestion": "请多说几个字，比如'末世重生'而不仅是'末'，这样匹配更准确",
            "matched": False,
            "query": query
        }
        print(json.dumps(error_response, ensure_ascii=False, indent=2))
        sys.exit(1)

    # --- 路由计算 ---
    try:
        result = route(query)
        print(json.dumps(result, ensure_ascii=False, indent=2))

        if result.get("error"):
            sys.exit(2)
        sys.exit(0)

    except UserFacingError as e:
        error_response = {
            "error": True,
            "error_type": "匹配失败",
            "error_message": friendly_message(e),
            "suggestion": "参考这些常见类型：末世、都市、玄幻、仙侠、悬疑、言情、科幻，或者换个更简单的关键词",
            "query": query,
            "matched": False
        }
        print(json.dumps(error_response, ensure_ascii=False, indent=2))
        sys.exit(3)
    except Exception as e:
        ScriptLogger.error(friendly_message(e))
        error_response = {
            "error": True,
            "error_type": "匹配失败",
            "error_message": friendly_message(e),
            "suggestion": "参考这些常见类型：末世、都市、玄幻、仙侠、悬疑、言情、科幻，或者换个更简单的关键词",
            "query": query,
            "matched": False
        }
        print(json.dumps(error_response, ensure_ascii=False, indent=2))
        sys.exit(3)


if __name__ == "__main__":
    main()