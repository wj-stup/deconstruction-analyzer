#!/usr/bin/env python3
"""
opening_formula.py — 开篇公式查表器

功能：根据网文类型，查询推荐的开篇公式、避坑项和自检清单
职责：纯查表逻辑，与素材-开篇技法.md保持同步
接口：CLI参数 → JSON stdout

用法：
  python opening_formula.py "末世重生"
  python opening_formula.py "玄幻"
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from shared_utils import _fuzzy_match_type


# ============================================================
# 开篇公式库（与素材-开篇技法.md保持同步）
# ============================================================

OPENING_FORMULAS = {
    "A": {
        "id": "A",
        "name": "冲突导入型",
        "structure": "平静 → 异常信号 → 冲突爆发 → 主角反应",
        "rhythm": "3句铺垫 + 1句打破 + 2句升级 + 1句悬念结尾",
        "applicable_types": ["玄幻", "都市", "末世", "历史"],
        "example_scene": "日常环境 + 反常事件",
    },
    "B": {
        "id": "B",
        "name": "身份重置型",
        "structure": "迷茫 → 信息差（我知道别人不知道的）→ 决策点 → 行动",
        "rhythm": "1句场景 + 2句内心 + 3句信息差展示 + 1句行动决心",
        "applicable_types": ["末世重生", "穿越", "重生修仙", "都市重生"],
        "example_scene": "主角'醒来'",
    },
    "C": {
        "id": "C",
        "name": "金手指展示型",
        "structure": "触发事件 → 能力展示 → 规则暗示 → 后果预告",
        "rhythm": "1句触发 + 2句能力描述 + 2句规则限制 + 1句暗示风险",
        "applicable_types": ["系统流", "异能", "游戏", "都市"],
        "example_scene": "系统/面板/异能触发",
    },
    "D": {
        "id": "D",
        "name": "悬念型",
        "structure": "抛出谜题 → 线索碎片 → 读者猜测 → 主角介入",
        "rhythm": "1句悬念 + 2句异常 + 2句未知 + 1句行动驱动",
        "applicable_types": ["悬疑", "推理", "科幻"],
        "example_scene": "一封神秘来信、一桩离奇事件",
    },
    "E": {
        "id": "E",
        "name": "日常打破型",
        "structure": "平静日常 → 微小异常 → 异常升级 → 日常被彻底打破",
        "rhythm": "2句日常 + 1句微异常 + 2句异常升级 + 1句打破",
        "applicable_types": ["都市", "科幻", "言情"],
        "example_scene": "普通一天突然出现异常",
    },
}

# 类型 → 推荐公式 + 避开公式
TYPE_FORMULA_MAP = {
    "玄幻":          {"推荐": ["A", "B"], "避开": ["C"], "避开原因": "金手指太早会压缩悬念空间"},
    "修仙/修真":     {"推荐": ["B", "A"], "避开": [], "避开原因": "避免大段设定铺陈"},
    "都市":          {"推荐": ["A", "C"], "避开": [], "避开原因": "避免玄幻式长篇设定"},
    "末世/废土":     {"推荐": ["B"], "避开": [], "避开原因": "避免日常太长后再切入"},
    "科幻":          {"推荐": ["E", "D"], "避开": [], "避开原因": "避免科普式叙事"},
    "悬疑/推理":     {"推荐": ["D"], "避开": [], "避开原因": "避免大段背景交代"},
    "游戏":          {"推荐": ["C", "A"], "避开": [], "避开原因": "避免慢热日常"},
    "历史/架空历史": {"推荐": ["B", "A"], "避开": [], "避开原因": "避免大段历史科普"},
    "言情":          {"推荐": ["A", "E"], "避开": [], "避开原因": "避免大段心理描写"},
    "轻小说/二次元": {"推荐": ["A", "C"], "避开": [], "避开原因": "避免沉重开头"},
    "无限流/生存游戏": {"推荐": ["D", "B"], "避开": ["E"], "避开原因": "慢热日常与无限流高压节奏冲突，需在开篇即建立生存压力"},
}

# 黄金300字法则（固定内容）
GOLDEN_300_RULES = [
    "前50字：必须出现画面感（场景/动作/感官）",
    "前100字：读者必须知道主角是谁",
    "前200字：必须出现异常（与日常不同的信号）",
    "前300字：必须给出'为什么要继续读'的理由（悬念/冲突/反差）",
]

# 自检清单（固定内容）
SELF_CHECK_LIST = [
    "前3句话是否出现了冲突/悬念/反差？",
    "第300字内是否交代了'与众不同'？",
    "第800字内是否有第一个小冲突？",
    "第一章结尾是否有悬念/钩子？",
    "开篇是否有'可记忆点'？",
    "对标作品中最高赞的开篇用了什么手法？",
    "主角是否有明确的短期目标？",
    "前3章是否建立了至少1个读者关心的问题？",
    "信息释放节奏是否渐进（非一次性倾倒）？",
    "开篇是否与该类型的读者预期匹配？",
]

# 易犯错误12条
COMMON_MISTAKES = [
    "大段世界观铺陈 — 开篇就写设定集，读者直接流失",
    "主角无目标 — 没有明确的行动方向",
    "慢热过度 — 超过3章还没有任何冲突或悬念",
    "信息过载 — 前3章引入太多角色和组织",
    "被动主角 — 主角只是被动接受事件",
    "平淡日常 — 开篇写了一堆日常但没有任何异常信号",
    "频繁切换视角 — 开篇就在多个角色之间跳转",
    "过度内心独白 — 大段主角的心理活动",
    "预告式叙事 — 展示而非预告",
    "开篇就虐 — 没有建立情感联结就安排惨烈桥段",
    "缺乏钩子 — 每章结尾平滑过渡",
    "千人一面 — 开篇套路与其他作品雷同",
]


def lookup_opening(type_name: str, resolved_type: str = None) -> dict:
    """
    查询指定类型的开篇公式推荐

    输入: type_name — 大类名称
    resolved_type: 上游 type_router 已解析的类型名，提供时跳过模糊匹配
    输出: dict — 开篇公式推荐结果
    """
    # 模糊匹配
    if resolved_type:
        matched_key = resolved_type
        formula_config = TYPE_FORMULA_MAP.get(resolved_type)
        is_matched = True
        type_name = resolved_type
    else:
        matched_key, formula_config = _fuzzy_match_type(type_name, TYPE_FORMULA_MAP)
        is_matched = matched_key is not None
        if matched_key:
            type_name = matched_key
    if not formula_config:
        formula_config = {"推荐": ["A"], "避开": [], "避开原因": "未匹配到具体类型，使用默认推荐"}
        is_matched = False if resolved_type else is_matched

    # 构建推荐公式详情
    recommended = []
    for fid in formula_config["推荐"]:
        if fid in OPENING_FORMULAS:
            f = OPENING_FORMULAS[fid]
            recommended.append({
                "id": f["id"],
                "name": f["name"],
                "structure": f["structure"],
                "rhythm": f["rhythm"],
                "applicable_types": f["applicable_types"],
                "example_scene": f["example_scene"],
            })
    
    # 构建避开公式详情
    avoided = []
    for fid in formula_config["避开"]:
        if fid in OPENING_FORMULAS:
            f = OPENING_FORMULAS[fid]
            avoided.append({"id": f["id"], "name": f["name"]})
    
    return {
        "matched": is_matched,
        "type_name": type_name,
        "recommended_formulas": recommended,
        "avoided_formulas": avoided,
        "avoid_reason": formula_config.get("避开原因", ""),
        "golden_300_rules": GOLDEN_300_RULES,
        "self_check_list": SELF_CHECK_LIST,
        "common_mistakes": COMMON_MISTAKES,
    }


# ============================================================
# CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="开篇公式查表器 — 根据网文类型查询推荐开篇公式、避坑项和自检清单",
        epilog="示例:\n"
               "  python opening_formula.py '末世重生'\n"
               "  python opening_formula.py '玄幻'\n"
               "  echo '{\"type\": \"都市\"}' | python opening_formula.py\n\n"
               "输入: CLI类型名称 或 stdin JSON {\"type\": \"...\", \"major_category\": \"...\"}\n"
               "输出: JSON stdout（推荐公式 + 避坑 + 黄金300字 + 自检清单）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("type", nargs="?", default=None,
                        help="网文类型名称（也可通过 stdin 传入 JSON）")
    parser.add_argument("--resolved-type", "-r", default=None,
                        help="上游已解析的类型名（如'末世/废土'），提供时跳过模糊匹配直接查表")
    args = parser.parse_args()

    type_name = None
    resolved_type = args.resolved_type

    if args.type:
        type_name = args.type
    else:
        try:
            raw = sys.stdin.read().lstrip('\ufeff').strip()
            if raw:
                try:
                    data = json.loads(raw)
                    type_name = data.get("type", data.get("major_category", ""))
                    resolved_type = resolved_type or data.get("resolved_major_category") or data.get("major_category")
                except json.JSONDecodeError:
                    type_name = raw
        except EOFError:
            pass

    if not type_name and not resolved_type:
        error = {
            "error": True,
            "error_type": "未输入",
            "error_message": "请提供小说类型名称，例如：'末世重生'、'玄幻'",
        }
        print(json.dumps(error, ensure_ascii=False, indent=2))
        sys.exit(1)
    
    result = lookup_opening(type_name or resolved_type, resolved_type=resolved_type)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
