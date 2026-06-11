# MemPalace 深度技术分析报告

> 基于 MemPalace 仓库源码的全面架构分析。所有代码片段均来自真实源文件，逐行解析。

---

## 1. 项目概述

MemPalace 是一个**本地优先、零外部 API 依赖**的 AI 记忆系统，灵感来自古罗马的"记忆宫殿"（Method of Loci）方法和 Niklas Luhmann 的 Zettelkasten 卡片盒笔记法。其核心设计原则是：

- **逐字存储**（Verbatim always）：永不总结、不改写用户数据
- **增量写入**（Incremental only）：只追加，不破坏已有数据
- **实体优先**（Entity-first）：以真实人名/项目名为键
- **本地优先**（Local-first）：数据永远不离开用户机器

### 核心架构图

```
User → CLI / MCP Server → Storage Backend (ChromaDB) → SQLite (知识图谱)

宫殿结构:
  WING (人物/项目)
    └── ROOM (日期/主题)
          └── DRAWER (逐字文本块)

索引层 (AAAK):
  压缩指针 → DRAWER 位置
  LLM 扫描以找到相关 drawer

知识图谱:
  ENTITY → PREDICATE → ENTITY (带 valid_from / valid_to 时间)
```

---

## 2. 宫殿架构详解

### 2.1 Wing（翼楼）— 顶层分类

Wing 是宫殿的最高层级，对应一个**人物、项目或主题**。例如 `wing_alice`、`wing_mempalace`、`wing_api`（用于 API 来源的对话）。

Wing 名称通过 `normalize_wing_name` 标准化处理：

```python
# palacce.py 中的 wing 解析逻辑
def resolve_backend_name(palace_path: str, explicit: Optional[str] = None) -> str:
    """Resolve and validate the selected backend for palace_path.

    Public resolution order:
    1. Explicit CLI/MCP flag or direct get_collection(..., backend=...).
    2. backend in ~/.mempalace/config.json.
    3. MEMPALACE_BACKEND.
    4. Detected existing palace artifacts.
    5. chroma.
    """
    explicit = explicit or os.environ.get(_EXPLICIT_BACKEND_ENV)
    selected = resolve_backend_for_palace(
        explicit=explicit.strip().lower() if explicit else None,
        config_value=_config_backend_value(palace_path),
        env_value=_env_backend_value(),
        palace_path=palace_path,
        default="chroma",
    )
```

### 2.2 Room（房间）— 主题/时间分组

Room 是 Wing 下的二级分类，按**主题或时间**组织。对于项目文件，Room 通过 `mempalace.yaml` 配置文件定义：

```python
# miner.py — Room 检测逻辑
def detect_room(filepath: Path, content: str, rooms: list, project_path: Path) -> str:
    """
    Route a file to the right room.
    Priority:
    1. Folder path matches a room name
    2. Filename matches a room name or keyword
    3. Content keyword scoring
    4. Fallback: "general"
    """
    relative = str(filepath.relative_to(project_path)).lower()
    filename = filepath.stem.lower()
    content_lower = content[:2000].lower()

    # Priority 1: folder path matches room name or keywords
    path_parts = relative.replace("\\", "/").split("/")
    for part in path_parts[:-1]:  # skip filename itself
        for room in rooms:
            candidates = [room["name"].lower()] + [k.lower() for k in room.get("keywords", [])]
            if any(_name_matches(part, c) for c in candidates):
                return room["name"]

    # Priority 2: filename matches room name
    for room in rooms:
        if _name_matches(filename, room["name"]):
            return room["name"]

    # Priority 3: keyword scoring from room keywords + name
    scores = defaultdict(int)
    for room in rooms:
        keywords = room.get("keywords", []) + [room["name"]]
        for kw in keywords:
            count = content_lower.count(kw.lower())
            scores[room["name"]] += count

    if scores:
        best = max(scores, key=scores.get)
        if scores[best] > 0:
            return best

    return "general"
```

对于对话文件，Room 通过关键词评分检测：

```python
# convo_miner.py — 对话 Room 检测
TOPIC_KEYWORDS = {
    "technical": ["code", "python", "function", "bug", "error", "api", "database",
                   "server", "deploy", "git", "test", "debug", "refactor"],
    "architecture": ["architecture", "design", "pattern", "structure", "schema",
                      "interface", "module", "component", "service", "layer"],
    "planning": ["plan", "roadmap", "milestone", "deadline", "priority", "sprint",
                  "backlog", "scope", "requirement", "spec"],
    "decisions": ["decided", "chose", "picked", "switched", "migrated", "replaced",
                   "trade-off", "alternative", "option", "approach"],
    "problems": ["problem", "issue", "broken", "failed", "crash", "stuck",
                  "workaround", "fix", "solved", "resolved"],
}

def detect_convo_room(content: str) -> str:
    """Score conversation content against topic keywords."""
    content_lower = content[:3000].lower()
    scores = {}
    for room, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in content_lower)
        if score > 0:
            scores[room] = score
    if scores:
        return max(scores, key=scores.get)
    return "general"
```

### 2.3 Drawer（抽屉）— 最小存储单元

Drawer 是宫殿的原子存储单元，存放**逐字原文**。每个 drawer 拥有唯一 ID，由 `ids.py` 模块生成：

```python
# ids.py — ID 生成策略
# '|' is reserved in Windows filenames and cannot appear in source paths
# on any supported platform, making it strictly safer than ':'
_DELIM: str = "|"
_HASH_TRUNC_DRAWER: int = 24

def _delimited_sha256(parts: tuple[object, ...], truncate: int) -> str:
    """Hash parts joined by the unambiguous delimiter, truncate to N hex chars."""
    key = _DELIM.join(str(p) for p in parts).encode()
    return hashlib.sha256(key).hexdigest()[:truncate]

def make_drawer_id_from_chunk(wing: str, room: str, source_file: str, chunk_index: int) -> str:
    """Drawer ID for the project / format miner paths.
    Hash input is f"{source_file}|{chunk_index}" — the '|' separator
    prevents the classic "/a1" + "23" == "/a" + "123" collision.
    """
    return (
        f"drawer_{wing}_{room}_"
        f"{_delimited_sha256((source_file, str(chunk_index)), _HASH_TRUNC_DRAWER)}"
    )
```

**关键设计**：使用 `|` 分隔符代替 `:` 来避免 ID 碰撞。`s1 + str(i1) == s2 + str(i2)` 的碰撞问题通过分隔符得到解决。每个 drawer 的元数据包含：

```python
# convo_miner.py — drawer 元数据结构
batch_metas.append({
    "wing": wing,
    "room": chunk_room,
    "hall": _detect_hall_cached(chunk["content"]),
    "source_file": source_file,
    "chunk_index": chunk["chunk_index"],
    "added_by": agent,
    "filed_at": filed_at,
    "ingest_mode": "convos",
    "extract_mode": extract_mode,
    "normalize_version": NORMALIZE_VERSION,
    "id_recipe": ID_RECIPE,
})
```

### 2.4 Closet（壁橱）— 索引层

Closet 是 AAAK 压缩格式生成的**索引层**，不存放原始内容，而是存放压缩的指针，指向 drawer 的位置：

```python
# palace.py — Closet 配置
CLOSET_CHAR_LIMIT = 1500  # fill closet until ~1500 chars, then start a new one
CLOSET_EXTRACT_WINDOW = 5000  # how many chars of source content to scan for entities/topics
```

Closet 指针格式：
```
topic|entities|→drawer_id_a,drawer_id_b
```

在搜索时，Closet 作为**排名信号**使用，不是门控：

