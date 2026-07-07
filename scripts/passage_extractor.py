#!/usr/bin/env python3
"""
passage_extractor.py — 范文段落提取与分析脚本

功能：从对标作品中提取关键段落，标注其技法特点和分析价值
职责：提供 AI 在拆书分析中引用的"原始段落+技法标注"素材
接口：CLI 参数 / JSON stdin → JSON stdout

用法：
  cat chapter_text.txt | python scripts/passage_extractor.py --mode opening
  python scripts/passage_extractor.py "原文段落" --mode climax
  python scripts/passage_extractor.py "搜索片段/简介/书评" --mode infer
"""

import json
import sys
import re
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shared_utils  # noqa: F401

def _strip_frontmatter(text: str) -> str:
    """移除 Markdown frontmatter（--- 包围的 YAML 头部）和文件头部元数据块"""
    # 情况1: 标准 YAML frontmatter（--- ... --- 在开头）
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            return text[end + 3:].lstrip("\n")
    # 情况2: 元数据标题+分隔线（#标题 / >引用 / --- 分隔线在前面）
    lines = text.split("\n")
    cut = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        # 跳过标题行、引用行、空行
        if stripped.startswith("#") or stripped.startswith(">") or stripped == "":
            cut = i + 1
            continue
        # 遇到 --- 分隔线，跳过它并截断
        if stripped == "---":
            cut = i + 1
            break
        # 遇到非元数据内容，停止
        break
    if cut > 0:
        return "\n".join(lines[cut:]).lstrip("\n")
    return text


# ============================================================
# 分析函数
# ============================================================

def analyze_opening(text: str) -> dict:
    """分析开篇段落的结构特征"""
    result = {
        "type": "opening",
        "hook_type": None,
        "word_count": len(text),
        "technique_notes": [],
        "extracted_excerpt": text[:300] if len(text) > 300 else text,
    }

    # 钩子类型识别（优先级从高到低：越具体的模式越先匹配）
    if re.search(r"死|杀|仇|血|恨", text[:200]):
        result["hook_type"] = "冲突型钩子"
        result["technique_notes"].append("前200字内出现暴力/冲突关键词，制造紧迫感")
    elif re.search(r"系统|面板|提示|叮|恭喜", text[:200]):
        result["hook_type"] = "金手指型钩子"
        result["technique_notes"].append("金手指提前展示，给读者明确的成长预期")
    elif re.search(r"规则|副本|任务|轮回|倒计时|存活|主神|游戏|选择.*YES|选择.*NO", text[:200]):
        result["hook_type"] = "规则导入型钩子"
        result["technique_notes"].append("开篇导入规则/副本机制/生存游戏框架，给予读者明确的挑战预期和选择张力（无限流/生存游戏典型开篇）")
    elif re.search(r"梦|醒|睁眼|穿越|重生", text[:200]):
        result["hook_type"] = "身份重置型钩子"
        result["technique_notes"].append("主角身份重置（重生/穿越），天然制造信息差悬念")
    elif re.search(r"[？?][！!]|[惊疑奇]", text[:100]):
        result["hook_type"] = "悬念型钩子"
        result["technique_notes"].append("开篇制造悬念，驱动读者继续阅读寻找答案")
    else:
        result["hook_type"] = "日常切入型"
        result["technique_notes"].append("以日常场景切入，逐渐引入异常，适合慢热型故事")

    # 节奏评估（覆盖中英文标点和省略号）
    sentences = re.split(r'[。！？\n；…！?]', text[:500])
    avg_sentence_len = sum(len(s) for s in sentences if s) / max(len([s for s in sentences if s]), 1)
    if avg_sentence_len < 20:
        result["technique_notes"].append(f"短句为主（均长{avg_sentence_len:.0f}字），节奏快")
    elif avg_sentence_len < 40:
        result["technique_notes"].append(f"中短句混用（均长{avg_sentence_len:.0f}字），节奏适中")
    else:
        result["technique_notes"].append(f"长句为主（均长{avg_sentence_len:.0f}字），节奏舒缓")

    return result


