#!/usr/bin/env python3
"""
outline_generator.py — 大纲模板生成器

功能：根据网文类型和目标字数，生成三幕结构大纲模板
职责：纯查表+模板拼接，不涉及AI判断
接口：CLI参数 → JSON stdout

用法：
  python outline_generator.py "末世重生" --words 20000
  python outline_generator.py "玄幻" --words 50000
"""

import json
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from shared_utils import _fuzzy_match_type


# ============================================================
# 大纲结构模板（与素材-大纲教程.md保持同步）
# ============================================================

OUTLINE_TEMPLATES = {
    "玄幻": {
        "act1": {
            "name": "起步期", "ratio": "20-25%",
            "主线": "废柴/普通开局 → 金手指/天赋觉醒 → 初入修炼世界",
            "辅线": "结识伙伴 + 发现身世暗示",
        },
        "act2": {
            "name": "磨砺期", "ratio": "50-55%",
            "主线": "宗门/势力试炼 → 小有名气 → 遭遇重大挫折",
            "辅线": "感情萌芽 + 与竞争者对立",
        },
        "act3": {
            "name": "爆发期", "ratio": "20-25%",
            "主线": "触底反弹 → 真相揭示 → 大决战 → 飞升/登顶",
            "辅线": "感情确定 + 竞争者结局",
        },
    },
    "修仙/修真": {
        "act1": {
            "name": "起步期", "ratio": "20-25%",
            "主线": "入门修炼 → 获得功法/传承 → 初窥大道",
            "辅线": "师门关系 + 秘境发现",
        },
        "act2": {
            "name": "磨砺期", "ratio": "50-55%",
            "主线": "境界突破 → 宗门大比 → 遭遇瓶颈/天劫",
            "辅线": "道侣 + 宗门危机",
        },
        "act3": {
            "name": "飞升期", "ratio": "20-25%",
            "主线": "悟道突破 → 天劫渡关 → 飞升仙界",
            "辅线": "恩怨了结 + 大道圆满",
        },
    },
    "都市": {
        "act1": {
            "name": "转折点", "ratio": "20-25%",
            "主线": "获得金手指/重生 → 第一步行动",
            "辅线": "人际关系的建立",
        },
        "act2": {
            "name": "上升期", "ratio": "50-55%",
            "主线": "事业/地位上升 → 遇到瓶颈或对手",
            "辅线": "感情发展 + 对手竞争",
        },
        "act3": {
            "name": "峰值期", "ratio": "20-25%",
            "主线": "突破瓶颈 → 解决核心问题 → 成功",
            "辅线": "感情结果",
        },
    },
    "末世/废土": {
        "act1": {
            "name": "囤货期", "ratio": "15-20%",
            "主线": "重生 → 利用信息差囤货 → 末世降临",
            "辅线": "前世恩怨的线索",
        },
        "act2": {
            "name": "生存期", "ratio": "55-60%",
            "主线": "末世生存 → 基地建设 → 抵御威胁",
            "辅线": "团队组建 + 蝴蝶效应",
        },
        "act3": {
            "name": "反击期", "ratio": "20-25%",
            "主线": "反击/清算 → 真相 → 重建",
            "辅线": "复仇线闭环",
        },
    },
    "科幻": {
        "act1": {
            "name": "发现期", "ratio": "20-25%",
            "主线": "异常事件 → 发现秘密 → 卷入漩涡",
            "辅线": "团队组建 + 个人动机",
        },
        "act2": {
            "name": "探索期", "ratio": "50-55%",
            "主线": "深入探索 → 技术突破 → 遭遇危机",
            "辅线": "信任危机 + 真相碎片",
        },
        "act3": {
            "name": "决战期", "ratio": "20-25%",
            "主线": "终极对决 → 真相揭示 → 新秩序",
            "辅线": "牺牲/选择 + 未来展望",
        },
    },
    "悬疑/推理": {
        "act1": {
            "name": "入局期", "ratio": "20-25%",
            "主线": "案件发生 → 线索初现 → 主角介入",
            "辅线": "嫌疑人登场 + 红鲱鱼",
        },
        "act2": {
            "name": "调查期", "ratio": "50-55%",
            "主线": "深入调查 → 伪解答 → 真正的线索浮现",
            "辅线": "个人危险 + 信任动摇",
        },
        "act3": {
            "name": "揭秘期", "ratio": "20-25%",
            "主线": "推理揭秘 → 真相对决 → 正义伸张",
            "辅线": "动机剖析 + 主题升华",
        },
    },
    "游戏": {
        "act1": {
            "name": "新手期", "ratio": "20-25%",
            "主线": "进入游戏/获得系统 → 选择职业 → 新手任务",
            "辅线": "组队 + 发现隐藏任务",
        },
        "act2": {
            "name": "成长期", "ratio": "50-55%",
            "主线": "升级打怪 → 竞技对战 → 遭遇强敌",
            "辅线": "公会 + 感情线",
        },
        "act3": {
            "name": "巅峰期", "ratio": "20-25%",
            "主线": "终极挑战 → 获得冠军/通关 → 登顶",
            "辅线": "队友告别 + 新起点",
        },
    },
    "历史/架空历史": {
        "act1": {
            "name": "入世期", "ratio": "20-25%",
            "主线": "穿越/重生古代 → 利用知识初显身手",
            "辅线": "结识关键人物 + 文化冲突",
        },
        "act2": {
            "name": "经营期", "ratio": "50-55%",
            "主线": "势力发展 → 遭遇强敌/政治阴谋",
            "辅线": "感情发展 + 蝴蝶效应",
        },
        "act3": {
            "name": "霸业期", "ratio": "20-25%",
            "主线": "决战 → 建立新秩序 → 王朝/传承",
            "辅线": "历史闭环",
        },
    },
    "言情": {
        "act1": {
            "name": "相遇期", "ratio": "20-25%",
            "主线": "CP相遇 → 第一印象 → 初步互动",
            "辅线": "各自背景 + 外部压力",
        },
        "act2": {
            "name": "纠葛期", "ratio": "50-55%",
            "主线": "感情升温 → 误会/阻碍 → 分离/冲突",
            "辅线": "第三者 + 家庭/社会压力",
        },
        "act3": {
            "name": "团圆期", "ratio": "20-25%",
            "主线": "障碍消除 → 真情告白 → 在一起",
            "辅线": "配角线闭环",
        },
    },
    "轻小说/二次元": {
        "act1": {
            "name": "引入期", "ratio": "20-25%",
            "主线": "日常开局 → 异常介入 → 主角卷入",
            "辅线": "日常互动 + 搞笑桥段",
        },
        "act2": {
            "name": "展开期", "ratio": "50-55%",
            "主线": "事件升级 → 各种展开 → 高潮前蓄力",
            "辅线": "角色关系 + 日常调剂",
        },
        "act3": {
            "name": "高潮期", "ratio": "20-25%",
            "主线": "大事件 → 解决 → 回归日常（升级版）",
            "辅线": "角色成长 + 新日常",
        },
    },
    "无限流/生存游戏": {
        "act1": {
            "name": "新手副本期", "ratio": "20-25%",
            "主线": "被拉入规则世界 → 首次觉醒/选择 → 第一个副本（生死试炼）",
            "辅线": "初次组队 + 规则探索",
        },
        "act2": {
            "name": "副本深化期", "ratio": "50-55%",
            "主线": "难度阶梯上升 → 团队磨合与分裂 → 发现隐藏规则/主神秘密",
            "辅线": "个人强化路线 + 信任危机 + 重大牺牲",
        },
        "act3": {
            "name": "终局副本期", "ratio": "20-25%",
            "主线": "最终副本（最高难度） → 主神空间真相揭露 → 打破规则/超越/新循环",
            "辅线": "终极牺牲或救赎 + 结局选择",
        },
    },
}