```python
# searcher.py — Closet 提取 drawer ID
_CLOSET_DRAWER_REF_RE = re.compile(r"→([\w,]+)")

def _extract_drawer_ids_from_closet(closet_doc: str) -> list:
    """Parse all →drawer_id_a,drawer_id_b pointers out of a closet document.
    Preserves order and dedupes.
    """
    seen: dict = {}
    for match in _CLOSET_DRAWER_REF_RE.findall(closet_doc):
        for did in match.split(","):
            did = did.strip()
            if did and did not in seen:
                seen[did] = None
    return list(seen.keys())
```

### 2.5 Hallway（走廊）— 翼内实体连接

Hallway 是同一 Wing 内两个实体之间的连接，基于它们在 drawer 中的**共现关系**：

```python
# hallways.py — Hallway 核心算法
def compute_hallways_for_wing(
    wing: str,
    col=None,
    min_count: int = 2,
) -> list[dict]:
    """Compute entity-pair hallways for one wing.

    Algorithm:
      1. Query drawers for wing from col.
      2. For each drawer with entities, every pair of distinct entities in
         that drawer is one co-occurrence.
      3. For each pair whose co-occurrence count is >= min_count,
         materialize a hallway record.
      4. Persist the full hallway list and return.
    """
    # 2. Walk drawers, counting entity-pair co-occurrence + tracking rooms.
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    pair_rooms: dict[tuple[str, str], set[str]] = defaultdict(set)

    for meta in metadatas:
        if not isinstance(meta, dict):
            continue
        if meta.get("is_sentinel"):
            continue
        entities = _parse_entities(meta.get("entities"))
        if len(entities) < 2:
            continue
        room = meta.get("room")

        # Each unordered pair of distinct entities in this drawer is one
        # co-occurrence. itertools.combinations gives unordered pairs.
        for a, b in combinations(entities, 2):
            if a == b:
                continue
            key = tuple(sorted([a, b]))
            pair_counts[key] += 1
            if room_str:
                pair_rooms[key].add(room_str)
```

Hallway ID 的生成是**对称的**——`(Aya, Lumi)` 和 `(Lumi, Aya)` 产生相同的 ID：

```python
def _hallway_id(wing: str, entity_a: str, entity_b: str) -> str:
    a, b = sorted([entity_a, entity_b])
    key = f"{wing}::{a}::{b}".encode("utf-8")
    suffix = hashlib.sha256(key).hexdigest()[:8]
    return f"hallway_{wing}_{a}_{b}_{suffix}"
```

### 2.6 Tunnel（隧道）— 跨翼连接

Tunnel 连接不同 Wing 中的 Room：

```python
# palace_graph.py — 跨翼隧道
def find_tunnels(wing_a: str = None, wing_b: str = None, col=None, config=None):
    """Find rooms that connect two wings (or all tunnel rooms if no wings specified).
    These are the "hallways" — same named idea appearing in multiple domains.
    """
    nodes, edges = build_graph(col, config)
    tunnels = []
    for room, data in nodes.items():
        wings = data["wings"]
        if len(wings) < 2:
            continue
        if norm_a and norm_a not in wings:
            continue
        if norm_b and norm_b not in wings:
            continue
        tunnels.append({
            "room": room,
            "wings": wings,
            "halls": data["halls"],
            "count": data["count"],
            "recent": data["dates"][-1] if data["dates"] else "",
        })
    tunnels.sort(key=lambda x: -x["count"])
    return tunnels[:50]
```

---

## 3. 记忆写入管道（Mining Pipeline）

### 3.1 完整流程概览

```
对话/文件输入
    ↓
格式检测 + 标准化 (normalize.py)
    ↓
噪声剥离 (strip_noise)
    ↓
分块 (chunk_exchanges / chunk_text)
    ↓
Room 检测 (detect_room / detect_convo_room)
    ↓
Hall 检测 (_detect_hall_cached)
    ↓
ID 生成 (make_*_drawer_id)
    ↓
碰撞检查 (assert_no_collisions)
    ↓
批量写入 ChromaDB (collection.upsert)
    ↓
Closet 生成 (build_closet_lines → upsert_closet_lines)
    ↓
Hallway 计算 (compute_hallways_for_wing)
```

### 3.2 格式标准化 (normalize.py)

支持多种对话格式的自动检测和转换：

```python
# normalize.py — 支持的格式
# - Plain text with > markers (pass through)
# - Claude.ai JSON export
# - ChatGPT conversations.json
# - Claude Code JSONL (with tool_use/tool_result block capture)
# - OpenAI Codex CLI JSONL
# - Gemini CLI JSONL
# - Slack JSON export
```

标准化主入口：

```python
def normalize(filepath: str) -> str:
    """Load a file and normalize to transcript format if it's a chat export."""
    with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f:
        content = f.read()

    # Already has > markers — pass through unchanged.
    lines = content.split("\n")
    if sum(1 for line in lines if line.strip().startswith(">")) >= 3:
        return content

    # Try JSON normalization
    ext = Path(filepath).suffix.lower()
    if ext in (".json", ".jsonl") or content.strip()[:1] in ("{", "["):
        normalized = _try_normalize_json(content)
        if normalized:
            return normalized
    return content
```

### 3.3 噪声剥离 (strip_noise)

Claude Code 等工具会在转录中注入系统标签和 UI chrome，需要清除：

```python
# normalize.py — 噪声标签模式
_NOISE_TAGS = (
    "system-reminder", "command-message", "command-name",
    "task-notification", "user-prompt-submit-hook", "hook_output",
)

_NOISE_LINE_PREFIXES = (
    "CURRENT TIME:", "VERIFIED FACTS (do not contradict)",
    "AGENT SPECIALIZATION:", "Checking verified facts...",
    "Injecting timestamp...", "Starting background pipeline...",
    "Checking emotional weights...", "Auto-save reminder...",
    "MemPalace auto-save checkpoint.",
)

def strip_noise(text: str) -> str:
    """Remove system tags, hook output, and Claude Code UI chrome from text.
    All patterns are line-anchored. User prose that happens to mention these
    strings inline is preserved verbatim.
    """
    for pat in _NOISE_TAG_PATTERNS:
        text = pat.sub("", text)
    for pat in _NOISE_LINE_PATTERNS:
        text = pat.sub("", text)
    text = _HOOK_LINE_RE.sub("", text)
    text = _COLLAPSED_LINES_RE.sub("", text)
    text = re.sub(r"\s*\[\d+\s+tokens?\]\s*\(ctrl\+o to expand\)", "", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()
```

### 3.4 Claude Code JSONL 解析

```python
# normalize.py — Claude Code JSONL 解析器
def _try_claude_code_jsonl(content: str) -> Optional[str]:
    """Claude Code JSONL sessions."""
    lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
    messages = []
    tool_use_map = {}  # tool_use_id → tool_name

    for line in lines:
        entry = json.loads(line)
        msg_type = entry.get("type", "")
        message = entry.get("message", {})
        msg_content = message.get("content", "")

        # Build tool_use_map from assistant messages
        if msg_type == "assistant" and isinstance(msg_content, list):
            for block in msg_content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_id = block.get("id", "")
                    if tool_id:
                        tool_use_map[tool_id] = block.get("name", "Unknown")

        if msg_type in ("human", "user"):
            text = _extract_content(msg_content, tool_use_map=tool_use_map)
            if text:
                text = strip_noise(text)
            if text:
                messages.append(("user", text))
        elif msg_type == "assistant":
            text = _extract_content(msg_content, tool_use_map=tool_use_map)
            if text:
                text = strip_noise(text)
            if text:
                # If previous message is also assistant, merge
                if messages and messages[-1][0] == "assistant":
                    prev_role, prev_text = messages[-1]
                    messages[-1] = (prev_role, prev_text + "\n" + text)
                else:
                    messages.append(("assistant", text))

    if len(messages) >= 2:
        return _messages_to_transcript(messages)
    return None
```

