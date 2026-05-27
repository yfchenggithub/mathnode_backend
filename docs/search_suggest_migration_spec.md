# Search / Suggest 迁移规格（基于当前实现）

## 0. 结论先行
- 当前项目里，`search/suggest` 的**唯一在线检索数据源**是 `backend_search_index.json` 加载后的 `MemoryIndexStore`；`canonical_content_v2.json` 不参与这两个接口的召回和打分，仅用于结论详情内容读取。  
  证据：`app/core/lifespan.py:69-80`, `app/api/dependencies.py:29-35`, `app/api/v1/search.py:52-61`, `app/api/v1/suggest.py:27`, `app/api/v1/conclusions.py:24-25,38-43`, `app/services/conclusion_service.py:59`, `app/stores/memory_content_store.py:83-87`
- `search` 是“过滤 + 分页”，**没有相关性打分和重排**；`suggest` 会计算 `score`，但当前实现也**不会按 score 重排**，只取过滤结果前 8 条。  
  证据：`app/stores/memory_index_store.py:36,76-109,111-183,209-314`

---

## 1. 调用链梳理（从 JSON 到 API 返回）

### 1.1 启动装配链
- 配置默认路径：`CONTENT_JSON_PATH=app/data/canonical_content_v2.json`，`INDEX_JSON_PATH=app/data/backend_search_index.json`。  
  证据：`app/core/config.py:103-117`
- 启动时解析路径并加载两个 JSON：`load_content(...)` 与 `load_index_records(...)`。  
  证据：`app/core/lifespan.py:49-50,69,76`
- 分别实例化并挂载到 `app.state`：`content_store`、`index_store`。  
  证据：`app/core/lifespan.py:70-80,126-128`
- API 依赖注入通过 `get_index_store` 取 `app.state.index_store`。  
  证据：`app/api/dependencies.py:29-35`

### 1.2 `/search` 请求链
- 路由参数接收后调用 `SearchService.search(...)`。  
  证据：`app/api/v1/search.py:20-31,52-61`
- 服务层直接委托 `index_store.search(...)`。  
  证据：`app/services/search_service.py:49-57`
- 返回统一响应包裹 `{code,message,data}`。  
  证据：`app/api/v1/search.py:80`, `app/core/response.py:9-14`

### 1.3 `/suggest` 请求链
- 路由参数接收后调用 `SearchService.suggest(...)`。  
  证据：`app/api/v1/suggest.py:16-20,27`
- 服务层直接委托 `index_store.suggest(...)`。  
  证据：`app/services/search_service.py:102`
- 返回统一响应包裹 `{code,message,data}`。  
  证据：`app/api/v1/suggest.py:35`, `app/core/response.py:9-14`

---

## 2. 两个 JSON 的数据模型与字段映射

## 2.1 `canonical_content_v2.json`（内容库）
- Loader 目标：把 canonical 结构化内容转换为 `ContentDocument`，并保留 `raw_records_by_id`。  
  证据：`app/loaders/content_loader.py:30-37,412-459,470-507`
- 关键输出字段：`id,title,module,difficulty,tags,statement_clean,statement,explanation,proof,examples,traps,summary,pdf_url`。  
  证据：`app/stores/interfaces.py:13-27`, `app/loaders/content_loader.py:445-459`
- `statement_clean` 生成优先级：`statement -> primary_formula -> title`。  
  证据：`app/loaders/content_loader.py:401-409,431-443`
- 该数据进入 `MemoryContentStore`，用于结论详情查询（`get_raw_by_id`），不进入搜索索引计算。  
  证据：`app/core/lifespan.py:69-74`, `app/stores/memory_content_store.py:27-35,83-87`, `app/services/conclusion_service.py:59`

## 2.2 `backend_search_index.json`（检索索引）
- Loader 只强依赖顶层 `docs` 节点并做结构校验。  
  证据：`app/loaders/index_loader.py:139-160,232-233`