# 字数→章节分配映射
WORD_COUNT_MAP = {
    "2万字": {"chapters": "10-15章", "words_per_chapter": "1500-2000字", "thrillpoint_interval": "每2-3章"},
    "5万字": {"chapters": "25-35章", "words_per_chapter": "1500-2000字", "thrillpoint_interval": "每3-5章"},
    "10万字": {"chapters": "50-70章", "words_per_chapter": "1500-2000字", "thrillpoint_interval": "每5-8章"},
    "20万字": {"chapters": "100-130章", "words_per_chapter": "1500-2000字", "thrillpoint_interval": "每5-8章"},
    "50万字+": {"chapters": "长篇连载", "words_per_chapter": "2000-3000字", "thrillpoint_interval": "每8-12章"},
}

# 辅线类型
SUBPLOT_TYPES = {
    "感情线": {"功能": "丰富角色维度", "占比建议": "15-25%", "引入时机": "Act 1 后半"},
    "竞争线": {"功能": "制造对手压力", "占比建议": "10-20%", "引入时机": "Act 1 末尾"},
    "解谜线": {"功能": "维持好奇心", "占比建议": "10-15%", "引入时机": "贯穿全文"},
    "成长线": {"功能": "展示角色内在变化", "占比建议": "10-15%", "引入时机": "与主线交织"},
    "副副本线": {"功能": "调节节奏", "占比建议": "5-10%", "引入时机": "张弛之间的缓冲"},
}


