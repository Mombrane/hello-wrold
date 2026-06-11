#!/usr/bin/env python3
"""Generate 8 MemPalace diagrams - NO emoji, high resolution, clean design."""

import math
from PIL import Image, ImageDraw, ImageFont
import os

OUT = os.path.expanduser("~/.hermes/repos/hello-wrold/reports/assets/mempalace/")
os.makedirs(OUT, exist_ok=True)

# Scale factor for 2x resolution
S = 2

# Colors
WHITE = (255, 255, 255)
BG = (248, 249, 252)
NAVY = (20, 20, 40)
DARK = (40, 44, 60)
BLUE = (55, 100, 180)
LIGHT_BLUE = (230, 235, 255)
ACCENT = (70, 130, 210)
GREEN = (50, 150, 90)
ORANGE = (210, 130, 30)
RED = (190, 60, 60)
GRAY = (130, 135, 150)
LIGHT_GRAY = (240, 242, 248)
CARD_BORDER = (190, 195, 215)

# Fonts - find CJK font
def _find_font(bold=False):
    import glob
    if bold:
        candidates = glob.glob("/usr/share/fonts/**/NotoSansCJK*Bold*", recursive=True)
    else:
        candidates = glob.glob("/usr/share/fonts/**/NotoSansCJK*Regular*", recursive=True)
        if not candidates:
            candidates = glob.glob("/usr/share/fonts/**/NotoSansCJK*", recursive=True)
    for c in candidates:
        if c.endswith(('.ttf', '.ttc', '.otf')):
            return c
    return None

_font_path_bold = _find_font(bold=True)
_font_path_regular = _find_font(bold=False)

def font(size, bold=False):
    path = _font_path_bold if bold else _font_path_regular
    if path:
        return ImageFont.truetype(path, size * S)
    return ImageFont.load_default()

TITLE = font(32, bold=True)
H2 = font(24, bold=True)
BODY = font(18)
SMALL = font(14)
TINY = font(12)
LABEL = font(16, bold=True)


def canvas(w=1800, h=1000):
    img = Image.new("RGB", (w * S, h * S), BG)
    draw = ImageDraw.Draw(img)
    return img, draw, w * S, h * S


def rrect(draw, xy, r=12, fill=WHITE, outline=CARD_BORDER, width=2):
    draw.rounded_rectangle([v * S for v in xy], radius=r * S, fill=fill, outline=outline, width=width * S)


def arrow(draw, x0, y0, x1, y1, color=GRAY, w=2, head=10):
    sx0, sy0, sx1, sy1 = x0*S, y0*S, x1*S, y1*S
    draw.line([(sx0, sy0), (sx1, sy1)], fill=color, width=w*S)
    angle = math.atan2(sy1 - sy0, sx1 - sx0)
    for da in [-0.4, 0.4]:
        ax = sx1 - head*S * math.cos(angle + da)
        ay = sy1 - head*S * math.sin(angle + da)
        draw.polygon([(sx1, sy1), (int(ax), int(ay))], fill=color)