def analyze_climax(text: str) -> dict:
    """分析高潮段落的技法"""
    result = {
        "type": "climax",
        "climax_type": None,
        "word_count": len(text),
        "technique_notes": [],
        "extracted_excerpt": text[:300] if len(text) > 300 else text,
    }

    if re.search(r"打|战|杀|斗|战意|剑气|出手|轰", text):
        result["climax_type"] = "战斗型高潮"
        result["technique_notes"].append("通过动作描写+感官冲击制造高潮")
    elif re.search(r"身份|竟然|原来|真相|揭晓|暴露", text):
        result["climax_type"] = "揭秘型高潮"
        result["technique_notes"].append("通过信息释放（身份/真相）制造情绪峰值")
    elif re.search(r"获得|突破|升级|恭喜|奖励|新能力", text):
        result["climax_type"] = "收获型高潮"
        result["technique_notes"].append("通过角色成长/获得新能力带来爽感")
    elif re.search(r"哭|泪|抱|拥|从未|永远|誓言", text):
        result["climax_type"] = "情感型高潮"
        result["technique_notes"].append("通过情感爆发（重逢/告白/牺牲）打动读者")

    # 高潮前置节奏分析
    if re.search(r"就在[这那]|突然|猛然|一瞬间|毫无征兆", text[:200]):
        result["technique_notes"].append("高潮前有节奏突变标记词")

    return result


def analyze_extract(text: str, mode: str = "auto") -> dict:
    """主分析函数"""
    if not text or not text.strip():
        return {"error": True, "error_message": "请提供要分析的文本段落，至少需要20个字"}

    # --- 文本过短 → 友好提示 ---
    if len(text.strip()) < 20:
        return {
            "error": True,
            "error_message": f"文本只有{len(text.strip())}个字，太短了没法分析",
            "suggestion": "至少需要20个字才能分析技法特征，建议贴出一段完整段落（比如开篇前300字）"
        }

    if mode == "opening":
        return analyze_opening(text)
    elif mode == "climax":
        return analyze_climax(text)
    elif mode == "reveal":
        return analyze_reveal(text)
    elif mode == "infer":
        return analyze_infer(text)
    else:
        # auto-detect
        if len(text) < 1000:
            # 短文本 → 开篇分析
            return analyze_opening(text)
        else:
            return analyze_climax(text)


def analyze_infer(text: str) -> dict:
    """技法推断模式：接受搜索片段/摘要/书评等非完整原文，输出推断性技法分析
    
    当无法获取完整正文时（平台封锁/仅搜索片段），使用此模式从二手素材中
    推断技法特征。所有结论标注推断置信度。
    """
    result = {
        "type": "infer",
        "word_count": len(text),
        "technique_notes": [],
        "extracted_excerpt": text[:500] if len(text) > 500 else text,
        "inference_mode": True,
        "confidence": "medium",
    }

    # 推断开篇类型
    if re.search(r"重生|醒来|回到|睁眼|惊醒", text[:300]):
        result["technique_notes"].append("推断：身份重置型开篇（重生/穿越）")
        result["confidence"] = "high"
    elif re.search(r"系统|面板|提示|空间", text[:300]):
        result["technique_notes"].append("推断：金手指展示型开篇")
        result["confidence"] = "high"
    elif re.search(r"怪谈|论坛|求救|诡异|恐怖", text[:300]):
        result["technique_notes"].append("推断：悬念/日常打破型开篇（怪谈导入）")
    elif re.search(r"冲突|被杀|背叛|追杀", text[:300]):
        result["technique_notes"].append("推断：冲突导入型开篇")
    else:
        result["technique_notes"].append("推断：开篇类型无法从片段确定")
        result["confidence"] = "low"

    # 推断核心设定/金手指
    if re.search(r"空间|异能|系统|面板|金手指", text):
        result["technique_notes"].append("推断：含空间/系统类金手指")
    if re.search(r"伪人|异种|替换|仿生|非人", text):
        result["technique_notes"].append("推断：含信任博弈/身份识别元素")

    # 推断爽点类型
    if re.search(r"囤|物资|采购|仓库|采购|百万|千亿", text):
        result["technique_notes"].append("推断：囤货收获类爽点为主")
    if re.search(r"复仇|清算|渣男|背叛|黑化", text):
        result["technique_notes"].append("推断：含逆袭/复仇爽点线")
    if re.search(r"升级|进化|强化|突破", text):
        result["technique_notes"].append("推断：含升级类爽点线")

    # 推断节奏
    sentences = re.split(r'[。！？\n；…！?]', text[:500])
    valid_sents = [s for s in sentences if s]
    if valid_sents:
        avg_len = sum(len(s) for s in valid_sents) / len(valid_sents)
        if avg_len < 20:
            result["technique_notes"].append(f"推断：快节奏叙事（句均{avg_len:.0f}字）")
        elif avg_len < 40:
            result["technique_notes"].append(f"推断：中等节奏叙事（句均{avg_len:.0f}字）")
        else:
            result["technique_notes"].append(f"推断：舒缓叙事（句均{avg_len:.0f}字）")

    # 素材来源标注
    if re.search(r"书评|评论|读者|评分", text[:200]):
        result["technique_notes"].append("素材来源：读者评论/书评（非原文）")
        result["confidence"] = "low"
    elif re.search(r"简介|作品简介|内容简介", text[:200]):
        result["technique_notes"].append("素材来源：作品简介（非原文正文）")
    elif re.search(r"章节|正文|第.{1,3}章", text[:200]):
        result["technique_notes"].append("素材来源：含原文片段")
        result["confidence"] = "high"
    else:
        result["technique_notes"].append("素材来源：不确定")

    return result