def _resolve_word_band(word_count: int) -> str:
    """根据字数确定所属区间"""
    if word_count <= 30000:
        return "2万字"
    elif word_count <= 70000:
        return "5万字"
    elif word_count <= 150000:
        return "10万字"
    elif word_count <= 300000:
        return "20万字"
    else:
        return "50万字+"


def generate_outline(type_name: str, word_count: int = 20000, resolved_type: str = None) -> dict:
    """
    生成大纲模板

    resolved_type: 上游 type_router 已解析的类型名，提供时跳过模糊匹配直接使用
    """
    # 类型匹配
    if resolved_type:
        matched_key = resolved_type
        template = OUTLINE_TEMPLATES.get(resolved_type)
        type_name = resolved_type
    else:
        matched_key, template = _fuzzy_match_type(type_name, OUTLINE_TEMPLATES)
    if matched_key:
        type_name = matched_key
    if not template:
        template = OUTLINE_TEMPLATES["玄幻"]  # 默认使用玄幻模板
    
    word_band = _resolve_word_band(word_count)
    word_config = WORD_COUNT_MAP.get(word_band, WORD_COUNT_MAP["2万字"])
    
    # 估算各Act字数
    act1_words = int(word_count * 0.225)
    act2_words = int(word_count * 0.525)
    act3_words = int(word_count * 0.25)
    
    outline = {
        "matched": matched_key is not None,
        "type_name": type_name,
        "target_word_count": word_count,
        "word_band": word_band,
        "chapter_config": word_config,
        "act1": {
            "name": template["act1"]["name"],
            "ratio": template["act1"]["ratio"],
            "estimated_words": act1_words,
            "main_plot": template["act1"]["主线"],
            "subplot": template["act1"]["辅线"],
        },
        "act2": {
            "name": template["act2"]["name"],
            "ratio": template["act2"]["ratio"],
            "estimated_words": act2_words,
            "main_plot": template["act2"]["主线"],
            "subplot": template["act2"]["辅线"],
        },
        "act3": {
            "name": template["act3"]["name"],
            "ratio": template["act3"]["ratio"],
            "estimated_words": act3_words,
            "main_plot": template["act3"]["主线"],
            "subplot": template["act3"]["辅线"],
        },
        "subplot_types": SUBPLOT_TYPES,
    }
    
    return outline


# ============================================================
# CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="大纲模板生成器 — 根据网文类型和目标字数生成三幕结构大纲模板",
        epilog="示例:\n"
               "  python outline_generator.py '末世重生' --words 20000\n"
               "  python outline_generator.py '玄幻' -w 50000\n"
               "  echo '{\"type\": \"都市\", \"word_count\": 30000}' | python outline_generator.py\n\n"
               "输入: CLI类型名称+字数 或 stdin JSON {\"type\": \"...\", \"word_count\": N}\n"
               "输出: JSON stdout（三幕结构 + 章节/字数分配 + 辅线类型）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("type", nargs="?", default=None, help="网文类型名称")
    parser.add_argument("--words", "-w", type=int, default=20000, help="目标字数（默认20000）")
    parser.add_argument("--resolved-type", "-r", default=None,
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
                    if "word_count" in data:
                        args.words = int(data["word_count"])
                except json.JSONDecodeError:
                    type_name = raw
        except EOFError:
            pass

    if not type_name and not resolved_type:
        error = {
            "error": True,
            "error_type": "未输入",
            "error_message": "请提供小说类型名称和目标字数，例如：'末世重生'、2万字",
        }
        print(json.dumps(error, ensure_ascii=False, indent=2))
        sys.exit(1)
    
    result = generate_outline(type_name or resolved_type, args.words, resolved_type=resolved_type)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