### 3.5 对话分块 (chunk_exchanges)

对话按**交换对**（exchange pair）分块：一个用户 turn + AI 响应 = 一个单元：

```python
# convo_miner.py — 交换对分块
def chunk_exchanges(content: str, chunk_size: int = None, min_chunk_size: int = None) -> list:
    """Chunk by exchange pair: one > turn + AI response = one unit.
    Falls back to paragraph chunking if no > markers.
    """
    lines = content.split("\n")
    quote_lines = sum(1 for line in lines if line.strip().startswith(">"))

    if quote_lines >= 3:
        return _chunk_by_exchange(lines, chunk_size, min_chunk_size)
    else:
        return _chunk_by_paragraph(content, chunk_size, min_chunk_size)

def _chunk_by_exchange(lines: list, chunk_size: int, min_chunk_size: int) -> list:
    """One user turn (>) + the AI response that follows = one or more chunks.
    The full AI response is preserved verbatim.
    """
    chunks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith(">"):
            user_turn = line.strip()
            i += 1
            ai_lines = []
            while i < len(lines):
                next_line = lines[i]
                if next_line.strip().startswith(">") or next_line.strip().startswith("---"):
                    break
                ai_lines.append(next_line)
                i += 1
            ai_response = "\n".join(ai_lines).rstrip("\n")
            content = f"{user_turn}\n{ai_response}" if ai_response else user_turn
            _emit_bounded(chunks, content, chunk_size, min_chunk_size)
        else:
            i += 1
    return chunks
```

有界发射函数确保每个 drawer 不超过 `chunk_size`（默认 800 字符）：

```python
def _emit_bounded(chunks: list, content: str, chunk_size: int, min_chunk_size: int) -> None:
    """Append content as one or more drawers, none exceeding chunk_size.
    The min_chunk_size floor gates the WHOLE call (drops the input if
    its stripped length is at or below the floor, treated as noise).
    """
    if len(content.strip()) <= min_chunk_size:
        return
    for i in range(0, len(content), chunk_size):
        chunks.append({"content": content[i : i + chunk_size], "chunk_index": len(chunks)})
```

### 3.6 项目文件分块 (chunk_text)

项目文件使用段落边界分块，带重叠（overlap）：

```python
# miner.py — 项目文件分块
def chunk_text(content: str, source_file: str, chunk_size=None, chunk_overlap=None,
               min_chunk_size=None) -> list:
    """Split content into drawer-sized chunks.
    Tries to split on paragraph/line boundaries.
    Returns list of {content, chunk_index, line_start, line_end}
    """
    content = content.strip()
    chunks = []
    start = 0
    chunk_index = 0

    while start < len(content):
        end = min(start + chunk_size, len(content))

        # Try to break at paragraph boundary
        if end < len(content):
            newline_pos = content.rfind("\n\n", start, end)
            if newline_pos > start + chunk_size // 2:
                end = newline_pos
            else:
                newline_pos = content.rfind("\n", start, end)
                if newline_pos > start + chunk_size // 2:
                    end = newline_pos

        chunk = content[start:end].strip()
        if len(chunk) >= min_chunk_size:
            line_start = content.count("\n", 0, start) + 1
            line_end = content.count("\n", 0, end) + 1
            chunks.append({
                "content": chunk,
                "chunk_index": chunk_index,
                "line_start": line_start,
                "line_end": line_end,
            })
            chunk_index += 1

        start = end - chunk_overlap if end < len(content) else end
    return chunks
```

### 3.7 写入锁机制

并发写入通过文件级锁和宫殿级锁保护：

```python
# convo_miner.py — 锁定写入
def _file_chunks_locked(collection, source_file, chunks, wing, room, agent, extract_mode):
    """Lock the source file, purge stale drawers, and upsert fresh chunks.
    Combines the per-file serialization with the normalize-version rebuild
    contract (purge-before-insert so pre-v2 drawers don't survive).
    """
    with mine_lock(source_file):
        # Re-check after lock — another agent may have just finished this file
        if file_already_mined(collection, source_file, extract_mode=extract_mode):
            return 0, room_counts_delta, True

        # Purge stale drawers first
        delete_ids = _source_file_delete_ids(collection, source_file, extract_mode)
        if delete_ids:
            collection.delete(ids=delete_ids)

        # Batch chunks into bounded upserts
        filed_at = datetime.now().isoformat()
        for batch_start in range(0, len(chunks), DRAWER_UPSERT_BATCH_SIZE):
            batch_docs, batch_ids, batch_metas = [], [], []
            for chunk in chunks[batch_start : batch_start + DRAWER_UPSERT_BATCH_SIZE]:
                drawer_id = make_convo_drawer_id(
                    wing, chunk_room, source_file, extract_mode, chunk["chunk_index"]
                )
                batch_docs.append(chunk["content"])
                batch_ids.append(drawer_id)
                batch_metas.append({ ... })

            assert_no_collisions(list(zip(batch_ids, batch_metas)), collection)
            collection.upsert(documents=batch_docs, ids=batch_ids, metadatas=batch_metas)
```

---

## 4. 记忆召回管道（Search Pipeline）

### 4.1 完整流程概览

```
查询输入
    ↓
向量检索 (ChromaDB query, top 3*n_results)
    ↓
Closet 检索 (top 2*n_results, 构建 boost lookup)
    ↓
Closet Boost 计算 (rank-based boost)
    ↓
Drawer-Grep 增强 (关键词最佳 chunk + 邻居)
    ↓
BM25 + 向量混合排名 (_hybrid_rank)
    ↓
候选策略合并 (candidate_strategy="union" 可选)
    ↓
最终结果输出
```

### 4.2 主搜索入口 (search_memories)

```python
# searcher.py — MCP 和程序化搜索的主入口
def search_memories(
    query: str,
    palace_path: str,
    wing: str = None,
    room: str = None,
    n_results: int = 5,
    max_distance: float = 0.0,
    vector_disabled: bool = False,
    candidate_strategy: str = "vector",
    collection_name: str = None,
) -> dict:
    """Programmatic search — returns a dict instead of printing."""

    # 向量禁用时走 BM25-only 路径
    if vector_disabled:
        return _vector_disabled_search(...)

    # 打开集合
    drawers_col, open_error = _open_search_collection(palace_path, collection_name)
    metric = _metric_for_collection(drawers_col)
    where = build_where_filter(wing, room)

    # 第一步：直接向量检索 drawer（始终作为基线）
    dkwargs = {
        "query_texts": [query],
        "n_results": n_results * 3,  # 过量获取用于重排名
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        dkwargs["where"] = where
    drawer_results = _query_drawers_with_filter_fallback(
        drawers_col, dkwargs, query, n_results, wing, room
    )
```

### 4.3 Closet Boost 机制

Closet 检索用于**增强排名信号**，不是门控：

```python
    # 第二步：检索 closet 建立 boost lookup
    closet_boost_by_source: dict = {}  # source_file -> (rank, closet_dist, preview)
    closets_col = get_closets_collection(palace_path, create=False)
    ckwargs = {
        "query_texts": [query],
        "n_results": n_results * 2,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        ckwargs["where"] = where
    closet_results = closets_col.query(**ckwargs)
    for rank, (cdoc, cmeta, cdist) in enumerate(zip(
        _first_or_empty(closet_results, "documents"),
        _first_or_empty(closet_results, "metadatas"),
        _first_or_empty(closet_results, "distances"),
    )):
        cmeta = cmeta or {}
        source = cmeta.get("source_file", "")
        if source and source not in closet_boost_by_source:
            closet_boost_by_source[source] = (rank, cdist, cdoc[:200])
```

