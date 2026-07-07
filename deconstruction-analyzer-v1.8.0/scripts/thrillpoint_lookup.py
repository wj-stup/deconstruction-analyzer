#!/usr/bin/env python3
"""
thrillpoint_lookup.py — 爽点库查表器

功能：根据网文类型，查询该类型侧重的爽点类别和具体爽点
职责：纯查表逻辑，与素材-爽点库.md保持同步
接口：CLI参数 → JSON stdout

用法：
  python thrillpoint_lookup.py "末世重生"
  python thrillpoint_lookup.py "玄幻" --category "逆袭类"
  python thrillpoint_lookup.py --list-categories
"""

import json
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from shared_utils import _fuzzy_match_type


# ============================================================
# 爽点库数据（与素材-爽点库.md保持同步）
# ============================================================

THRILLPOINT_CATEGORIES = {
    "逆袭类": {
        "id": 1, "count": 15,
        "items": [
            "废柴逆袭", "扮猪吃虎", "越级挑战", "身份反转", "绝地翻盘",
            "学渣变学霸", "穷人暴富", "弱者觉醒", "众人皆错我独对", "冷门变热门",
            "弃子回归", "以一敌百", "小人物立大功", "翻旧账", "不被看好却成功",
        ],
    },
    "打脸类": {
        "id": 2, "count": 10,
        "items": [
            "当面打脸", "实力碾压", "让子弹飞", "证据翻出", "前辈认错",
            "集体震惊", "排名逆袭", "打赌获胜", "专业碾压", "预言应验",
        ],
    },
    "收获类": {
        "id": 3, "count": 10,
        "items": [
            "天降横财", "稀有掉落", "奇遇传承", "贵人相助", "意外收获",
            "捡漏成功", "彩票中奖", "系统奖励", "宝物认主", "机缘巧合",
        ],
    },
    "升级类": {
        "id": 4, "count": 10,
        "items": [
            "突破瓶颈", "连升多级", "觉醒血脉", "功法大成", "新技能解锁",
            "转职进化", "领悟真理", "体质蜕变", "境界碾压", "开枝散叶",
        ],
    },
    "装逼类": {
        "id": 5, "count": 10,
        "items": [
            "装完再打", "淡然处之", "一招制敌", "随手为之", "背对爆炸",
            "大佬待遇", "言出法随", "秒杀全场", "云淡风轻", "众人跪拜",
        ],
    },
    "揭秘类": {
        "id": 6, "count": 10,
        "items": [
            "身份揭露", "真相大白", "幕后揭示", "隐藏实力", "逆转认知",
            "前世记忆", "系统真相", "血脉觉醒", "阴谋破灭", "天机揭露",
        ],
    },
    "情感类": {
        "id": 7, "count": 10,
        "items": [
            "久别重逢", "真情告白", "承诺兑现", "守护成功", "冰释前嫌",
            "被理解", "认可致敬", "救命恩人", "破镜重圆", "誓言兑现",
        ],
    },
    "情节类": {
        "id": 8, "count": 5,
        "items": [
            "以弱胜强", "绝处逢生", "大局逆转", "完美复仇", "终战告捷",
        ],
    },
}

# 类型 → 侧重爽点类别（基于素材-爽点库.md的使用说明第3条）
TYPE_THRILLPOINT_FOCUS = {
    "玄幻":        {"primary": ["升级类", "逆袭类", "装逼类"], "secondary": ["收获类", "打脸类"]},
    "修仙/修真":   {"primary": ["升级类", "逆袭类", "收获类"], "secondary": ["装逼类", "揭秘类"]},
    "都市":        {"primary": ["打脸类", "逆袭类", "装逼类"], "secondary": ["收获类", "情感类"]},
    "末世/废土":   {"primary": ["收获类", "逆袭类", "升级类"], "secondary": ["打脸类", "揭秘类"]},
    "科幻":        {"primary": ["揭秘类", "升级类", "逆袭类"], "secondary": ["收获类", "情节类"]},
    "悬疑/推理":   {"primary": ["揭秘类", "情节类", "逆袭类"], "secondary": ["打脸类"]},
    "游戏":        {"primary": ["升级类", "收获类", "打脸类"], "secondary": ["装逼类", "逆袭类"]},
    "历史/架空历史": {"primary": ["逆袭类", "打脸类", "装逼类"], "secondary": ["收获类", "升级类"]},
    "言情":        {"primary": ["情感类", "逆袭类", "揭秘类"], "secondary": ["打脸类", "收获类"]},
    "轻小说/二次元": {"primary": ["装逼类", "逆袭类", "揭秘类"], "secondary": ["收获类", "升级类"]},
    "无限流/生存游戏": {"primary": ["升级类", "逆袭类", "情节类"], "secondary": ["收获类", "揭秘类", "打脸类"]},
    # 无限流核心爽感：基因锁解锁（升级）、绝地翻盘（逆袭）、以弱胜强（情节）、副本奖励（收获）
}