- `docs` 每条转换为记录字段（含默认值）：
  - `id`: `doc.id`，为空时回退 `doc_key`
  - `title`: `doc.title`（字符串）
  - `module`: `doc.module`（字符串）
  - `difficulty`: `_safe_int(..., default=1)`
  - `tags`: `_safe_tags(...)`（支持字符串按 `[，,;；|]` 切分）
  - `module_dir`: `doc.moduleDir`（字符串）
  - `summary`: `doc.summary`（字符串）
  - `statement_clean`: 当前实现等于 `summary or ""`
  - `category`: `doc.category`（字符串）
  - `core_formula`: `doc.coreFormula`（字符串）
  - `rank`: `_safe_int(..., default=0)`
  - `search_boost`: `_safe_float(..., default=0.0)`
  - `hot_score`: `_safe_float(..., default=0.0)`
  - `exam_frequency`: `_safe_float(..., default=0.0)`
  - `exam_score`: `_safe_float(..., default=0.0)`
  - `doc_payload`: 原始 doc 深拷贝（若无 id 会补齐）
  
  证据：`app/loaders/index_loader.py:36-91,183-213`
- `missing_key_field_count` 统计口径：`raw_id/title/module/statement_clean` 为空即计缺失。  
  证据：`app/loaders/index_loader.py:163-176,215-221`
- 加载结果 source 固定为 `"backend_search_index:file"`。  
  证据：`app/loaders/index_loader.py:242-246`

## 2.3 运行期 `MemoryIndexStore` 真正使用的字段
- 规范化后仅保留并索引：`id,title,module,difficulty,tags,tags_text,statement_clean,doc_payload`，再派生小写缓存字段用于匹配。  
  证据：`app/stores/memory_index_store.py:40-54`
- 初始化时对输入记录按 `id` 升序排序，后续过滤保持该顺序。  
  证据：`app/stores/memory_index_store.py:36,87-109`

---

## 3. Search 核心算法（当前真实实现）

## 3.1 查询预处理
- `q` 在过滤时执行 `strip().lower()`；`tag` 执行 `(tag or "").strip().lower()`。  
  证据：`app/stores/memory_index_store.py:83-84`
- `module` 不做大小写归一化，按原值精确比较。  
  证据：`app/stores/memory_index_store.py:88-89`

## 3.2 召回与过滤规则
- 过滤顺序（短路）：
  1. `module` 精确匹配  
  2. `difficulty` 精确匹配  
  3. `tag` 子串匹配（在 `tags_text_lower` 上）  
  4. `q` 非空时，在 `title/module/statement_clean/tags_text` 四字段做 contains 任一命中
  
  证据：`app/stores/memory_index_store.py:87-107`
- `q` 为空时，不做关键词过滤（即保留通过 facet 过滤的全部记录）。  
  证据：`app/stores/memory_index_store.py:97-105`

## 3.3 评分、排序、分页
- **无 search 评分公式**；排序来自初始化的 `id` 升序稳定顺序。  
  证据：`app/stores/memory_index_store.py:36,123-129,144-147`
- 分页：`start=(page-1)*page_size`，`end=start+page_size`。  
  证据：`app/stores/memory_index_store.py:144-146`
- `total = len(matched_rows)`（分页前总量）。  
  证据：`app/stores/memory_index_store.py:129,165`

## 3.4 返回结构与 facets
- `items`：每项来自 `doc_payload` 深拷贝，并附加 `is_favorited`。  
  证据：`app/stores/memory_index_store.py:149-152`
- facets 使用 `Counter` 统计 `module/difficulty/tags`，输出 `[{value,count}]`。  
  证据：`app/stores/memory_index_store.py:154-181`
- `query` 原样返回传入 `q`（不是 trim 后字符串）。  
  证据：`app/stores/memory_index_store.py:164`, `app/services/search_service.py:49-51`

## 3.5 空查询 / 无结果 / 异常
- 空查询可返回全量分页结果（受 facet 过滤约束）。  
  证据：`app/stores/memory_index_store.py:97-105,144-147`