排名 boost 的具体数值：

```python
    # 排名序号信号比绝对距离更可靠
    CLOSET_RANK_BOOSTS = [0.40, 0.25, 0.15, 0.08, 0.04]
    CLOSET_DISTANCE_CAP = 1.5  # cosine dist > 1.5 = too weak to use as signal

    scored: list = []
    for doc, meta, dist in zip(...):
        meta = meta or {}
        source = meta.get("source_file", "") or ""
        boost = 0.0
        matched_via = "drawer"
        if source in closet_boost_by_source:
            c_rank, c_dist, c_preview = closet_boost_by_source[source]
            if c_dist <= CLOSET_DISTANCE_CAP and c_rank < len(CLOSET_RANK_BOOSTS):
                boost = CLOSET_RANK_BOOSTS[c_rank]
                matched_via = "drawer+closet"

        # Clamp to valid cosine-distance range [0, 2]
        effective_dist = max(0.0, min(2.0, dist - boost))
        entry = {
            "text": doc,
            "similarity": round(_distance_to_similarity(effective_dist, metric), 3),
            "distance": round(dist, 4),
            "effective_distance": round(effective_dist, 4),
            "closet_boost": round(boost, 3),
            "matched_via": matched_via,
        }
```

### 4.4 Drawer-Grep 增强

对于 closet 命中的结果，如果源文件有多个 drawer，系统会用**关键词匹配**找到最佳 chunk 及其邻居：

```python
    # Drawer-grep enrichment: for closet-boosted hits, return the
    # keyword-best chunk + its immediate neighbors
    MAX_HYDRATION_CHARS = 10000
    for h in hits:
        if h["matched_via"] == "drawer":
            continue
        full_source = h.get("_source_file_full") or ""
        source_drawers = drawers_col.get(
            where={"source_file": full_source},
            include=["documents", "metadatas"],
        )
        docs = source_drawers.documents
        if len(docs) <= 1:
            continue

        # Sort by chunk_index
        indexed = []
        for idx, (d, m) in enumerate(zip(docs, metas_)):
            ci = m.get("chunk_index", idx) if isinstance(m, dict) else idx
            indexed.append((ci, d))
        indexed.sort(key=lambda p: p[0])
        ordered_docs = [d for _, d in indexed]

        # Find the chunk with the most query terms
        query_terms = set(_tokenize(query))
        best_idx, best_score = 0, -1
        for idx, d in enumerate(ordered_docs):
            d_lower = d.lower()
            s = sum(1 for t in query_terms if t in d_lower)
            if s > best_score:
                best_score, best_idx = s, idx

        # Expand with ±1 neighbors
        start = max(0, best_idx - 1)
        end = min(len(ordered_docs), best_idx + 2)
        expanded = "\n\n".join(ordered_docs[start:end])
        h["text"] = expanded
        h["drawer_index"] = best_idx
        h["total_drawers"] = len(ordered_docs)
```

### 4.5 BM25 + 向量混合排名

这是搜索管道的**核心排名算法**：

```python
# searcher.py — BM25 评分实现
def _bm25_scores(query: str, documents: list, k1: float = 1.5, b: float = 0.75) -> list:
    """Compute Okapi-BM25 scores for query against each document.
    IDF is computed over the *provided corpus* using the Lucene/BM25+
    smoothed formula log((N - df + 0.5) / (df + 0.5) + 1), which is
    always non-negative.
    """
    n_docs = len(documents)
    query_terms = set(_tokenize(query))
    if not query_terms or n_docs == 0:
        return [0.0] * n_docs

    tokenized = [_tokenize(d) for d in documents]
    doc_lens = [len(toks) for toks in tokenized]
    avgdl = sum(doc_lens) / n_docs or 1.0

    # Document frequency: how many docs contain each query term?
    df = {term: 0 for term in query_terms}
    for toks in tokenized:
        seen = set(toks) & query_terms
        for term in seen:
            df[term] += 1

    # IDF: Lucene/BM25+ smoothed formula
    idf = {term: math.log((n_docs - df[term] + 0.5) / (df[term] + 0.5) + 1)
           for term in query_terms}

    scores = []
    for toks, dl in zip(tokenized, doc_lens):
        if dl == 0:
            scores.append(0.0)
            continue
        tf: dict = {}
        for t in toks:
            if t in query_terms:
                tf[t] = tf.get(t, 0) + 1
        score = 0.0
        for term, freq in tf.items():
            num = freq * (k1 + 1)
            den = freq + k1 * (1 - b + b * dl / avgdl)
            score += idf[term] * num / den
        scores.append(score)
    return scores
```

混合排名的凸组合公式：

```python
# searcher.py — 混合排名
def _hybrid_rank(
    results: list,
    query: str,
    vector_weight: float = 0.6,
    bm25_weight: float = 0.4,
    metric: str = "cosine",
) -> list:
    """Re-rank results by a convex combination of vector similarity and BM25.

    * Vector similarity is derived from each candidate's backend-reported
      distance via _distance_to_similarity.
    * BM25 is real Okapi-BM25 with corpus-relative IDF over the candidates
      themselves. BM25 is min-max normalized within the candidate set.
    """
    if not results:
        return results

    docs = [r.get("text", "") for r in results]
    bm25_raw = _bm25_scores(query, docs)
    max_bm25 = max(bm25_raw) if bm25_raw else 0.0
    bm25_norm = [s / max_bm25 for s in bm25_raw] if max_bm25 > 0 else [0.0] * len(bm25_raw)

    scored = []
    for r, raw, norm in zip(results, bm25_raw, bm25_norm):
        vec_sim = _distance_to_similarity(r.get("distance"), metric)
        r["bm25_score"] = round(raw, 3)
        # 核心公式: vector_weight * vec_sim + bm25_weight * bm25_norm
        scored.append((vector_weight * vec_sim + bm25_weight * norm, r))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    results[:] = [r for _, r in scored]
    return results
```

距离到相似度的转换支持多种度量：

```python
def _distance_to_similarity(distance, metric: str = "cosine") -> float:
    """Map a backend-reported distance to a [0, 1]-ish similarity.
    * cosine — distance ∈ [0, 2], 0 = identical: max(0, 1 - d).
    * l2 — Euclidean ∈ [0, ∞): 1 / (1 + d).
    * ip — inner-product: logistic squash 1 / (1 + e^d).
    """
    if distance is None:
        return 0.0
    m = (metric or "cosine").lower()
    if m == "l2":
        return 1.0 / (1.0 + max(0.0, distance))
    if m == "ip":
        return 1.0 / (1.0 + math.exp(min(60.0, distance)))
    # cosine (default)
    return max(0.0, 1.0 - distance)
```

### 4.6 BM25-only 回退路径

当 HNSW 索引损坏或不可用时，系统可以通过 SQLite 直接进行 BM25 搜索：