# 爽点密度建议
DENSITY_ADVICE = {
    "2万字": {"章节": "10-15章", "小爽点间隔": "每2-3章", "大爽点间隔": "每5-8章"},
    "5万字": {"章节": "25-35章", "小爽点间隔": "每3-5章", "大爽点间隔": "每8-12章"},
    "10万字": {"章节": "50-70章", "小爽点间隔": "每3-5章", "大爽点间隔": "每10-15章"},
    "20万字": {"章节": "100-130章", "小爽点间隔": "每5-8章", "大爽点间隔": "每15-20章"},
}

# 爽点使用原则
USAGE_PRINCIPLES = [
    "密度控制：每3-5章安排一个小爽点，每10-15章安排一个大爽点",
    "类型交替：不要连续使用同一类型的爽点，避免审美疲劳",
    "与类型匹配：末世文侧重'收获类'、玄幻文侧重'升级类'、都市文侧重'打脸类'",
    "铺垫很重要：爽点效果取决于铺垫质量，3分铺垫7分回报",
    "创新空间：在经典爽点基础上加入该类型的创新变体，增加新鲜感",
]


def lookup_thrillpoints(type_name: str, category: str = None, resolved_type: str = None) -> dict:
    """
    查询指定类型的爽点推荐

    resolved_type: 上游 type_router 已解析的类型名，提供时跳过模糊匹配直接使用
    """
    # 类型匹配
    if resolved_type:
        # 上游已解析，直接使用，跳过模糊匹配
        matched_key = resolved_type
        focus = TYPE_THRILLPOINT_FOCUS.get(resolved_type)
        type_name = resolved_type
    else:
        matched_key, focus = _fuzzy_match_type(type_name, TYPE_THRILLPOINT_FOCUS)
        if matched_key:
            type_name = matched_key
    if not focus:
        focus = {"primary": ["逆袭类", "打脸类", "升级类"], "secondary": ["收获类", "装逼类"]}
    
    result = {
        "matched": matched_key is not None,
        "type_name": type_name,
        "primary_categories": focus["primary"],
        "secondary_categories": focus["secondary"],
    }
    
    # 如果指定了类别，输出该类别的具体爽点
    if category:
        cat_data = THRILLPOINT_CATEGORIES.get(category)
        if cat_data:
            result["selected_category"] = category
            result["items"] = cat_data["items"]
        else:
            result["selected_category"] = None
            result["error"] = f"未找到类别「{category}」，可选的类别有：逆袭类、打脸类、收获类、升级类、装逼类、揭秘类、情感类、情节类"
    else:
        # 输出侧重类别的具体爽点
        primary_items = {}
        for cat in focus["primary"]:
            if cat in THRILLPOINT_CATEGORIES:
                primary_items[cat] = THRILLPOINT_CATEGORIES[cat]["items"]
        result["primary_items"] = primary_items
        
        secondary_items = {}
        for cat in focus["secondary"]:
            if cat in THRILLPOINT_CATEGORIES:
                secondary_items[cat] = THRILLPOINT_CATEGORIES[cat]["items"]
        result["secondary_items"] = secondary_items
    
    result["density_advice"] = DENSITY_ADVICE
    result["usage_principles"] = USAGE_PRINCIPLES
    
    return result


# ============================================================
# CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="爽点库查表器 — 根据网文类型查询侧重爽点类别和具体爽点",
        epilog="示例:\n"
               "  python thrillpoint_lookup.py '末世重生'\n"
               "  python thrillpoint_lookup.py '玄幻' --category '逆袭类'\n"
               "  python thrillpoint_lookup.py --list-categories\n"
               "  echo '{\"type\": \"都市\"}' | python thrillpoint_lookup.py\n\n"
               "输入: CLI类型名称 或 stdin JSON {\"type\": \"...\", \"major_category\": \"...\"}\n"
               "输出: JSON stdout（爽点类别 + 具体条目 + 密度建议 + 使用原则）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("type", nargs="?", default=None, help="网文类型名称")
    parser.add_argument("--category", "-c", default=None, help="爽点类别（如'逆袭类'）")
    parser.add_argument("--list-categories", action="store_true", help="列出所有爽点类别")
    parser.add_argument("--resolved-type", "-r", default=None,
                        help="上游已解析的类型名（如'末世/废土'），提供时跳过模糊匹配直接查表")
    args = parser.parse_args()

    if args.list_categories:
        cats = {}
        for name, data in THRILLPOINT_CATEGORIES.items():
            cats[name] = {"count": data["count"], "items": data["items"]}
        print(json.dumps({"categories": cats}, ensure_ascii=False, indent=2))
        sys.exit(0)
    
    type_name = args.type
    resolved_type = args.resolved_type
    if not type_name:
        try:
            raw = sys.stdin.read().lstrip('\ufeff').strip()
            if raw:
                try:
                    data = json.loads(raw)
                    type_name = data.get("type", data.get("major_category", ""))
                    # 优先使用上游解析后的类型名
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
    
    result = lookup_thrillpoints(type_name or resolved_type, args.category, resolved_type=resolved_type)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
