#!/usr/bin/env python3
"""
problem_matcher.py — 写作问题诊断匹配器

功能：解析用户描述的写作问题，匹配12类症状→根因→方案
职责：纯查表关键词匹配，不涉及AI判断
接口：CLI参数 → JSON stdout

用法：
  python problem_matcher.py "我开篇没人看怎么办"
  python problem_matcher.py "节奏太慢了"
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shared_utils  # noqa: F401


# ============================================================
# 12类写作问题映射表（与素材-问题诊断.md保持同步）
# ============================================================

PROBLEM_MAP = [
    {
        "id": 1, "title": "开篇没人看",
        "keywords": ["开篇没人看", "开头无聊", "前几章没吸引力", "读者不往下翻", "开头没人看", "开头太慢"],
        "root_causes": ["大段设定铺陈", "没有冲突/悬念", "主角没有目标", "节奏太慢", "千人一面"],
        "checklist": ["前300字有异常信号吗？", "前3章有冲突吗？", "主角有明确目标吗？"],
        "solutions": ["用冲突/重置型开篇重写第一章", "把设定后置到行动中带出", "添加开篇钩子"],
        "report_reference": "开篇钩子公式",
    },
    {
        "id": 2, "title": "节奏太慢",
        "keywords": ["节奏慢", "拖沓", "流水账", "读着没劲", "太平了", "节奏太慢", "拖沓冗长", "注水严重"],
        "root_causes": ["铺垫过长", "缺乏爽点", "信息密度不均", "时间流速失当"],
        "checklist": ["连续几章有无新事件？", "爽点间隔多少章？", "有无连续3章无冲突？"],
        "solutions": ["压缩铺垫段3:1原则", "每3-5章安排1个小爽点", "快慢交替节奏"],
        "report_reference": "爽点节奏图",
    },
    {
        "id": 3, "title": "角色不鲜活",
        "keywords": ["角色脸谱化", "不像真人", "配角工具人", "主角没特点", "人物扁平", "角色单薄"],
        "root_causes": ["缺少核心信念", "行为缺乏内在逻辑", "没有矛盾面", "全是功能型配角"],
        "checklist": ["能一句话说清角色核心信念吗？", "有'绝对不会做的事'吗？", "配角有独立动机吗？"],
        "solutions": ["用'思想→性格→命运'框架重设角色", "给主角加矛盾面", "让配角有自主性"],
        "report_reference": "人物原型库",
    },
    {
        "id": 4, "title": "金手指不合理",
        "keywords": ["金手指太强", "开后开太大", "没有代价", "开挂感太强", "金手指不合理", "过于逆天"],
        "root_causes": ["金手指无限制", "无成长感", "违背公平性", "与世界观不兼容"],
        "checklist": ["金手指有明确限制吗？", "使用有代价吗？", "升级路径清晰吗？"],
        "solutions": ["添加使用限制和代价", "设置升级条件", "让金手指与世界观规则绑定"],
        "report_reference": "金手指类型库",
    },
    {
        "id": 5, "title": "逻辑漏洞",
        "keywords": ["逻辑不自洽", "前后矛盾", "设定冲突", "蝴蝶效应滥用", "逻辑漏洞", "bug"],
        "root_causes": ["设定未通盘考虑", "遗忘前文伏笔", "金手指规则不一致"],
        "checklist": ["重新通读全文，标记每个设定规则", "检查是否有规则被后来打破"],
        "solutions": ["创建设定文档统一管理规则", "修复矛盾点", "必要时回铺前文伏笔"],
        "report_reference": "常见雷区",
    },
    {
        "id": 6, "title": "爽点不够爽",
        "keywords": ["爽点不爽", "高潮不起来", "打脸没感觉", "压抑后没释放", "不够爽"],
        "root_causes": ["铺垫不足", "爽点太短", "预期太容易猜到", "反差不够"],
        "checklist": ["爽点前有多少铺垫？", "爽点持续几段？", "读者能提前猜到吗？"],
        "solutions": ["加长铺垫+缩短爆发=更大反差", "设置出人意料的转折", "爽点后留回味"],
        "report_reference": "爽点节奏图",
    },
    {
        "id": 7, "title": "卡文写不动",
        "keywords": ["卡文", "写不下去", "不知道接下来写什么", "没有灵感", "写不动"],
        "root_causes": ["大纲缺失", "没有短期目标", "写了太多没规划", "走到死胡同"],
        "checklist": ["有完整大纲吗？", "下一章的核心事件是什么？", "主线方向清晰吗？"],
        "solutions": ["补充细纲（下5章的核心事件）", "回到大纲看方向", "用'如果...会怎样'引出新事件"],
        "report_reference": "结构模板",
    },
    {
        "id": 8, "title": "读者弃书",
        "keywords": ["弃书率高", "追读下降", "完本率低", "后面没人看", "弃书"],
        "root_causes": ["中段无聊", "承诺未兑现", "节奏单一", "持续压抑无释放"],
        "checklist": ["弃书集中发生在哪个位置？", "是否有长时间无爽点段？"],
        "solutions": ["在弃书高峰点添加转折", "确保每个Act有1-2个记忆点", "张弛交替"],
        "report_reference": "爽点节奏图",
    },
    {
        "id": 9, "title": "感情线突兀",
        "keywords": ["感情线生硬", "CP没有化学反应", "相爱太突然", "感情不自然", "感情线突兀"],
        "root_causes": ["缺少互动铺垫", "没有阻碍", "没有互补性", "纯功能型配对"],
        "checklist": ["CP有共同经历吗？", "有合理阻碍吗？", "性格是互补还是冲突？"],
        "solutions": ["添加共患难事件", "设置合理阻碍（身份/立场/误解）", "设计互补性互动"],
        "report_reference": "人物原型库",
    },
    {
        "id": 10, "title": "世界观混乱",
        "keywords": ["设定太多", "世界观讲不清", "读者看不懂", "设定打架", "世界观混乱"],
        "root_causes": ["一次性释放太多设定", "设定间互相矛盾", "没有体系化"],
        "checklist": ["第一章新设定超过3个吗？", "读者能一句话描述世界规则吗？"],
        "solutions": ["分批释放设定（用到才说）", "创建设定词典统一管理", "用事件展示规则"],
        "report_reference": "类型总览",
    },
    {
        "id": 11, "title": "结尾无力",
        "keywords": ["结尾太平", "结局草率", "读者不满意", "结尾无力", "虎头蛇尾"],
        "root_causes": ["高潮前铺垫不够", "核心冲突未彻底解决", "情感线未闭合"],
        "checklist": ["主角的目标达成了吗？", "核心冲突有明确胜负吗？", "各辅线有闭环吗？"],
        "solutions": ["在高潮前设置'最低点'增强反差", "确保核心冲突的终极对决", "闭合所有辅线"],
        "report_reference": "结构模板",
    },
    {
        "id": 12, "title": "同质化严重",
        "keywords": ["和别人写的差不多", "没有新意", "套路感太重", "千篇一律", "同质化", "套路"],
        "root_causes": ["盲目跟风", "没有创新点", "照搬模板", "缺乏个人特色"],
        "checklist": ["你的故事和同类作品的核心差异是什么？", "有同类没尝试过的元素吗？"],
        "solutions": ["在经典框架上加入1-2个创新变体", "交叉类型带来新鲜感", "找到独特视角"],
        "report_reference": "常见雷区",
    },
]


def match_problem(user_input: str) -> dict:
    """
    匹配用户描述到问题类型
    
    输入: user_input — 用户描述的写作问题
    输出: dict — 匹配结果（含前3个候选）
    """
    if not user_input or not user_input.strip():
        return {"error": True, "error_message": "请描述一下你遇到的写作问题，比如：'我开篇没人看怎么办'、'节奏太慢了'", "matches": []}
    
    text = user_input.strip()
    scores = []
    
    for problem in PROBLEM_MAP:
        score = 0
        matched_kws = []
        for kw in problem["keywords"]:
            if kw in text:
                score += len(kw)  # 更长关键词权重更高
                matched_kws.append(kw)
        if score > 0:
            scores.append((score, problem, matched_kws))
    
    # 模糊匹配：无论精确匹配是否命中，都补充模糊匹配以发现更优候选
    for problem in PROBLEM_MAP:
        # 跳过已有精确匹配的问题（避免重复加分）
        if any(s[1]["id"] == problem["id"] for s in scores):
            continue
        fuzzy_score = 0
        for kw in problem["keywords"]:
            # 有序子串匹配：检查关键词中的连续2字片段是否在文本中按序出现
            if len(kw) >= 2:
                segments = [kw[i:i+2] for i in range(len(kw)-1)]
                matched_segs = sum(1 for seg in segments if seg in text)
                if matched_segs >= len(segments) * 0.5 and matched_segs >= 1:
                    fuzzy_score += matched_segs
        if fuzzy_score > 0:
            scores.append((fuzzy_score * 0.5, problem, []))
    
    scores.sort(key=lambda x: -x[0])
    
    top_matches = []
    for score, problem, matched_kws in scores[:3]:
        top_matches.append({
            "problem_id": problem["id"],
            "title": problem["title"],
            "score": round(score, 1),
            "matched_keywords": matched_kws,
            "root_causes": problem["root_causes"],
            "checklist": problem["checklist"],
            "solutions": problem["solutions"],
            "report_reference": problem["report_reference"],
        })
    
    return {
        "matched": len(top_matches) > 0,
        "query": text,
        "match_count": len(top_matches),
        "matches": top_matches,
        "next_step": "Step -2: 按匹配到的第1个问题的checklist逐项排查" if top_matches else "引导用户描述更具体的症状",
    }


# ============================================================
# CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="写作问题诊断匹配器 — 解析写作问题，匹配12类症状→根因→方案",
        epilog="示例:\n"
               "  python problem_matcher.py '我开篇没人看怎么办'\n"
               "  python problem_matcher.py '节奏太慢了'\n"
               "  echo '{\"query\": \"金手指太强\"}' | python problem_matcher.py\n\n"
               "输入: CLI问题描述 或 stdin JSON {\"query\": \"...\", \"text\": \"...\"}\n"
               "输出: JSON stdout（匹配结果 + 前3候选 + 根因/方案/清单）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("query", nargs="*", default=[],
                        help="写作问题描述（也可通过 stdin 传入 JSON）")
    args = parser.parse_args()

    query = None

    if args.query:
        query = " ".join(args.query)
    else:
        try:
            raw = sys.stdin.read().lstrip('\ufeff').strip()
            if raw:
                try:
                    data = json.loads(raw)
                    query = data.get("query", data.get("text", raw))
                except json.JSONDecodeError:
                    query = raw
        except EOFError:
            pass
    
    if not query:
        error = {
            "error": True,
            "error_type": "未输入",
            "error_message": "请描述你遇到的写作问题，比如：'我开篇没人看怎么办'",
            "suggestion": "你能具体说说哪里卡住了吗？比如'节奏太慢'、'人物写崩了'、'金手指太逆天'",
        }
        print(json.dumps(error, ensure_ascii=False, indent=2))
        sys.exit(1)
    
    result = match_problem(query)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