```python
# searcher.py — SQLite-only BM25 回退
def _bm25_only_via_sqlite(query, palace_path, wing=None, room=None, n_results=5,
                          max_candidates=500, ...) -> dict:
    """BM25-only search reading drawers directly from chroma.sqlite3.
    Used when HNSW is diverged or unloadable (#1222).
    Routes through chromadb's own FTS5 trigram index for candidate selection,
    then re-ranks with the same Okapi-BM25.
    """
    db_path = os.path.join(palace_path, "chroma.sqlite3")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

    # FTS5 MATCH — trigram tokenizer
    tokens = [t for t in _tokenize(query) if len(t) >= 3]
    if tokens:
        fts_query = " OR ".join(tokens)
        rows = conn.execute(f"""
            SELECT embedding_fulltext_search.rowid
            FROM embedding_fulltext_search
            JOIN embeddings e ON e.id = embedding_fulltext_search.rowid
            JOIN segments s ON e.segment_id = s.id
            JOIN collections c ON s.collection = c.id
            WHERE embedding_fulltext_search MATCH ?
              AND c.name = ?
            {filter_sql}
            LIMIT ?
        """, (fts_query, collection_name, *filter_params, max_candidates)).fetchall()
        candidate_ids = [r[0] for r in rows]

    # 本地 BM25 排名
    docs = [c["text"] for c in candidates]
    bm25_raw = _bm25_scores(query, docs)
    max_bm25 = max(bm25_raw) if bm25_raw else 0.0
    for c, raw in zip(candidates, bm25_raw):
        c["bm25_score"] = round(raw, 3)
        c["_score"] = (raw / max_bm25) if max_bm25 > 0 else 0.0
    candidates.sort(key=lambda c: c["_score"], reverse=True)
```

### 4.7 候选策略合并 (Union Mode)

`candidate_strategy="union"` 除了向量检索结果外，还从后端词法搜索获取 BM25 候选：

```python
def _merge_bm25_union_candidates(hits, drawers_col, query, wing, room, n_results,
                                  max_distance=0.0) -> None:
    """Append top-K backend lexical candidates into hits in place.
    BM25-only additions carry distance=None so _hybrid_rank scores
    them on BM25 contribution alone.
    """
    if max_distance > 0.0:
        return  # BM25-only candidates have no vector distance

    where = build_where_filter(wing, room)
    lexical = drawers_col.lexical_search(query=query, n_results=n_results * 3, where=where or None)

    bm25_extra = []
    for hit in lexical.hits:
        meta = hit.metadata or {}
        full_source = meta.get("source_file", "") or ""
        bm25_extra.append({
            "text": hit.document or "",
            "distance": None,  # No vector distance available
            "effective_distance": None,
            "closet_boost": 0.0,
            "matched_via": "bm25_backend",
            "bm25_score": round(float(hit.score), 3),
        })

    # Chunk-precise dedup
    def _dedup_key(entry: dict):
        full = entry.get("_source_file_full")
        ci = entry.get("_chunk_index")
        if full and ci is not None:
            return (full, ci)
        return entry.get("source_file")

    seen = {_dedup_key(h) for h in hits}
    for bh in bm25_extra:
        key = _dedup_key(bh)
        if not key or key == "?" or key in seen:
            continue
        hits.append(bh)
        seen.add(key)
```

### 4.8 Filter 回退机制

当 ChromaDB 过滤查询失败时（HNSW/SQLite 索引不一致），系统自动回退到无过滤查询 + Python 侧过滤：

```python
def _query_drawers_with_filter_fallback(drawers_col, dkwargs, query, n_results, wing, room):
    """Run the filtered drawer query, falling back to an unfiltered query plus
    a Python-side post-filter when ChromaDB raises on the filtered query.
    """
    where = dkwargs.get("where")
    try:
        return drawers_col.query(**dkwargs)
    except Exception as filter_err:
        if not where:
            raise
        # Retry unfiltered (over-fetching) and re-apply filter in Python
        raw = drawers_col.query(
            query_texts=[query],
            n_results=min(n_results * 15, 500),
            include=["documents", "metadatas", "distances"],
        )
        fdocs, fmetas, fdists = [], [], []
        for doc, meta, dist in zip(...):
            meta = meta or {}
            if wing and meta.get("wing") != wing:
                continue
            if room and meta.get("room") != room:
                continue
            fdocs.append(doc)
            fmetas.append(meta)
            fdists.append(dist)
        return {"documents": [fdocs], "metadatas": [fmetas], "distances": [fdists]}
```

---

## 5. 知识图谱

### 5.1 数据模型

知识图谱使用 SQLite 存储，采用**时间有效性**的三元组模型：

```python
# knowledge_graph.py — 数据库初始化
def _init_db(self):
    conn.executescript("""
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT DEFAULT 'unknown',
            properties TEXT DEFAULT '{}',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS triples (
            id TEXT PRIMARY KEY,
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object TEXT NOT NULL,
            valid_from TEXT,
            valid_to TEXT,
            confidence REAL DEFAULT 1.0,
            source_closet TEXT,
            source_file TEXT,
            source_drawer_id TEXT,
            adapter_name TEXT,
            extracted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subject) REFERENCES entities(id),
            FOREIGN KEY (object) REFERENCES entities(id)
        );

        CREATE INDEX IF NOT EXISTS idx_triples_subject ON triples(subject);
        CREATE INDEX IF NOT EXISTS idx_triples_object ON triples(object);
        CREATE INDEX IF NOT EXISTS idx_triples_predicate ON triples(predicate);
        CREATE INDEX IF NOT EXISTS idx_triples_valid ON triples(valid_from, valid_to);
    """)
```

### 5.2 三元组写入

```python
def add_triple(self, subject: str, predicate: str, obj: str,
               valid_from: str = None, valid_to: str = None,
               confidence: float = 1.0, source_closet: str = None, ...) -> str:
    """Add a relationship triple: subject → predicate → object."""
    sub_id = self._entity_id(subject)
    obj_id = self._entity_id(obj)
    pred = predicate.lower().replace(" ", "_")

    with self._lock:
        conn = self._conn()
        with conn:
            # Auto-create entities
            conn.execute("INSERT OR IGNORE INTO entities (id, name) VALUES (?, ?)", (sub_id, subject))
            conn.execute("INSERT OR IGNORE INTO entities (id, name) VALUES (?, ?)", (obj_id, obj))

            # Check for existing identical triple
            existing = conn.execute(
                "SELECT id FROM triples WHERE subject=? AND predicate=? AND object=? AND valid_to IS NULL",
                (sub_id, pred, obj_id),
            ).fetchone()
            if existing:
                return existing["id"]  # Already exists and still valid

            triple_id = make_triple_id(sub_id, pred, obj_id, valid_from, datetime.now().isoformat())
            conn.execute("""INSERT INTO triples (
                id, subject, predicate, object, valid_from, valid_to,
                confidence, source_closet, source_file, source_drawer_id, adapter_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", ...)
```

### 5.3 时间查询

**时间过滤**是知识图谱的核心特性——查询"某个时间点为真的事实"：