- 无结果时 `total=0, items=[]`，facets 为空列表。  
  证据：`app/stores/memory_index_store.py:129,154-183`
- 异常由 `SearchService` 记录日志后继续抛出。  
  证据：`app/services/search_service.py:48-73`

---

## 4. Suggest 核心算法（当前真实实现）

## 4.1 召回来源
- `suggest` 调用同一套 `_filter_records`，仅传 `module/difficulty/tag=None`，只按 `q` 四字段 contains 召回。  
  证据：`app/stores/memory_index_store.py:287-292,97-103`

## 4.2 匹配类型与基础分
- 默认：`match_type=contains`, `match_field=statement_clean`, `base_score=0.70`。  
  证据：`app/stores/memory_index_store.py:211-213`
- 规则按优先级命中：
  - `title == q` -> `exact/title/1.00`
  - `title.startswith(q)` -> `prefix/title/0.95`
  - `q in title` -> `contains/title/0.90`
  - `q in tags` -> `contains/tags/0.82`
  - `q in module` -> `contains/module/0.78`
  - `q in statement_clean` -> `contains/statement_clean/0.74`
  
  证据：`app/stores/memory_index_store.py:215-238`

## 4.3 权重项与总分公式
- 取值与裁剪：
  - `searchBoost` -> `[0,1]`
  - `hotScore` -> `[0,100]`
  - `examFrequency` -> `[0,1]`
  
  证据：`app/stores/memory_index_store.py:241-243,195-200`
- 公式：
  - `score = base_score + search_boost*0.03 + (hot_score/100)*0.03 + exam_frequency*0.02`
  - 最终 `clamp[0,1]` 后 `round(3)`
  
  证据：`app/stores/memory_index_store.py:245-249`

## 4.4 badge 规则
- `hot_score >= 85` 或 `exam_frequency >= 1.0` -> `高频`
- 否则若 `search_boost >= 0.9` 或 `hot_score >= 70` -> `常用`
- 否则若 `difficulty >= 4` -> `进阶`
- 否则空字符串
  
  证据：`app/stores/memory_index_store.py:251-257`

## 4.5 排序、截断、无结果策略
- 先按 `_records`（即 `id` 升序）过滤，再直接 `rows[:8]` 截断；**不按 score 排序**。  
  证据：`app/stores/memory_index_store.py:36,287-301`
- 空查询：返回 `query=""`, `total=0`, `items=[]`, `empty_hint="请输入关键词"`。  
  证据：`app/stores/memory_index_store.py:278-285`
- 非空但无匹配：`empty_hint="没有匹配结果，换个关键词试试"`。  
  证据：`app/stores/memory_index_store.py:309-313`

---

## 5. 可迁移规格（给另一个系统直接实现）

## 5.1 参数表

### Search 参数
| 参数 | 类型 | 默认值 | 约束 | 说明 | 证据 |
|---|---|---|---|---|---|
| `q` | `str` | `""` | 无 | 关键词，过滤时 `trim+lower` | `app/api/v1/search.py:22`, `app/stores/memory_index_store.py:83` |
| `module` | `str\|None` | `None` | 无 | 精确匹配，大小写敏感 | `app/api/v1/search.py:23`, `app/stores/memory_index_store.py:88` |
| `difficulty` | `int\|None` | `None` | 路由层无范围校验 | 精确匹配 | `app/api/v1/search.py:24`, `app/stores/memory_index_store.py:91` |
| `tag` | `str\|None` | `None` | 无 | 在 `tags_text_lower` 上做子串匹配 | `app/api/v1/search.py:25`, `app/stores/memory_index_store.py:84,94` |
| `page` | `int` | `1` | `>=1` | 分页页码 | `app/api/v1/search.py:26` |
| `page_size` | `int` | `10` | `1~50` | 分页大小 | `app/api/v1/search.py:27` |
| `favorite_ids` | `set[str]\|None` | `None` | 内部参数 | 标记 `is_favorited` | `app/services/search_service.py:25,49-57`, `app/stores/memory_index_store.py:121,151` |