def analyze_reveal(text: str) -> dict:
    """分析揭秘段落的技法"""
    result = {
        "type": "reveal",
        "reveal_type": None,
        "word_count": len(text),
        "technique_notes": [],
        "extracted_excerpt": text[:300] if len(text) > 300 else text,
    }

    if re.search(r"原来[^\n]*?[是他她它]", text):
        result["reveal_type"] = "身份揭秘"
        result["technique_notes"].append('通过原来是他句式制造恍然大悟感')
    elif re.search(r"真相|阴谋|算计|布局|幕后", text):
        result["reveal_type"] = "阴谋揭秘"
        result["technique_notes"].append("揭示背后有更大势力/布局，为后续剧情埋线")
    elif re.search(r"系统|传承|血脉|天赋|隐藏", text):
        result["reveal_type"] = "能力揭秘"
        result["technique_notes"].append("揭示主角隐藏能力/血脉，提供新的成长方向")

    # 揭秘公平性检查
    if re.search(r"前文|之前|上文|早已|早就", text):
        result["technique_notes"].append("✅ 有前文铺垫，揭秘有据可循（公平性较好）")
    else:
        result["technique_notes"].append("⚠️ 无前文铺垫标记，需检查是否属于'机械降神'")

    return result


# ============================================================
# CLI 入口
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="范文段落提取与分析 — 从对标作品中提取关键段落，标注技法特点和分析价值",
        epilog="示例:\n"
               "  python passage_extractor.py '原文段落' --mode opening\n"
               "  python passage_extractor.py '高潮段落' -m climax\n"
               "  cat chapter_text.txt | python passage_extractor.py --mode opening\n\n"
               "输入: CLI文本 或 stdin 原文\n"
               "输出: JSON stdout（钩子/高潮类型 + 技法标注 + 摘录）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("text", nargs="?", default=None,
                        help="要分析的文本段落（也可通过 stdin 传入）")
    parser.add_argument("--mode", "-m", default="auto",
                        choices=["auto", "opening", "climax", "reveal", "infer"],
                        help="分析模式：auto=自动, opening=开篇, climax=高潮, reveal=揭秘, infer=技法推断")

    args = parser.parse_args()

    # 读取文本：优先 args.text，其次 stdin
    text = args.text
    if not text:
        try:
            raw = sys.stdin.read().lstrip('\ufeff').strip()
            if raw:
                try:
                    data = json.loads(raw)
                    text = data.get("text", raw)
                except json.JSONDecodeError:
                    text = raw
        except EOFError:
            pass

    # 过滤 Markdown frontmatter（text 可能为 None）
    if text:
        text = _strip_frontmatter(text)

    if not text:
        result = {
            "error": True,
            "error_message": "请提供要分析的文本段落，至少20个字",
            "suggestion": "使用方式：把原文贴给AI，或者说'帮我分析这段开篇：...'",
            "usage": "cat chapter.txt | python passage_extractor.py --mode opening"
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1)

    result = analyze_extract(text, mode=args.mode)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