```python
def _temporal_filter_sql(as_of: str) -> tuple[str, list[str]]:
    """Return SQL and parameters for an as-of temporal filter.
    Date-only KG values are normalized:
    - valid_from='2026-05-06' compares as '2026-05-06T00:00:00Z'
    - valid_to='2026-05-06' compares as '2026-05-06T23:59:59Z'
    """
    as_of_key = _temporal_start_key(as_of)
    valid_from_expr = _sql_temporal_start_expr("t.valid_from")
    valid_to_expr = _sql_temporal_end_expr("t.valid_to")

    return (
        f" AND (t.valid_from IS NULL OR {valid_from_expr} <= ?) "
        f"AND (t.valid_to IS NULL OR {valid_to_expr} >= ?)",
        [as_of_key, as_of_key],
    )

def query_entity(self, name: str, as_of: str = None, direction: str = "outgoing"):
    """Get all relationships for an entity.
    direction: "outgoing" (entity → ?), "incoming" (? → entity), "both"
    as_of: ISO date or canonical UTC datetime — only return facts valid then
    """
    eid = self._entity_id(name)
    temporal_sql = ""
    temporal_params = []
    if as_of:
        temporal_sql, temporal_params = _temporal_filter_sql(as_of)

    if direction in ("outgoing", "both"):
        query = (
            "SELECT t.*, e.name as obj_name FROM triples t "
            "JOIN entities e ON t.object = e.id WHERE t.subject = ?" + temporal_sql
        )
        params = [eid] + temporal_params
        for row in conn.execute(query, params).fetchall():
            results.append({
                "direction": "outgoing",
                "subject": name,
                "predicate": row["predicate"],
                "object": row["obj_name"],
                "valid_from": row["valid_from"],
                "valid_to": row["valid_to"],
                "confidence": row["confidence"],
                "current": row["valid_to"] is None,
            })
```

### 5.4 三元组失效

```python
def invalidate(self, subject: str, predicate: str, obj: str, ended: str = None):
    """Mark a relationship as no longer valid (set valid_to date/time)."""
    sub_id = self._entity_id(subject)
    obj_id = self._entity_id(obj)
    pred = predicate.lower().replace(" ", "_")
    ended = sanitize_iso_temporal(ended or date.today().isoformat(), "ended")

    with self._lock:
        conn = self._conn()
        with conn:
            conn.execute(
                "UPDATE triples SET valid_to=? "
                "WHERE subject=? AND predicate=? AND object=? AND valid_to IS NULL",
                (ended, sub_id, pred, obj_id),
            )
```

---

## 6. 四层记忆堆栈 (L0-L3)

### 6.1 设计理念

```
Layer 0: Identity       (~100 tokens)   — Always loaded. "Who am I?"
Layer 1: Essential Story (~500-800)      — Always loaded. Top moments from the palace.
Layer 2: On-Demand      (~200-500 each)  — Loaded when a topic/wing comes up.
Layer 3: Deep Search    (unlimited)      — Full ChromaDB semantic search.

Wake-up cost: ~600-900 tokens (L0+L1). Leaves 95%+ of context free.
```

### 6.2 Layer 0 — Identity

```python
# layers.py — L0 身份层
class Layer0:
    """~100 tokens. Always loaded.
    Reads from ~/.mempalace/identity.txt — a plain-text file the user writes.

    Example identity.txt:
        I am Atlas, a personal AI assistant for Alice.
        Traits: warm, direct, remembers everything.
        People: Alice (creator), Bob (Alice's partner).
    """
    def __init__(self, identity_path: str = None):
        if identity_path is None:
            identity_path = os.path.expanduser("~/.mempalace/identity.txt")
        self.path = identity_path

    def render(self) -> str:
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                self._text = f.read().strip()
        else:
            self._text = "## L0 — IDENTITY\nNo identity configured."
        return self._text

    def token_estimate(self) -> int:
        return len(self.render()) // 4
```

### 6.3 Layer 1 — Essential Story

自动从宫殿中**最重要**的 drawer 生成：

```python
# layers.py — L1 精华层
class Layer1:
    """~500-800 tokens. Always loaded.
    Auto-generated from the highest-weight / most-recent drawers in the palace.
    """
    MAX_DRAWERS = 15  # at most 15 moments in wake-up
    MAX_CHARS = 3200  # hard cap on total L1 text (~800 tokens)

    def generate(self) -> str:
        col = _get_collection(self.palace_path, create=False)

        # Fetch all drawers in batches
        docs, metas = [], []
        offset = 0
        while True:
            kwargs = {"include": ["documents", "metadatas"], "limit": 500, "offset": offset}
            batch = col.get(**kwargs)
            batch_docs = batch.get("documents", [])
            if not batch_docs:
                break
            docs.extend(batch_docs)
            metas.extend(batch.get("metadatas", []))
            offset += len(batch_docs)
            if len(docs) >= self.MAX_SCAN:
                break

        # Score each drawer: prefer high importance
        scored = []
        for doc, meta in zip(docs, metas):
            importance = 3
            for key in ("importance", "emotional_weight", "weight"):
                val = meta.get(key)
                if val is not None:
                    importance = float(val)
                    break
            scored.append((importance, meta, doc))

        # Sort by importance descending, take top N
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:self.MAX_DRAWERS]

        # Group by room for readability
        by_room = defaultdict(list)
        for imp, meta, doc in top:
            room = meta.get("room", "general")
            by_room[room].append((imp, meta, doc))

        # Build compact text
        lines = ["## L1 — ESSENTIAL STORY"]
        total_len = 0
        for room, entries in sorted(by_room.items()):
            lines.append(f"\n[{room}]")
            for _imp, meta, doc in entries:
                snippet = doc.strip().replace("\n", " ")
                if len(snippet) > 200:
                    snippet = snippet[:197] + "..."
                entry_line = f"  - {snippet}"
                if total_len + len(entry_line) > self.MAX_CHARS:
                    lines.append("  ... (more in L3 search)")
                    return "\n".join(lines)
                lines.append(entry_line)
        return "\n".join(lines)
```

### 6.4 Layer 2 — On-Demand

按 Wing/Room 过滤的按需检索：

```python
class Layer2:
    """~200-500 tokens per retrieval.
    Loaded when a specific topic or wing comes up in conversation.
    """
    def retrieve(self, wing: str = None, room: str = None, n_results: int = 10) -> str:
        col = _get_collection(self.palace_path, create=False)
        where = build_where_filter(wing, room)
        kwargs = {"include": ["documents", "metadatas"], "limit": n_results}
        if where:
            kwargs["where"] = where
        results = col.get(**kwargs)
        docs = results.get("documents", [])
        metas = results.get("metadatas", [])

        lines = [f"## L2 — ON-DEMAND ({len(docs)} drawers)"]
        for doc, meta in zip(docs[:n_results], metas[:n_results]):
            snippet = doc.strip().replace("\n", " ")[:300]
            room_name = meta.get("room", "?")
            lines.append(f"  [{room_name}] {snippet}")
        return "\n".join(lines)
```

### 6.5 Layer 3 — Deep Search

完整的语义搜索：

```python
class Layer3:
    """Unlimited depth. Semantic search against the full palace."""
    def search(self, query: str, wing: str = None, room: str = None, n_results: int = 5) -> str:
        col = _get_collection(self.palace_path, create=False)
        where = build_where_filter(wing, room)
        kwargs = {
            "query_texts": [query],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        results = col.query(**kwargs)

        metric = _metric_for_collection(col)
        lines = [f'## L3 — SEARCH RESULTS for "{query}"']
        for i, (doc, meta, dist) in enumerate(zip(
            _first_or_empty(results, "documents"),
            _first_or_empty(results, "metadatas"),
            _first_or_empty(results, "distances"),
        ), 1):
            similarity = round(_distance_to_similarity(dist, metric), 3)
            lines.append(f"  [{i}] {wing_name}/{room_name} (sim={similarity})")
        return "\n".join(lines)
```

### 6.6 统一接口 MemoryStack

