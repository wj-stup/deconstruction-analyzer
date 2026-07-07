#!/usr/bin/env python3
"""
character_template.py — 人物原型模板查表器

功能：根据网文类型，输出主角原型建议、配角配置建议和人设模板
职责：纯查表逻辑，与素材-人物设定.md保持同步
接口：CLI参数 → JSON stdout

用法：
  python character_template.py "末世重生"
  python character_template.py "玄幻" --role protagonist
"""

import json
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from shared_utils import _fuzzy_match_type


# ============================================================
# 主角原型库（与素材-人物设定.md保持同步）
# ============================================================

PROTAGONIST_ARCHETYPES = {
    "玄幻": [
        {
            "type": "草根逆袭型", "core_belief": "我不信命",
            "personality": "隐忍、坚韧、不服输",
            "cheat_match": "系统/面板/灵根觉醒", "arc": "弱→强→碾压",
        },
        {
            "type": "大能重生型", "core_belief": "这次不会再错",
            "personality": "老练、腹黑、目标明确",
            "cheat_match": "前世记忆/重修经验", "arc": "强→弱→更强",
        },
        {
            "type": "天才型", "core_belief": "我要证明自己",
            "personality": "倔强、孤傲、追求极致",
            "cheat_match": "天赋/特殊体质", "arc": "强→更强→突破极限",
        },
        {
            "type": "穿越者型", "core_belief": "用知识改变世界",
            "personality": "理性、创新、不合常规",
            "cheat_match": "现代知识/科技思维", "arc": "陌生→适应→碾压",
        },
    ],
    "修仙/修真": [
        {
            "type": "凡人修仙型", "core_belief": "大道可期",
            "personality": "沉稳、谨慎、步步为营",
            "cheat_match": "奇遇传承/功法", "arc": "微末→积累→证道",
        },
        {
            "type": "重修型", "core_belief": "重来必胜",
            "personality": "老辣、果断、知己知彼",
            "cheat_match": "前世经验/遗留法宝", "arc": "强者归来→碾压→飞升",
        },
    ],
    "都市": [
        {
            "type": "重生型", "core_belief": "这次选对路",
            "personality": "老成、利用信息差、精明",
            "cheat_match": "记忆/先知", "arc": "落魄→重来→成功",
        },
        {
            "type": "异能型", "core_belief": "用能力改变生活",
            "personality": "隐藏、双面生活",
            "cheat_match": "异能/修仙", "arc": "普通→觉醒→双面人生",
        },
        {
            "type": "神豪型", "core_belief": "花钱也是本事",
            "personality": "果断、享受、有时张扬",
            "cheat_match": "系统/遗产", "arc": "贫穷→暴富→领悟",
        },
    ],
    "末世/废土": [
        {
            "type": "囤货型", "core_belief": "有备无患",
            "personality": "谨慎、细致、未雨绸缪",
            "cheat_match": "空间/重生记忆", "arc": "筹备→安全→扩建",
        },
        {
            "type": "复仇型", "core_belief": "欠我的要还",
            "personality": "狠辣、果断、目标导向",
            "cheat_match": "重生记忆/特殊能力", "arc": "被害→重生→清算",
        },
        {
            "type": "救世型", "core_belief": "不能看着大家死",
            "personality": "正义、担当、有时天真",
            "cheat_match": "基地/庇护所/特殊能力", "arc": "救人→建势力→拯救",
        },
    ],
    "悬疑/推理": [
        {
            "type": "侦探型", "core_belief": "真相只有一个",
            "personality": "敏锐、执着、理性至上",
            "cheat_match": "观察力/推理能力/特殊感知", "arc": "接案→深入→揭露真相",
        },
        {
            "type": "受害者型", "core_belief": "我必须查清楚",
            "personality": "执念驱动、不择手段、内心创伤",
            "cheat_match": "线索/隐秘知识/复仇动力", "arc": "受害→追查→救赎或毁灭",
        },
        {
            "type": "嫌疑人型", "core_belief": "没人能证明是我做的",
            "personality": "冷静、伪装大师、控制欲强",
            "cheat_match": "不在场证明/心理操纵/完美犯罪", "arc": "嫌疑→博弈→反转",
        },
    ],
    "无限流/生存游戏": [
        {
            "type": "热血领袖型（郑吒原型）", "core_belief": "我要带所有人活着回去",
            "personality": "热血、正义感强、行动派、道德挣扎中成长",
            "cheat_match": "基因锁定强化/战斗本能进化", "arc": "普通人→团队领袖→超越者",
        },
        {
            "type": "绝对理性型（楚轩原型）", "core_belief": "数据不骗人。最优解只有一个",
            "personality": "极致智商、表面无情（或隐藏极深）、算计一切",
            "cheat_match": "天才大脑/预判能力/信息整合", "arc": "谜之新人→团队大脑→超越逻辑的存在",
        },
        {
            "type": "冷酷专精型（零点原型）", "core_belief": "目标清除。完毕",
            "personality": "寡言、专业、效率至上、偶露温柔",
            "cheat_match": "武器专精/狙击/刺客技能树", "arc": "孤狼→团队最锋利的刃→为信念牺牲",
        },
        {
            "type": "规则适应型", "core_belief": "规则就是用来利用的",
            "personality": "投机、灵活、善于发现漏洞、风险偏好高",
            "cheat_match": "规则解析/漏洞利用/系统外挂", "arc": "新人→规则玩家→制定规则者",
        },
        {
            "type": "智囊辅助型（詹岚原型）", "core_belief": "信息就是力量",
            "personality": "观察敏锐、沟通协调能力强、女性视角/细腻",
            "cheat_match": "分析能力/情报网络/辅助技能", "arc": "普通成员→团队情报中心→不可或缺",
        },
    ],
}

