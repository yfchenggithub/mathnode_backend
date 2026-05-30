# 收藏讲义 API 契约（阶段 2）

## 1. 功能边界

“收藏讲义”只做一件事：
按“我的收藏”默认顺序，把服务器**已提前构建**的单条结论 PDF 合并为一份可下载讲义。

本功能不会：
- 根据详情正文重新排版生成 PDF
- 读取 `canonical_content_v2.json` 重建正文
- 重新渲染 LaTeX / 公式图
- 接收前端上传 `pdf_url` / `pdf_path`

阶段 2 在合并基础上新增：
- 讲义第一页开始生成“收藏讲义 + 基本信息 + 目录”
- 目录支持多页，并写入每条内容在最终讲义中的起始页码
- 最终讲义统一页脚页码（若检测到正文遮挡风险则自动跳过页脚，正文仍保持原样）
- 对外文件名升级为 `收藏讲义_YYYYMMDD_N条.pdf`

## 2. 鉴权与安全

- 三个接口都必须登录（Bearer Token / X-Token，复用现有依赖）
- `handout_id` 不是授权凭证，查询和下载都必须校验 `current_user`
- 非本人资源统一返回 `404 HANDOUT_NOT_FOUND`
- 不向客户端暴露服务器绝对路径、源 PDF 物理路径、字体路径

## 3. 源 PDF 解析规则

- 只从当前用户收藏快照中读取 `conclusion_id`
- 通过 `pdf_mapping_store + PdfService.resolve_conclusion_pdf_file(...)` 做服务端可信映射
- 必须校验文件存在且路径在受控根目录内（防 path traversal）
- 任意一条源 PDF 缺失，整次生成失败（不静默跳过）

## 4. 同步生成流程

1. 读取当前用户收藏（固定快照）
2. 按默认顺序解析全部源 PDF，并读取页数
3. 生成目录 PDF，迭代计算直到目录页数稳定
4. 合并顺序：目录页 + 源 PDF（原样）
5. 对最终副本叠加统一页脚页码（如无遮挡风险）
6. 原子写入最终文件并做输出校验
7. 持久化讲义元数据（用户归属、快照、过期时间等）
8. 返回 `status=ready` 与受鉴权保护的 `pdf_url`

当前阶段为同步 MVP：成功直接 `ready`，未引入异步队列与轮询。

## 5. 接口契约

### 5.1 POST `/api/v1/favorites/handouts`

- 用途：生成收藏讲义
- 请求体：可空或 `{}`
- 前端禁止传入：`user_id`、`conclusion_ids`、`favorite_ids`、`pdf_urls`、`pdf_paths`、正文内容等

成功：`201 Created`

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "handout_id": "fh_xxx",
    "title": "收藏讲义",
    "status": "ready",
    "item_count": 24,
    "filename": "收藏讲义_20260530_24条.pdf",
    "pdf_url": "/api/v1/favorites/handouts/fh_xxx/pdf",
    "created_at": "2026-05-30T10:30:00+08:00",
    "expires_at": "2026-06-06T10:30:00+08:00",
    "error": null
  }
}
```

常见失败：
- `409 NO_FAVORITES`
- `409 HANDOUT_SOURCE_PDF_MISSING`（可附 `missing_items`）
- `500 HANDOUT_FONT_UNAVAILABLE`
- `500 HANDOUT_TOC_GENERATION_FAILED`
- `500 HANDOUT_PAGE_NUMBERING_FAILED`
- `500 HANDOUT_OUTPUT_INVALID`
- `500 HANDOUT_MERGE_FAILED`

### 5.2 GET `/api/v1/favorites/handouts/{handout_id}`

- 用途：查询讲义元信息
- 成功：`200 OK`
- 过期：返回元信息且 `status=expired`
- 不存在或无权限：`404 HANDOUT_NOT_FOUND`

### 5.3 GET `/api/v1/favorites/handouts/{handout_id}/pdf`

- 用途：下载 / 预览最终讲义 PDF
- 成功：`200 OK`
  - `Content-Type: application/pdf`
  - `Content-Disposition: inline; filename*=UTF-8''...`
- 不存在或无权限：`404 HANDOUT_NOT_FOUND`
- 已过期：`410 HANDOUT_EXPIRED`
- 元数据存在但文件不存在：`500 HANDOUT_FILE_MISSING`

## 6. 顺序与快照

- 合并顺序严格复用当前收藏默认顺序（当前实现：`conclusion_id ASC, favorite.id ASC`）
- 生成时固定一次快照，后续收藏变更不影响已生成讲义
- 元数据保存 `snapshot_conclusion_ids_json`

## 7. 存储与过期

- 源 PDF 根目录：`PDF_ROOT_DIR`
- 讲义输出目录：`HANDOUT_OUTPUT_DIR`
- 讲义默认过期：`HANDOUT_EXPIRE_DAYS`（默认 7 天）
- 下载时强制检查过期状态

## 8. 阶段 2 新增配置

- `HANDOUT_CJK_FONT_PATH`：中文字体路径（可选，建议显式配置）
- `HANDOUT_CJK_FONT_NAME`：保留字段（兼容字体命名配置）
- `HANDOUT_FOOTER_ENABLED`：是否启用统一页脚（默认 `true`）
- `HANDOUT_FOOTER_Y_MM`：页脚纵向位置
- `HANDOUT_FOOTER_FONT_SIZE`：页脚字号
- `HANDOUT_TOC_MAX_ITERATIONS`：目录分页稳定计算最大迭代次数（默认 `3`）

## 9. 小程序接入流程（不变）

用户点击“生成收藏讲义”
→ `POST /api/v1/favorites/handouts`
→ 返回 `ready + pdf_url`
→ `wx.downloadFile`（携带登录态）请求 `pdf_url`
→ `wx.openDocument` 预览。