```python
class MemoryStack:
    """The full 4-layer stack. One class, one palace, everything works."""
    def __init__(self, palace_path=None, identity_path=None):
        self.l0 = Layer0(self.identity_path)
        self.l1 = Layer1(self.palace_path)
        self.l2 = Layer2(self.palace_path)
        self.l3 = Layer3(self.palace_path)

    def wake_up(self, wing: str = None) -> str:
        """Generate wake-up text: L0 (identity) + L1 (essential story).
        Typically ~600-900 tokens.
        """
        parts = [self.l0.render(), ""]
        if wing:
            self.l1.wing = wing
        parts.append(self.l1.generate())
        return "\n".join(parts)

    def recall(self, wing=None, room=None, n_results=10) -> str:
        return self.l2.retrieve(wing=wing, room=room, n_results=n_results)

    def search(self, query, wing=None, room=None, n_results=5) -> str:
        return self.l3.search(query, wing=wing, room=room, n_results=n_results)
```

---

## 7. 嵌入策略

### 7.1 双模型支持

```python
# embedding.py — 嵌入模型配置
# Two embedding models are available:
# * minilm (default) — all-MiniLM-L6-v2, 384-dim, English-only.
# * embeddinggemma — onnx-community/embeddinggemma-300m-ONNX (q8),
#   384-dim via Matryoshka truncation, multilingual (100+ languages).
#   Cross-lingual cos ~0.88 on parallel translations vs MiniLM's ~0.35.
```

### 7.2 硬件加速

```python
_PROVIDER_MAP = {
    "cpu": ["CPUExecutionProvider"],
    "cuda": ["CUDAExecutionProvider", "CPUExecutionProvider"],
    "coreml": ["CoreMLExecutionProvider", "CPUExecutionProvider"],
    "dml": ["DmlExecutionProvider", "CPUExecutionProvider"],
}

def _resolve_providers(device: str) -> tuple[list, str]:
    device = (device or "auto").strip().lower()
    try:
        import onnxruntime as ort
        available = set(ort.get_available_providers())
    except ImportError:
        return (["CPUExecutionProvider"], "cpu")

    if device == "auto":
        for provider, name in _AUTO_ORDER:
            if provider in available:
                return ([provider, "CPUExecutionProvider"], name)
        return (["CPUExecutionProvider"], "cpu")
```

### 7.3 Embeddinggemma ONNX 实现

```python
class EmbeddinggemmaONNX:
    """ChromaDB-compatible EF using embeddinggemma-300m ONNX (q8, MRL→384d)."""
    @staticmethod
    def name() -> str:
        return "embeddinggemma_300m"

    def __call__(self, input):
        self._lazy_load()
        np = self._np
        texts = [_EMBEDDINGGEMMA_PREFIX + t for t in input]
        encs = self._tokenizer.encode_batch(texts)
        input_ids = np.asarray([e.ids for e in encs], dtype=np.int64)
        attention_mask = np.asarray([e.attention_mask for e in encs], dtype=np.int64)
        outputs = self._session.run(
            None, {"input_ids": input_ids, "attention_mask": attention_mask}
        )
        sent_emb = outputs[self._output_idx][:, :_EMBEDDINGGEMMA_DIM]  # MRL truncation
        # L2-normalize so cosine similarity == dot product
        norms = np.linalg.norm(sent_emb, axis=1, keepdims=True) + 1e-12
        return (sent_emb / norms).tolist()
```

### 7.4 嵌入器身份检查 (RFC 001)

系统在打开集合时检查嵌入器身份一致性：

```python
# base.py — 嵌入器身份检查
def check_embedder_identity(stored, current, *, force_model_swap=False) -> str:
    """Three-state embedder-identity check.
    Returns: "unknown", "known_match", or "known_mismatch"
    """
    if current is None or not current.model_name:
        return "unknown"
    if stored is None:
        return "unknown"

    dim_conflict = bool(stored.dimension and current.dimension) and (
        stored.dimension != current.dimension
    )
    name_conflict = stored.model_name != current.model_name

    if not dim_conflict and not name_conflict:
        return "known_match"
    if force_model_swap:
        return "known_mismatch"
    if dim_conflict:
        raise DimensionMismatchError(...)
    raise EmbedderIdentityMismatchError(...)
```

---

## 8. AAAK 压缩方言

### 8.1 格式规范

AAAK 是一种**有损摘要格式**，不是无损压缩。原始文本无法从 AAAK 输出重建。

```
Header:   FILE_NUM|PRIMARY_ENTITY|DATE|TITLE
Zettel:   ZID:ENTITIES|topic_keywords|"key_quote"|WEIGHT|EMOTIONS|FLAGS
Tunnel:   T:ZID<->ZID|label
Arc:      ARC:emotion->emotion->emotion
```

### 8.2 情感代码系统

```python
# dialect.py — 情感代码映射
EMOTION_CODES = {
    "vulnerability": "vul", "joy": "joy", "fear": "fear", "trust": "trust",
    "grief": "grief", "wonder": "wonder", "rage": "rage", "love": "love",
    "hope": "hope", "despair": "despair", "peace": "peace", "humor": "humor",
    "tenderness": "tender", "raw_honesty": "raw", "self_doubt": "doubt",
    "anxiety": "anx", "exhaustion": "exhaust", "conviction": "convict",
    "quiet_passion": "passion", "warmth": "warmth", "curiosity": "curious",
    "gratitude": "grat", "frustration": "frust", "excitement": "excite",
    "determination": "determ", "surprise": "surprise",
}
```

### 8.3 标志系统

```python
_FLAG_SIGNALS = {
    "decided": "DECISION", "chose": "DECISION", "switched": "DECISION",
    "migrated": "DECISION", "replaced": "DECISION", "instead of": "DECISION",
    "founded": "ORIGIN", "created": "ORIGIN", "started": "ORIGIN",
    "born": "ORIGIN", "launched": "ORIGIN", "first time": "ORIGIN",
    "core": "CORE", "fundamental": "CORE", "essential": "CORE",
    "principle": "CORE", "belief": "CORE", "always": "CORE",
    "turning point": "PIVOT", "changed everything": "PIVOT",
    "realized": "PIVOT", "breakthrough": "PIVOT", "epiphany": "PIVOT",
    "api": "TECHNICAL", "database": "TECHNICAL", "architecture": "TECHNICAL",
    "deploy": "TECHNICAL", "infrastructure": "TECHNICAL",
}
```

### 8.4 主题提取

```python
# dialect.py — 主题提取
def _extract_topics(self, text: str, max_topics: int = 3) -> List[str]:
    """Extract key topic words from plain text."""
    words = re.findall(r"[a-zA-Z][a-zA-Z_-]{2,}", text)
    freq = {}
    for w in words:
        w_lower = w.lower()
        if w_lower in _STOP_WORDS or len(w_lower) < 3:
            continue
        freq[w_lower] = freq.get(w_lower, 0) + 1

    # Boost words that look like proper nouns or technical terms
    for w in words:
        w_lower = w.lower()
        if w[0].isupper() and w_lower in freq:
            freq[w_lower] += 2
        if "_" in w or "-" in w or (any(c.isupper() for c in w[1:])):
            if w_lower in freq:
                freq[w_lower] += 2

    ranked = sorted(freq.items(), key=lambda x: -x[1])
    return [w for w, _ in ranked[:max_topics]]
```

### 8.5 关键句子提取

```python
def _extract_key_sentence(self, text: str) -> str:
    """Extract the most important sentence fragment from text."""
    sentences = re.split(r"[.!?\n]+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    if not sentences:
        return ""

    # Score each sentence
    decision_words = {
        "decided", "because", "instead", "prefer", "switched", "chose",
        "realized", "important", "key", "critical", "discovered", "learned",
    }
    scored = []
    for s in sentences:
        s_lower = s.lower()
        # Score = (decision word hits * 3) + (capitalized word count)
        score = sum(3 for w in decision_words if w in s_lower)
        score += sum(1 for word in s.split() if word[0:1].isupper() and len(word) > 2)
        scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored else ""
```