### Suggest 参数
| 参数 | 类型 | 默认值 | 约束 | 说明 | 证据 |
|---|---|---|---|---|---|
| `q` | `str` | `""` | 无 | 空值直接返回提示 | `app/api/v1/suggest.py:18`, `app/stores/memory_index_store.py:278-285` |
| `limit` | 固定常量 | `8` | 不可配置 | 过滤后取前 8 条 | `app/stores/memory_index_store.py:298-301,306` |

## 5.2 权重表（Suggest）
| 项 | 数值/区间 | 作用 | 证据 |
|---|---|---|---|
| `base_score(title exact)` | `1.00` | 精确标题匹配基础分 | `app/stores/memory_index_store.py:215-218` |
| `base_score(title prefix)` | `0.95` | 标题前缀匹配基础分 | `app/stores/memory_index_store.py:219-222` |
| `base_score(title contains)` | `0.90` | 标题包含匹配基础分 | `app/stores/memory_index_store.py:223-226` |
| `base_score(tags contains)` | `0.82` | 标签包含匹配基础分 | `app/stores/memory_index_store.py:227-230` |
| `base_score(module contains)` | `0.78` | 模块包含匹配基础分 | `app/stores/memory_index_store.py:231-234` |
| `base_score(statement contains)` | `0.74` | 陈述包含匹配基础分 | `app/stores/memory_index_store.py:235-238` |
| `base_score(default)` | `0.70` | 兜底基础分 | `app/stores/memory_index_store.py:211-213` |
| `search_boost` 增益 | `+ search_boost * 0.03` | 热度微调 | `app/stores/memory_index_store.py:241,246` |
| `hot_score` 增益 | `+ (hot_score/100) * 0.03` | 热度微调 | `app/stores/memory_index_store.py:242,247` |
| `exam_frequency` 增益 | `+ exam_frequency * 0.02` | 高频微调 | `app/stores/memory_index_store.py:243,248` |
| 最终分 | `clamp(0,1)` + `round(3)` | 输出 score | `app/stores/memory_index_store.py:249` |

## 5.3 伪代码

### Search
```python
def search(q, module, difficulty, tag, page, page_size, favorite_ids):
    # records 已按 id 升序初始化
    rows = []
    keyword = q.strip().lower()
    tag_kw = (tag or "").strip().lower()

    for row in records:
        if module and row.module != module:
            continue
        if difficulty is not None and row.difficulty != difficulty:
            continue
        if tag_kw and tag_kw not in row.tags_text_lower:
            continue
        if keyword:
            hit = (
                keyword in row.title_lower
                or keyword in row.module_lower
                or keyword in row.statement_clean_lower
                or keyword in row.tags_text_lower
            )
            if not hit:
                continue
        rows.append(row)

    total = len(rows)
    page_rows = rows[(page - 1) * page_size : (page - 1) * page_size + page_size]
    items = [deepcopy(r.doc_payload) + {"is_favorited": (r.id in favorite_ids)} for r in page_rows]
    facets = counter_module_difficulty_tags(rows)
    return {"query": q, "total": total, "page": page, "page_size": page_size, "items": items, "facets": facets}
```
证据：`app/stores/memory_index_store.py:36,83-107,121-183`

