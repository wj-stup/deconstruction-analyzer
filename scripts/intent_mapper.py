#!/usr/bin/env python3
"""
intent_mapper.py — 用户意图→分析策略映射器

功能：解析用户输入的意图关键词，映射到拆书分析策略
职责：纯查表逻辑，不涉及AI判断
状态：已合并入 type_router.py，仅作为内部模块被导入，不可独立调用
"""

import json


# ============================================================
# 意图→策略映射表
# ============================================================

INTENT_MAP = {
    "market": {
        "id": "A",
        "label": "市场行情",
        "icon": "📊",
        "keywords": ["市场", "行情", "热度", "趋势", "竞品", "商业", "赚钱", "变现", "数据", "排行榜", "榜单"],
        "step3_focus": "类型总览+竞品扫描",
        "step5_focus": "章节一+章节七",
        "extra_output": "热度对比表",
        "analysis_weight_shift": {"结构": 2, "节奏": 2, "人物": 2, "金手指": 2, "开篇": 2, "雷区": 4},
    },
    "structure": {
        "id": "B",
        "label": "结构模板",
        "icon": "🏗️",
        "keywords": ["结构", "模板", "框架", "蓝图", "章节", "布局", "大纲", "三幕", "黄金三章"],
        "step3_focus": "全篇结构+章节分布",
        "step5_focus": "章节二+章节三",
        "extra_output": "可复用的结构框架",
        "analysis_weight_shift": {"结构": 5, "节奏": 4, "人物": 2, "金手指": 2, "开篇": 3, "雷区": 2},
    },
    "opening": {
        "id": "C",
        "label": "开篇写法",
        "icon": "🎣",
        "keywords": ["开篇", "开头", "前三章", "钩子", "开头怎么写", "黄金三章", "开篇钩子", "前几章"],
        "step3_focus": "前3章逐句分析",
        "step5_focus": "章节五",
        "extra_output": "开篇对照表",
        "analysis_weight_shift": {"结构": 3, "节奏": 3, "人物": 2, "金手指": 2, "开篇": 5, "雷区": 3},
    },
    "cheat": {
        "id": "D",
        "label": "金手指",
        "icon": "💎",
        "keywords": ["金手指", "系统", "异能", "能力", "外挂", "设定", "特殊能力"],
        "step3_focus": "金手指类型+升级路径",
        "step5_focus": "章节六",
        "extra_output": "金手指卡牌模板",
        "analysis_weight_shift": {"结构": 2, "节奏": 2, "人物": 3, "金手指": 5, "开篇": 2, "雷区": 3},
    },
    "pitfall": {
        "id": "E",
        "label": "避坑",
        "icon": "⚠️",
        "keywords": ["避坑", "雷区", "错误", "踩坑", "差评", "读者不喜欢", "负面", "翻车"],
        "step3_focus": "读者差评+逻辑漏洞",
        "step5_focus": "章节七",
        "extra_output": "避坑清单",
        "analysis_weight_shift": {"结构": 2, "节奏": 3, "人物": 2, "金手指": 2, "开篇": 2, "雷区": 5},
    },
    "full": {
        "id": "F",
        "label": "全面分析",
        "icon": "🔬",
        "keywords": ["全面", "完整", "详细", "深入", "全部", "整体", "综合",
                      "写小说", "创作", "写书", "写文"],
        # 类型关键词单独存放，权重=1（防止"玄幻避坑"→full误分类）
        "genre_keywords": [
            "悬疑", "推理", "惊悚", "玄幻", "修仙", "仙侠", "都市", "末世",
            "科幻", "言情", "历史", "游戏", "轻小说", "短篇", "中篇", "长篇",
            "武侠", "恐怖", "奇幻", "校园", "军事", "现实", "同人", "网文",
            "末日", "废土", "种马", "种田", "囤货", "重生", "变异", "天灾",
            "后宫", "基建", "求生", "异能", "空间", "系统流",
        ],
        # 额外的意图信号词（"小说""写作""拆书""分析"）
        "intent_keywords": ["小说", "写作", "拆书", "分析"],
        "step3_focus": "所有6维度",
        "step5_focus": "标准9章节",
        "extra_output": "完整报告",
        "analysis_weight_shift": None,  # 使用默认权重
    },
}


def map_intent(user_input: str) -> dict:
    """
    将用户输入映射到分析策略
    
    输入: user_input — 用户输入的文本
    输出: dict — 意图分析结果 + 策略配置
    """
    if not user_input or not user_input.strip():
        return _default_result("未提供输入")
    
    text = user_input.strip()
    scores = {}
    matched_keywords = {}
    
    for intent_id, intent_data in INTENT_MAP.items():
        score = 0
        matched = []
        for kw in intent_data["keywords"]:
            if kw in text:
                score += len(kw)  # 更长关键词权重更高（与problem_matcher一致）
                matched.append(kw)
        # genre_keywords 以权重=1计分（防止类型词压倒具体意图词）
        for kw in intent_data.get("genre_keywords", []):
            if kw in text:
                score += 1
                matched.append(kw)
        # intent_keywords 以权重=1计分（补充信号但不主导）
        for kw in intent_data.get("intent_keywords", []):
            if kw in text:
                score += 1
                matched.append(kw)
        if score > 0:
            scores[intent_id] = score
            matched_keywords[intent_id] = matched
    
    if not scores:
        return _default_result(f"未识别到明确意图：{text}")
    
    # 选择得分最高的意图（平分时优先选"全面分析"，否则选关键词最长匹配）
    best_id = max(scores, key=scores.get)
    best = INTENT_MAP[best_id]
    
    # 如果有并列最高分，优先选"全面分析"（仅当full有核心信号词时）
    best_score = scores[best_id]
    _full_signals = set(INTENT_MAP["full"]["keywords"])  # 仅核心信号词（全面/完整/...）
    if "full" in scores and scores["full"] == best_score:
        if any(sig in text for sig in _full_signals):
            best_id = "full"
            best = INTENT_MAP["full"]
    elif best_score == scores.get(best_id):
        # 其他并列情况：选关键词匹配更长（更精确）的意图
        max_kw_len = max((len(kw) for kws in matched_keywords.get(best_id, []) for kw in kws), default=0)
        for iid, iscore in scores.items():
            if iscore == best_score and iid != best_id:
                kw_len = max((len(kw) for kws in matched_keywords.get(iid, []) for kw in kws), default=0)
                if kw_len > max_kw_len:
                    best_id = iid
                    best = INTENT_MAP[best_id]
                    max_kw_len = kw_len
    
    return {
        "matched": True,
        "query": text,
        "intent_id": best_id,
        "intent_label": best["label"],
        "intent_icon": best["icon"],
        "matched_keywords": matched_keywords.get(best_id, []),
        "all_candidates": {k: {"label": INTENT_MAP[k]["label"], "score": v} for k, v in scores.items()},
        "strategy": {
            "step3_focus": best["step3_focus"],
            "step5_focus": best["step5_focus"],
            "extra_output": best["extra_output"],
            "analysis_weight_shift": best["analysis_weight_shift"],
        },
    }


def _default_result(reason: str) -> dict:
    """默认结果（未匹配时使用全面分析）"""
    full = INTENT_MAP["full"]
    return {
        "matched": False,
        "query": reason,
        "intent_id": "full",
        "intent_label": full["label"],
        "intent_icon": full["icon"],
        "matched_keywords": [],
        "all_candidates": {},
        "strategy": {
            "step3_focus": full["step3_focus"],
            "step5_focus": full["step5_focus"],
            "extra_output": full["extra_output"],
            "analysis_weight_shift": full["analysis_weight_shift"],
        },
    }