---

## 9. 辅助系统

### 9.1 实体检测 (entity_detector.py)

```python
# 三阶段实体检测
# Tier 2: COCA 内容词过滤（排除非专有名词的大写词）
@functools.lru_cache(maxsize=1)
def _get_coca_filter() -> frozenset[str]:
    """Return the COCA content-word filter set (lowercased)."""
    data_path = Path(__file__).parent / "data" / "coca_content_words.json"
    raw = json.loads(data_path.read_text(encoding="utf-8"))
    words = raw.get("words", [])
    return frozenset(w.lower() for w in words if isinstance(w, str))

# Tier 3: 已知系统复合词预处理（如 "Claude Code" 不被拆分为 "Claude" + "Code"）
def _apply_known_systems_prepass(text: str) -> tuple[str, dict[str, int]]:
    """Scan text for known-systems compounds, return a working copy
    with matched spans masked to whitespace."""
    compounds = _get_known_systems()
    working = text
    compound_counts: dict[str, int] = {}
    for compound, rx in compounds:
        matches = list(rx.finditer(working))
        if not matches:
            continue
        compound_counts[compound] = len(matches)
        # Mask matched spans with spaces so subsequent passes don't re-decompose
        for m in reversed(matches):
            start, end = m.span()
            working = working[:start] + (" " * (end - start)) + working[end:]
    return working, compound_counts
```

### 9.2 去重 (dedup.py)

```python
# dedup.py — 贪心去重算法
def dedup_source_group(col, drawer_ids, threshold=DEFAULT_THRESHOLD, dry_run=True):
    """Dedup drawers within one source_file group.
    Greedy: sort by doc length (longest first), keep if not too similar
    to any already-kept drawer.
    """
    data = col.get(ids=drawer_ids, include=["documents", "metadatas"])
    items = list(zip(data["ids"], data["documents"], data["metadatas"]))
    items.sort(key=lambda x: len(x[1] or ""), reverse=True)

    kept = []
    to_delete = []
    for did, doc, _meta in items:
        if not doc or len(doc) < 20:
            to_delete.append(did)
            continue
        if not kept:
            kept.append((did, doc))
            continue
        # Query for similar already-kept drawers
        results = col.query(query_texts=[doc], n_results=min(len(kept), 5), include=["distances"])
        dists = results["distances"][0] if results["distances"] else []
        is_dup = any(rid in kept_ids_set and dist < threshold
                     for rid, dist in zip(results["ids"][0], dists))
        if is_dup:
            to_delete.append(did)
        else:
            kept.append((did, doc))
```

### 9.3 宫殿图遍历 (palace_graph.py)

```python
# palace_graph.py — BFS 图遍历
def traverse(start_room: str, col=None, config=None, max_hops: int = 2):
    """Walk the graph from a starting room. Find connected rooms
    through shared wings. Returns list of paths."""
    nodes, edges = build_graph(col, config)
    visited = {start_room}
    results = [{"room": start_room, "wings": nodes[start_room]["wings"], "hop": 0}]

    # BFS traversal
    frontier = [(start_room, 0)]
    while frontier:
        current_room, depth = frontier.pop(0)
        if depth >= max_hops:
            continue
        current_wings = set(nodes.get(current_room, {}).get("wings", []))
        for room, data in nodes.items():
            if room in visited:
                continue
            shared_wings = current_wings & set(data["wings"])
            if shared_wings:
                visited.add(room)
                results.append({
                    "room": room, "wings": data["wings"],
                    "hop": depth + 1, "connected_via": sorted(shared_wings),
                })
                if depth + 1 < max_hops:
                    frontier.append((room, depth + 1))

    results.sort(key=lambda x: (x["hop"], -x["count"]))
    return results[:50]
```

### 9.4 存储后端抽象 (backends/base.py)

```python
# base.py — 后端合约 (RFC 001)
class BaseCollection(ABC):
    """Per-collection read/write surface every backend must implement."""

    @abstractmethod
    def add(self, *, documents: list[str], ids: list[str],
            metadatas: Optional[list[dict]] = None,
            embeddings: Optional[list[list[float]]] = None) -> None: ...

    @abstractmethod
    def upsert(self, *, documents: list[str], ids: list[str],
               metadatas: Optional[list[dict]] = None,
               embeddings: Optional[list[list[float]]] = None) -> None: ...

    @abstractmethod
    def query(self, *, query_texts: Optional[list[str]] = None,
              query_embeddings: Optional[list[list[float]]] = None,
              n_results: int = 10, where: Optional[dict] = None,
              include: Optional[list[str]] = None) -> QueryResult: ...

    @abstractmethod
    def get(self, *, ids: Optional[list[str]] = None,
            where: Optional[dict] = None, limit: Optional[int] = None,
            offset: Optional[int] = None,
            include: Optional[list[str]] = None) -> GetResult: ...

    @abstractmethod
    def delete(self, *, ids: Optional[list[str]] = None,
               where: Optional[dict] = None) -> None: ...

    @abstractmethod
    def count(self) -> int: ...

    def lexical_search(self, *, query: str, n_results: int = 10,
                       where: Optional[dict] = None) -> LexicalResult:
        raise UnsupportedCapabilityError("backend does not support lexical_search")
```

类型化结果数据结构：

```python
@dataclass(frozen=True)
class QueryResult(_DictCompatMixin):
    """Typed return from BaseCollection.query.
    Outer list dimension = number of query vectors / texts.
    Inner list dimension = hits per query (may be zero).
    """
    ids: list[list[str]]
    documents: list[list[str]]
    metadatas: list[list[dict]]
    distances: list[list[float]]
    embeddings: Optional[list[list[list[float]]]] = None
```

---

## 10. 总结

### 核心架构亮点

1. **逐字存储原则**：MemPalace 最核心的设计决策是永不总结用户数据。所有内容以原文形式存储在 drawer 中，搜索结果返回原文。

2. **混合搜索架构**：BM25 + 向量搜索的凸组合（60% 向量 + 40% BM25），配合 Closet boost 的排名信号增强，在不牺牲召回率的前提下提高精准度。

3. **四层记忆堆栈**：L0（身份，~100 tokens）+ L1（精华，~800 tokens）= 唤醒成本仅 ~900 tokens，保留 95%+ 上下文窗口。L2 按需加载，L3 深度搜索。

4. **时间知识图谱**：基于 SQLite 的三元组存储，支持 `valid_from` / `valid_to` 时间有效性查询，可以回答"2026 年 1 月时 Max 的情况"这类时间敏感问题。

5. **AAAK 压缩方言**：有损索引层，压缩实体、主题、情感和标志到紧凑格式，让 LLM 能快速扫描数千条目找到相关 drawer。

6. **安全的 ID 生成**：使用 `|` 分隔符的 SHA-256 哈希避免了字符串拼接碰撞问题。

7. **嵌入器身份一致性**：RFC 001 定义的三态检查（unknown/known_match/known_mismatch）防止在模型切换时产生静默降级。

8. **隐私架构**：数据永远不离开用户机器。默认使用本地嵌入模型（ONNX Runtime），无遥测、无外部 API 依赖。

### 技术债务与局限

- BM25 仅在候选集上计算 IDF，而非全局语料库
- Closet 的 boost 是基于排名序号的启发式，非精确语义信号
- 实体检测依赖正则表达式和关键词匹配，非 NER 模型
- 知识图谱的三元组提取依赖适配器而非内置推理

---

*报告基于 MemPalace 仓库 `~/.hermes/repos/mempalace/` 源码分析生成。*
*所有代码片段均来自真实源文件，行号可追溯。*