# 配角模板（通用）
SUPPORTING_TEMPLATES = {
    "引路人": {"function": "推动剧情、提供信息", "design_note": "必须有自己的动机", "common_mistake": "只当工具人无自主性"},
    "竞争对手": {"function": "制造冲突、衬托主角", "design_note": "实力相近有来有回", "common_mistake": "单纯的恶人无深度"},
    "情感锚点": {"function": "让读者关心", "design_note": "有独立的成长空间", "common_mistake": "纯花瓶无主动性"},
    "搞笑担当": {"function": "调节气氛", "design_note": "不抢主线节奏", "common_mistake": "喧宾夺主"},
    "背叛者": {"function": "制造转折", "design_note": "要有合理的背叛原因", "common_mistake": "无铺垫的突然背叛"},
    "导师": {"function": "指引成长", "design_note": "适时退出舞台", "common_mistake": "一直帮主角解决一切"},
}

# 配角数量建议
SUPPORTING_COUNT = {
    "short": {"range": "3-5", "word_count": "5万字以内"},
    "mid": {"range": "5-8", "word_count": "5-20万字"},
    "long": {"range": "8-15", "word_count": "20万字+"},
}

# 人设模板字段
CHARACTER_SHEET_FIELDS = [
    {"field": "角色名", "description": "姓名/外号"},
    {"field": "身份/职业", "description": "社会身份"},
    {"field": "核心思想", "description": "一句话描述最深层的信念/恐惧"},
    {"field": "性格关键词", "description": "3个关键词"},
    {"field": "外在特征", "description": "外貌/习惯/口癖"},
    {"field": "内在矛盾", "description": "最核心的内心冲突"},
    {"field": "关系网", "description": "与谁有什么样的关系"},
    {"field": "角色功能", "description": "在故事中承担什么功能"},
    {"field": "成长弧线", "description": "从哪里开始，到哪里结束"},
    {"field": "绝不开口/做的事", "description": "角色的底线"},
    {"field": "一句话速写", "description": "用一句话让读者记住这个角色"},
]

# 三项评估指标
EVALUATION_METRICS = [
    {"metric": "合理", "meaning": "人物行为是否符合其设定的性格和动机", "method": "行为是否有内在逻辑，是否自洽"},
    {"metric": "有特点", "meaning": "是否有区别于同类角色的独特之处", "method": "一句话能否描述这个角色的核心特征"},
    {"metric": "有代入感", "meaning": "读者是否能够理解和共情", "method": "读者的困境/欲望是否能投射到角色上"},
]


def lookup_character(type_name: str, role: str = None, resolved_type: str = None) -> dict:
    """
    查询指定类型的人物原型模板

    resolved_type: 上游 type_router 已解析的类型名，提供时跳过模糊匹配直接使用
    """
    # 类型匹配
    if resolved_type:
        matched_key = resolved_type
        archetypes = PROTAGONIST_ARCHETYPES.get(resolved_type)
        type_name = resolved_type
    else:
        matched_key, archetypes = _fuzzy_match_type(type_name, PROTAGONIST_ARCHETYPES)
        if matched_key:
            type_name = matched_key
    if not archetypes:
        # 回退到玄幻
        archetypes = PROTAGONIST_ARCHETYPES["玄幻"]
    
    result = {
        "matched": matched_key is not None,
        "type_name": type_name,
    }
    
    if role == "protagonist" or role is None:
        result["protagonist_archetypes"] = archetypes
    
    if role == "supporting" or role is None:
        result["supporting_templates"] = SUPPORTING_TEMPLATES
        result["supporting_count_advice"] = SUPPORTING_COUNT
    
    result["character_sheet_fields"] = CHARACTER_SHEET_FIELDS
    result["evaluation_metrics"] = EVALUATION_METRICS
    
    return result


# ============================================================
# CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="人物原型模板查表器 — 根据网文类型输出主角原型建议、配角配置和人设模板",
        epilog="示例:\n"
               "  python character_template.py '末世重生'\n"
               "  python character_template.py '玄幻' --role protagonist\n"
               "  echo '{\"type\": \"都市\"}' | python character_template.py\n\n"
               "输入: CLI类型名称 或 stdin JSON {\"type\": \"...\", \"major_category\": \"...\"}\n"
               "输出: JSON stdout（原型/模板/评估指标）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("type", nargs="?", default=None, help="网文类型名称")
    parser.add_argument("--role", "-r", default=None, choices=["protagonist", "supporting"],
                        help="角色类型：protagonist=主角, supporting=配角")
    parser.add_argument("--resolved-type", default=None,
                        help="上游已解析的类型名（如'末世/废土'），提供时跳过模糊匹配直接查表")
    args = parser.parse_args()

    type_name = args.type
    resolved_type = args.resolved_type
    if not type_name:
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
    
    result = lookup_character(type_name or resolved_type, args.role, resolved_type=resolved_type)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