### Suggest
```python
def suggest(q):
    keyword = q.strip()
    if not keyword:
        return {"query": "", "total": 0, "empty_hint": "请输入关键词", "items": []}

    rows = filter_records(keyword, module=None, difficulty=None, tag=None)  # 保持 id 升序
    items = []
    for row in rows[:8]:  # 注意：不按 score 排序
        base = resolve_base_score_by_match_field(row, keyword)
        search_boost = clamp(float(row.doc_payload.get("searchBoost", 0.0)), 0.0, 1.0)
        hot_score = clamp(float(row.doc_payload.get("hotScore", 0.0)), 0.0, 100.0)
        exam_frequency = clamp(float(row.doc_payload.get("examFrequency", 0.0)), 0.0, 1.0)
        score = round(clamp(base + search_boost * 0.03 + (hot_score / 100.0) * 0.03 + exam_frequency * 0.02, 0.0, 1.0), 3)
        badge = resolve_badge(hot_score, exam_frequency, search_boost, row.difficulty)
        items.append(build_suggest_item(..., score=score, badge=badge))

    return {
        "query": keyword,
        "total": len(rows),
        "empty_hint": "" if items else "没有匹配结果，换个关键词试试",
        "items": items,
    }
```
证据：`app/stores/memory_index_store.py:209-314`

## 5.4 一致性测试清单（至少 10 条）
1. `q=""`、无其他过滤时，`search.total == 索引总条数`，并按 `id` 升序分页。证据：`app/stores/memory_index_store.py:36,97-107,144-147`
2. `module` 过滤为精确匹配且区分大小写。证据：`app/stores/memory_index_store.py:88`
3. `difficulty` 为精确整数匹配。证据：`app/stores/memory_index_store.py:91`
4. `tag` 为 `tags_text_lower` 子串匹配（非 token 精确匹配）。证据：`app/stores/memory_index_store.py:84,94`
5. `search` 返回项应等于 `docs[id]` + `is_favorited`。证据：`tests/test_search_api.py:64-67`
6. `suggest` 返回字段完整：`id/title/subtitle/route/module/difficulty/tags/match_type/match_field/matched_text/score/badge`。证据：`tests/test_suggest_api.py:51-63`
7. `suggest` 结果最多 8 条。证据：`tests/test_suggest_api.py:48`, `app/stores/memory_index_store.py:300`
8. `suggest` 空查询返回 `请输入关键词`。证据：`tests/test_suggest_api.py:69-81`, `app/stores/memory_index_store.py:279-284`
9. `suggest` 无匹配返回 `没有匹配结果，换个关键词试试`。证据：`tests/test_suggest_api.py:83-96`, `app/stores/memory_index_store.py:312`
10. `suggest` 的 score 公式与 clamp/round 精确一致（保留三位小数）。证据：`app/stores/memory_index_store.py:241-249`
11. `suggest` 不按 score 排序，只按过滤后顺序截断前 8。证据：`app/stores/memory_index_store.py:36,287-301`
12. `search.query` 回传原始 `q`，`suggest.query` 回传 `trim` 后 `keyword`。证据：`app/stores/memory_index_store.py:164,278,310`

---

## 6. 迁移时最容易踩坑的 5 个点
1. 误以为 `canonical_content_v2.json` 参与 search/suggest：当前没有，search/suggest 只走 index store。  
   证据：`app/api/v1/search.py:52-61`, `app/api/v1/suggest.py:27`, `app/api/v1/conclusions.py:24-25,38-43`
2. 误以为 `search` 有相关性排序：当前是过滤后按 `id` 升序稳定输出。  
   证据：`app/stores/memory_index_store.py:36,123-147`
3. 误以为 `suggest` 会按 `score` 排序：当前仅计算分数展示，不参与排序。  
   证据：`app/stores/memory_index_store.py:245-249,298-301`
4. 忽略 `tag` 的“子串匹配”语义：会导致与 token 精确匹配系统结果不一致。  
   证据：`app/stores/memory_index_store.py:94`
5. 忽略 `statement_clean` 的来源差异：content loader 与 index loader 对 `statement_clean` 定义不同（前者由 statement/formula/title 推导，后者直接用 summary）。  
   证据：`app/loaders/content_loader.py:401-443`, `app/loaders/index_loader.py:187-189,204`

---

## 7. 已执行校验
- 已运行：`python -m unittest tests.test_search_api tests.test_suggest_api`，4 个用例全部通过。  
  证据：本次本地执行结果（`Ran 4 tests ... OK`）