def center(draw, text, y, f, fill=NAVY, x=900):
    bbox = draw.textbbox((0, 0), text, font=f)
    tw = bbox[2] - bbox[0]
    draw.text(((x * S - tw // 2), y * S), text, font=f, fill=fill)


def badge(draw, x, y, text, color=ACCENT):
    bbox = draw.textbbox((0, 0), text, font=TINY)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pad = 6 * S
    rrect(draw, (x, y, x + tw//S + 12, y + th//S + 12), r=6, fill=color, outline=color)
    draw.text((x*S + pad, y*S + pad), text, font=TINY, fill=WHITE)


def box(draw, x, y, w, h, text, f=BODY, fill=WHITE, tc=NAVY, border=ACCENT, sub=None):
    rrect(draw, (x, y, x+w, y+h), r=10, fill=fill, outline=border)
    bbox = draw.textbbox((0, 0), text, font=f)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    cx = x + w // 2
    if sub:
        draw.text((cx*S - tw//2, (y + h//2 - th//S - 4)*S), text, font=f, fill=tc)
        bbox2 = draw.textbbox((0, 0), sub, font=SMALL)
        tw2 = bbox2[2] - bbox2[0]
        draw.text((cx*S - tw2//2, (y + h//2 + 4)*S), sub, font=SMALL, fill=GRAY)
    else:
        draw.text((cx*S - tw//2, (y + h//2 - th//(2*S))*S), text, font=f, fill=tc)


def down_arrow(draw, x, y0, y1, color=GRAY, w=2):
    arrow(draw, x, y0, x, y1, color, w)


def right_arrow(draw, x0, y, x1, color=GRAY, w=2):
    arrow(draw, x0, y, x1, y, color, w)


# ============================================================
# 1. Palace Architecture
# ============================================================
def gen_palace():
    img, draw, W, H = canvas(1800, 1100)
    center(draw, "MemPalace 宫殿架构", 30, TITLE, NAVY)
    center(draw, "灵感来自记忆宫殿法 + Zettelkasten 卡片盒笔记法", 80, BODY, GRAY)

    # Palace outer
    rrect(draw, (100, 120, 1700, 1050), r=20, fill=(245, 247, 255), outline=BLUE, width=3)
    badge(draw, 120, 130, "PALACE", BLUE)

    wings = [
        ("Wing: Alice", ["auth-migration", "api-design", "debugging"]),
        ("Wing: Project-X", ["frontend", "backend", "deploy"]),
    ]
    for i, (wing, rooms) in enumerate(wings):
        wx = 160 + i * 760
        rrect(draw, (wx, 200, wx+700, 980), r=16, fill=(240, 243, 255), outline=ACCENT)
        badge(draw, wx+10, 210, wing, ACCENT)

        for j, room in enumerate(rooms):
            ry = 280 + j * 230
            rrect(draw, (wx+30, ry, wx+670, ry+200), r=12, fill=WHITE, outline=CARD_BORDER)
            badge(draw, wx+45, ry+8, f"Room: {room}", GREEN)

            halls = [["facts", "events", "preferences"], ["discoveries", "advice", "habits"]][i % 2]
            for k, hall in enumerate(halls[:3]):
                hx = wx + 55 + k * 200
                rrect(draw, (hx, ry+55, hx+180, ry+95), r=8, fill=LIGHT_BLUE, outline=BLUE, width=1)
                center(draw, hall, ry+63, TINY, DARK, hx+90)

            # Closets
            rrect(draw, (wx+55, ry+110, wx+310, ry+150), r=8, fill=(255, 248, 230), outline=ORANGE, width=1)
            center(draw, "Closet (AAAK)", ry+118, TINY, DARK, wx+182)

            # Drawers
            for dk in range(3):
                dx = wx + 330 + dk * 110
                rrect(draw, (dx, ry+110, dx+100, ry+150), r=6, fill=(230, 255, 235), outline=GREEN, width=1)
                center(draw, f"D{dk+1}", ry+118, TINY, DARK, dx+50)

    # Legend
    items = [("Wing", "人物/项目"), ("Room", "主题/时间"), ("Hall", "概念分类"), ("Closet", "压缩索引"), ("Drawer", "原文逐字")]
    colors = [ACCENT, GREEN, BLUE, ORANGE, GREEN]
    for i, ((name, desc), c) in enumerate(zip(items, colors)):
        lx = 200 + i * 300
        draw.rectangle([(lx*S, 1060*S), ((lx+15)*S, (1060+15)*S)], fill=c)
        draw.text(((lx+25)*S, 1060*S), f"{name} = {desc}", font=BODY, fill=DARK)

    img.save(os.path.join(OUT, "palace-architecture.png"))
    print("  palace-architecture.png")


# ============================================================
# 2. Mining Pipeline
# ============================================================
def gen_mining():
    img, draw, W, H = canvas(1800, 800)
    center(draw, "记忆写入管道", 25, TITLE, NAVY)

    steps = [
        ("Step 1", "输入格式", "JSONL / JSON / TXT\nSlack / Gemini / ChatGPT", BLUE),
        ("Step 2", "格式识别", "自动检测 7 种格式\n解析消息结构", ACCENT),
        ("Step 3", "噪声剥离", "移除系统标签\n行锚定匹配", GREEN),
        ("Step 4", "分块策略", "Exchange 对分块\n800字符/块", ORANGE),
        ("Step 5", "实体检测", "正则 -> COCA -> 词典\n双信号确认", RED),
        ("Step 6", "ID + 写入", "确定性ID配方\n批量Upsert", BLUE),
    ]

    for i, (step, title, desc, color) in enumerate(steps):
        x = 60 + i * 290
        y = 120
        rrect(draw, (x, y, x+270, y+350), r=14, fill=WHITE, outline=color, width=3)
        badge(draw, x+10, y+10, step, color)
        center(draw, title, y+50, LABEL, NAVY, x+135)
        for j, line in enumerate(desc.split("\n")):
            center(draw, line, y+90+j*28, SMALL, DARK, x+135)
        if i < len(steps) - 1:
            right_arrow(draw, x+275, y+175, x+290, color, 3)

    # Storage
    rrect(draw, (250, 530, 1550, 700), r=16, fill=(230, 255, 235), outline=GREEN, width=3)
    center(draw, "ChromaDB 存储", 555, H2, NAVY)
    center(draw, "Drawer: 逐字原文  |  Closet: AAAK压缩索引  |  知识图谱: SQLite", 600, BODY, DARK)
    center(draw, "每批 1000 Drawer / 原子写入 / 权限 0600 / 幂等ID", 640, SMALL, GRAY)

    down_arrow(draw, 1500, 475, 530, GREEN, 3)

    img.save(os.path.join(OUT, "mining-pipeline.png"))
    print("  mining-pipeline.png")


# ============================================================
# 3. Search Pipeline
# ============================================================
def gen_search():
    img, draw, W, H = canvas(1800, 1000)
    center(draw, "记忆召回管道", 25, TITLE, NAVY)

    box(draw, 700, 90, 400, 55, "用户查询", H2, LIGHT_BLUE, NAVY, BLUE)
    down_arrow(draw, 900, 150, 195, BLUE, 2)

    box(draw, 120, 200, 330, 75, "向量检索 Drawer", LABEL, WHITE, NAVY, ACCENT, "过量获取 3x 用于重排")
    box(draw, 570, 200, 330, 75, "向量检索 Closet", LABEL, WHITE, NAVY, ORANGE, "建立 source->boost 映射")
    box(draw, 1020, 200, 330, 75, "BM25 词法检索", LABEL, WHITE, NAVY, GREEN, "Union 策略合并候选")

    down_arrow(draw, 750, 280, 340, ORANGE, 2)
    box(draw, 450, 345, 600, 75, "Closet Boost 排名增强", LABEL, WHITE, NAVY, ORANGE, "排名序号信号 [0.40, 0.25, 0.15, 0.08, 0.04]")

    down_arrow(draw, 750, 425, 480, ORANGE, 2)
    box(draw, 450, 490, 600, 75, "Drawer-Grep 丰富化", LABEL, WHITE, NAVY, ACCENT, "关键词最佳 chunk + 邻居 (最多 10000 字符)")

    down_arrow(draw, 750, 570, 620, ACCENT, 2)
    box(draw, 350, 630, 800, 90, "BM25 + 向量混合排序", H2, WHITE, NAVY, BLUE, "final = 0.6 * vec_sim + 0.4 * bm25_norm")

    down_arrow(draw, 750, 725, 780, BLUE, 2)
    box(draw, 500, 790, 500, 65, "排序结果", H2, (230, 255, 235), NAVY, GREEN, "Top-K 相关记忆")

    # FTS5 fallback
    rrect(draw, (1300, 345, 1730, 470), r=12, fill=(255, 245, 235), outline=ORANGE)
    badge(draw, 1310, 355, "容错", ORANGE)
    center(draw, "HNSW 损坏时", 395, SMALL, DARK, 1515)
    center(draw, "SQLite FTS5 回退", 420, SMALL, DARK, 1515)
    draw.line([(1300*S, 410*S), (1100*S, 410*S)], fill=ORANGE, width=S)

    img.save(os.path.join(OUT, "search-pipeline.png"))
    print("  search-pipeline.png")


# ============================================================
# 4. Closet Boost
# ============================================================
def gen_closet():
    img, draw, W, H = canvas(1800, 800)
    center(draw, "Closet Boost 机制", 25, TITLE, NAVY)
    center(draw, "为什么用排名而非绝对距离？叙事内容的距离聚集在 1.2-1.5", 75, BODY, GRAY)

    boosts = [(1, 0.40), (2, 0.25), (3, 0.15), (4, 0.08), (5, 0.04)]
    for i, (rank, val) in enumerate(boosts):
        x = 150 + i * 300
        bar_h = int(val * 500)
        r = int(55 + val * 300)
        g = int(100 + val * 200)
        b = int(180 + val * 100)
        color = (r, g, b)
        # Bar
        rrect(draw, (x+20, 400-bar_h, x+200, 400), r=8, fill=color, outline=color)
        # Labels
        center(draw, f"#{rank}", 420, LABEL, NAVY, x+110)
        center(draw, f"{val}", 455, H2, color, x+110)

    # Formula
    rrect(draw, (200, 550, 1600, 680), r=14, fill=LIGHT_BLUE, outline=BLUE)
    center(draw, "effective_distance = max(0, min(2.0, distance - boost))", 590, H2, BLUE)
    center(draw, "boost 直接从余弦距离扣除，无 Closet 命中时 Drawer 独立排序", 635, BODY, DARK)

    # Cap note
    rrect(draw, (200, 710, 900, 760), r=10, fill=(255, 245, 235), outline=ORANGE, width=1)
    center(draw, "Closet 余弦距离 > 1.5 时信号太弱，不使用 boost", 725, SMALL, DARK, 550)

    img.save(os.path.join(OUT, "closet-boost.png"))
    print("  closet-boost.png")


# ============================================================
# 5. Hybrid Rank
# ============================================================
def gen_hybrid():
    img, draw, W, H = canvas(1800, 850)
    center(draw, "BM25 + 向量混合排序", 25, TITLE, NAVY)

    # Left: Vector
    rrect(draw, (60, 130, 510, 480), r=14, fill=WHITE, outline=ACCENT, width=3)
    badge(draw, 80, 140, "向量信号", ACCENT)
    center(draw, "ChromaDB 向量检索", 200, LABEL, NAVY, 285)
    center(draw, "余弦距离 -> 相似度", 240, BODY, DARK, 285)
    center(draw, "cosine: max(0, 1 - d)", 290, BODY, ACCENT, 285)
    center(draw, "l2: 1 / (1 + d)", 320, BODY, ACCENT, 285)
    center(draw, "使用绝对值", 370, SMALL, GRAY, 285)
    badge(draw, 170, 430, "权重: 0.6", BLUE)

    # Right: BM25
    rrect(draw, (580, 130, 1030, 480), r=14, fill=WHITE, outline=GREEN, width=3)
    badge(draw, 600, 140, "词法信号", GREEN)
    center(draw, "Okapi-BM25", 200, LABEL, NAVY, 805)
    center(draw, "Lucene 平滑 IDF", 240, BODY, DARK, 805)
    center(draw, "log((N-df+0.5)/(df+0.5)+1)", 290, BODY, GREEN, 805)
    center(draw, "小候选集上计算 IDF", 330, SMALL, GRAY, 805)
    center(draw, "Min-Max 归一化", 360, SMALL, GRAY, 805)
    badge(draw, 690, 430, "权重: 0.4", GREEN)

    # Arrows
    right_arrow(draw, 515, 280, 575, ACCENT, 3)

    # Center: Fusion
    rrect(draw, (1100, 180, 1700, 380), r=16, fill=LIGHT_BLUE, outline=BLUE, width=3)
    badge(draw, 1120, 190, "混合融合", BLUE)
    center(draw, "凸组合", 240, LABEL, NAVY, 1400)
    center(draw, "0.6 * vec_sim", 280, H2, ACCENT, 1400)
    center(draw, "+", 310, BODY, GRAY, 1400)
    center(draw, "0.4 * bm25_norm", 340, H2, GREEN, 1400)

    # Arrow to fusion
    right_arrow(draw, 1035, 280, 1095, BLUE, 3)

    # Output
    down_arrow(draw, 1400, 385, 500, BLUE, 3)
    box(draw, 1050, 510, 700, 70, "最终排序结果", H2, (230, 255, 235), NAVY, GREEN, "按 final_score 降序")

    # Note
    rrect(draw, (150, 630, 1650, 780), r=14, fill=(255, 248, 235), outline=ORANGE)
    center(draw, "关键设计", 650, LABEL, NAVY)
    center(draw, "向量相似度用绝对值 -> 增删候选不影响其他结果排序", 690, BODY, DARK)
    center(draw, "BM25 用 Min-Max 归一化 -> 权重可比较", 725, BODY, DARK)

    img.save(os.path.join(OUT, "hybrid-rank.png"))
    print("  hybrid-rank.png")


# ============================================================
# 6. Knowledge Graph
# ============================================================
def gen_kg():
    img, draw, W, H = canvas(1800, 900)
    center(draw, "知识图谱", 25, TITLE, NAVY)
    center(draw, "基于 SQLite 的时间实体关系图，支持时间旅行查询", 75, BODY, GRAY)

    entities = [
        ("Alice", "Person", 300, 250, RED),
        ("Project-X", "Project", 800, 250, BLUE),
        ("PostgreSQL", "Tool", 1300, 250, GREEN),
        ("Claude Code", "Tool", 300, 550, GREEN),
        ("Auth-Migration", "Concept", 800, 550, ORANGE),
        ("Kai", "Person", 1300, 550, RED),
    ]
    for name, etype, x, y, color in entities:
        rrect(draw, (x-100, y-40, x+100, y+40), r=20, fill=WHITE, outline=color, width=3)
        center(draw, name, y-20, LABEL, NAVY, x)
        badge(draw, x-25, y+10, etype, color)

    rels = [
        (300, 290, 800, 250, "works_on"),
        (800, 290, 1300, 250, "uses"),
        (300, 510, 300, 550, "developed_by"),
        (800, 510, 800, 550, "part_of"),
    ]
    for x0, y0, x1, y1, label in rels:
        draw.line([(x0*S, y0*S), (x1*S, y1*S)], fill=GRAY, width=2*S)
        mx, my = (x0+x1)//2, (y0+y1)//2
        badge(draw, mx-30, my-12, label, GRAY)

    # Triple structure
    rrect(draw, (80, 680, 830, 850), r=14, fill=WHITE, outline=BLUE)
    badge(draw, 100, 690, "三元组结构", BLUE)
    draw.text((120*S, 730*S), "Subject -> Predicate -> Object", font=BODY, fill=NAVY)
    draw.text((120*S, 765*S), "valid_from: 2026-01-15", font=BODY, fill=GREEN)
    draw.text((120*S, 800*S), "valid_to:   NULL (仍有效)", font=BODY, fill=RED)

    # Storage
    rrect(draw, (930, 680, 1720, 850), r=14, fill=WHITE, outline=GREEN)
    badge(draw, 950, 690, "SQLite 存储", GREEN)
    draw.text((970*S, 730*S), "WAL 模式 / B-tree 索引", font=BODY, fill=NAVY)
    draw.text((970*S, 765*S), "entities 表 + triples 表", font=BODY, fill=DARK)
    draw.text((970*S, 800*S), "零外部依赖，本地免费", font=BODY, fill=GRAY)

    img.save(os.path.join(OUT, "knowledge-graph.png"))
    print("  knowledge-graph.png")


# ============================================================
# 7. Memory Stack
# ============================================================
def gen_stack():
    img, draw, W, H = canvas(1800, 800)
    center(draw, "四层记忆堆栈", 25, TITLE, NAVY)

    layers = [
        ("L0 身份", "~100 tokens", "AI 角色定义", "始终加载", BLUE),
        ("L1 精华故事", "~500-800 tokens", "Top-15 最重要时刻", "始终加载", ACCENT),
        ("L2 房间回忆", "~200-500 tokens", "按翼楼/房间过滤", "话题匹配时", GREEN),
        ("L3 深度搜索", "可变", "完整语义查询", "显式请求时", ORANGE),
    ]

    for i, (name, size, desc, trigger, color) in enumerate(layers):
        y = 120 + i * 155
        # Width decreases by layer
        shrink = [0, 50, 120, 200][i]
        x = 100 + shrink
        w = 1600 - shrink * 2
        rrect(draw, (x, y, x+w, y+125), r=16, fill=WHITE, outline=color, width=3)

        # Left: name + size
        badge(draw, x+20, y+12, name, color)
        center(draw, size, y+55, H2, color, x+160)

        # Center: description
        center(draw, desc, y+50, BODY, DARK, 900)

        # Right: trigger
        rrect(draw, (x+w-210, y+80, x+w-20, y+115), r=8, fill=LIGHT_BLUE, outline=BLUE, width=1)
        center(draw, trigger, y+87, SMALL, DARK, x+w-115)

    # Cost
    rrect(draw, (300, 750, 1500, 795), r=12, fill=(230, 255, 235), outline=GREEN)
    center(draw, "唤醒成本: L0 + L1 = 600-900 tokens (仅占上下文 ~5%)", 762, LABEL, NAVY)

    img.save(os.path.join(OUT, "memory-stack.png"))
    print("  memory-stack.png")


# ============================================================
# 8. Benchmark Comparison
# ============================================================
def gen_benchmark():
    img, draw, W, H = canvas(2000, 850)
    center(draw, "竞品基准对比", 25, TITLE, NAVY)

    cols = [("系统", 180), ("策略", 280), ("LongMemEval", 200), ("ConvoMem", 150), ("LLM", 130), ("本地", 100), ("成本", 130)]
    x0 = 115
    y = 110
    x = x0
    for name, w in cols:
        rrect(draw, (x, y, x+w, y+45), r=0, fill=NAVY, outline=NAVY)
        center(draw, name, y+10, LABEL, WHITE, x+w//2)
        x += w

    rows = [
        ("MemPalace", "原文逐字", "96.6% R@5", "92.9%", "不需要", "是", "$0", GREEN),
        ("Mastra OM", "LLM观察提取", "94.87% QA", "-", "必需", "否", "高", ACCENT),
        ("Hindsight", "LLM提取", "91.4% QA", "-", "必需", "否", "高", ACCENT),
        ("Supermemory", "LLM+RAG", "~85% QA", "-", "必需", "否", "高", ORANGE),
        ("Mem0", "LLM提取事实", "-", "30-45%", "必需", "否", "高", RED),
        ("Zep", "图数据库", "71.2% QA", "-", "必需", "否", "高", RED),
    ]

    for ri, row in enumerate(rows):
        y = 160 + ri * 58
        bg = WHITE if ri % 2 == 0 else LIGHT_GRAY
        x = x0
        for ci, ((_, w), val) in enumerate(zip(cols, row[:7])):
            rrect(draw, (x, y, x+w, y+50), r=0, fill=bg, outline=CARD_BORDER, width=1)
            fc = row[7] if ci == 0 else DARK
            f = LABEL if ci == 0 else BODY
            center(draw, val, y+12, f, fc, x+w//2)
            x += w

    # Insight
    rrect(draw, (80, 540, 1920, 680), r=14, fill=LIGHT_BLUE, outline=BLUE)
    center(draw, "核心洞察", 555, H2, NAVY)
    center(draw, "零 LLM 约束下无人能及  |  Mastra 端到端 QA 更强 (需 API 费用)", 600, BODY, DARK)
    center(draw, "两种路线: MemPalace = 存储型 (记住一切)  vs  Mastra = 理解型 (AI 压缩)", 640, BODY, GRAY)

    img.save(os.path.join(OUT, "benchmark-comparison.png"))
    print("  benchmark-comparison.png")


if __name__ == "__main__":
    gen_palace()
    gen_mining()
    gen_search()
    gen_closet()
    gen_hybrid()
    gen_kg()
    gen_stack()
    gen_benchmark()
    print("\nDone! 8 diagrams generated.")
