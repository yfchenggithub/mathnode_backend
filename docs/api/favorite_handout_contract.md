# 收藏讲义 API 契约（MVP）

## 1. 功能定义

“收藏讲义”是把服务器上已经预构建好的单条 PDF 按收藏默认顺序合并成一份新 PDF。

本功能**不**做以下事情：
- 不根据详情内容重新排版生成 PDF
- 不读取 `canonical_content_v2.json` 重建正文
- 不重新渲染 LaTeX / 公式图片
- 不接收前端上传 `pdf_url` / `pdf_path`

## 2. 鉴权

- 三个接口都必须登录。
- 复用现有鉴权依赖（Bearer Token / X-Token）。
- `handout_id` 不是授权凭证，所有读取与下载都要校验当前用户归属。

## 3. 生成流程（同步）

1. 基于鉴权拿到当前用户 `user_id`
2. 读取当前收藏快照（按收藏页默认顺序）
3. 从收藏项拿到 `conclusion_id`
4. 通过 `pdf_mapping_store` + `PdfService.resolve_pdf_file` 解析并校验本地源 PDF
5. 任一源 PDF 缺失则整次失败（不静默跳过）
6. 顺序合并源 PDF，先写临时文件，再原子替换到最终文件
7. 持久化讲义元数据（含归属用户、快照、过期时间）
8. 返回 `ready` 与受鉴权保护的 `pdf_url`

## 4. 接口

### 4.1 POST `/api/v1/favorites/handouts`

- 用途：生成收藏讲义
- 请求体：允许空 body 或 `{}`；禁止额外字段
- 成功：`201`
- 失败：
  - 无收藏：`409`，`error_code=NO_FAVORITES`
  - 源 PDF 缺失：`409`，`error_code=HANDOUT_SOURCE_PDF_MISSING`，可带 `missing_items`
  - 合并失败：`500`，`error_code=HANDOUT_MERGE_FAILED`

### 4.2 GET `/api/v1/favorites/handouts/{handout_id}`

- 用途：查询讲义元信息
- 成功：`200`
- 不存在或不属于当前用户：`404`，`error_code=HANDOUT_NOT_FOUND`
- 过期行为：返回 `200` 且 `status=expired`

### 4.3 GET `/api/v1/favorites/handouts/{handout_id}/pdf`

- 用途：下载/预览最终合并 PDF
- 成功：`200`，`Content-Type: application/pdf`
- `Content-Disposition`: `inline`，支持中文文件名（`filename*=`）
- 失败：
  - 不存在或无权限：`404`，`error_code=HANDOUT_NOT_FOUND`
  - 已过期：`410`，`error_code=HANDOUT_EXPIRED`
  - 元数据在但文件丢失：`500`，`error_code=HANDOUT_FILE_MISSING`

## 5. 响应风格

项目沿用统一 envelope：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "handout_id": "fh_xxx",
    "title": "收藏讲义",
    "status": "ready",
    "item_count": 24,
    "filename": "收藏讲义_20260530.pdf",
    "pdf_url": "/api/v1/favorites/handouts/fh_xxx/pdf",
    "created_at": "2026-05-30T10:30:00+08:00",
    "expires_at": "2026-06-06T10:30:00+08:00",
    "error": null
  }
}
```

业务错误在原有 `code/message/data` 基础上附加 `error_code`，并在需要时附加 `missing_items`。

## 6. 顺序与快照规则

- 合并顺序严格跟随“我的收藏”默认展示顺序。
- 本次实现与当前收藏接口保持一致（按 `conclusion_id` 升序）。
- 生成时固定一次快照，后续收藏变更不影响已生成讲义。

## 7. 存储与过期

- 源 PDF：`PDF_ROOT_DIR`（默认 `app/data/pdfs`）
- 讲义输出目录：`HANDOUT_OUTPUT_DIR`（默认 `app/data/handouts`）
- 讲义默认有效期：`HANDOUT_EXPIRE_DAYS`（默认 7 天）
- 时区展示：`HANDOUT_TIMEZONE`（默认 `Asia/Shanghai`）

> 当前阶段未引入定时清理任务；后续可加离线清理作业删除过期文件。

## 8. 小程序接入流程

1. 点击“生成收藏讲义”
2. `POST /api/v1/favorites/handouts`
3. 返回 `ready + pdf_url`
4. 小程序用登录态请求 `pdf_url`（`wx.downloadFile`）
5. `wx.openDocument` 预览合并后单份 PDF
