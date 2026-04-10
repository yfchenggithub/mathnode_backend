from __future__ import annotations

"""
文件: schemas/content_v2.py

用途:
- 定义“高中数学二级结论系统”的跨端 canonical content schema v2
- 作为后端唯一真相源的数据模型
- 供 FastAPI / JSON 文件加载 / SQLite / PostgreSQL 共用
- 供 JSON Schema 导出、接口校验、内容构建脚本复用

设计原则:
1. 后端只保留一份 canonical JSON，不存端专用渲染结果
2. sections 为主展示源，plain 为降级/调试/搜索辅助源
3. 统一 token / block / section 协议，前端只做 renderer，不做内容解析器
4. 模型字段统一 snake_case，适合 Python / JSON / DB 演进
"""

from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ============================================================
# 基础基类
# ============================================================


class StrictBaseModel(BaseModel):
    """
    所有模型统一基类。

    约束:
    - extra="forbid": 禁止未声明字段，避免脏数据 silently 混入
    - populate_by_name=True: 允许按字段名赋值
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        validate_assignment=True,
    )


# ============================================================
# Inline Token 层
# 用于段落内混排文本 + 行内公式
# ============================================================


class TextToken(StrictBaseModel):
    """普通文本 token。"""

    type: Literal["text"] = Field(default="text", description="Token 类型：普通文本")
    text: str = Field(..., min_length=1, description="普通文本内容")


class MathInlineToken(StrictBaseModel):
    """行内公式 token。"""

    type: Literal["math_inline"] = Field(
        default="math_inline", description="Token 类型：行内公式"
    )
    latex: str = Field(..., min_length=1, description="LaTeX 公式字符串，用于行内渲染")


class MathDisplayToken(StrictBaseModel):
    """展示型公式 token。通常用于少量特殊内联场景；大段公式更建议用 math_block。"""

    type: Literal["math_display"] = Field(
        default="math_display", description="Token 类型：展示型公式"
    )
    latex: str = Field(
        ..., min_length=1, description="LaTeX 公式字符串，用于展示公式渲染"
    )


class LineBreakToken(StrictBaseModel):
    """换行 token。"""

    type: Literal["line_break"] = Field(
        default="line_break", description="Token 类型：换行"
    )


class RefToken(StrictBaseModel):
    """内容内引用 token，例如引用另一条结论。"""

    type: Literal["ref"] = Field(default="ref", description="Token 类型：内部引用")
    target_id: str = Field(..., min_length=1, description="被引用内容的稳定 ID")
    text: str = Field(..., min_length=1, description="引用展示文本")


InlineToken = Annotated[
    Union[
        TextToken,
        MathInlineToken,
        MathDisplayToken,
        LineBreakToken,
        RefToken,
    ],
    Field(discriminator="type"),
]


# ============================================================
# 轻量内容结构
# 供 conditions / conclusions / theorem desc 等场景复用
# ============================================================


class InlineContent(StrictBaseModel):
    """由多个 inline token 组成的一段混排内容。"""

    tokens: List[InlineToken] = Field(
        ...,
        min_length=1,
        description="段内 token 列表，支持 text / math_inline / ref / line_break 等",
    )


# ============================================================
# Block 层
# Section 内部统一使用 blocks 渲染
# ============================================================


class ParagraphBlock(StrictBaseModel):
    """正文段落块。支持文本与行内公式混排。"""

    id: str = Field(..., min_length=1, description="块 ID，建议在同一条内容内唯一")
    type: Literal["paragraph"] = Field(
        default="paragraph", description="块类型：正文段落"
    )
    tokens: List[InlineToken] = Field(..., min_length=1, description="段落 token 列表")


class MathBlock(StrictBaseModel):
    """独立公式块。"""

    id: str = Field(..., min_length=1, description="块 ID")
    type: Literal["math_block"] = Field(
        default="math_block", description="块类型：独立公式块"
    )
    latex: str = Field(..., min_length=1, description="独立展示的 LaTeX 公式")
    align: Literal["left", "center", "right"] = Field(
        default="center", description="公式块对齐方式"
    )


class DividerBlock(StrictBaseModel):
    """分隔线块。"""

    id: str = Field(..., min_length=1, description="块 ID")
    type: Literal["divider"] = Field(default="divider", description="块类型：分隔线")


class BulletListItem(StrictBaseModel):
    """无序列表单项。"""

    tokens: List[InlineToken] = Field(
        ..., min_length=1, description="列表项内容，支持混排"
    )


class BulletListBlock(StrictBaseModel):
    """要点列表块。"""

    id: str = Field(..., min_length=1, description="块 ID")
    type: Literal["bullet_list"] = Field(
        default="bullet_list", description="块类型：无序列表"
    )
    items: List[BulletListItem] = Field(..., min_length=1, description="列表项数组")


class TheoremItem(StrictBaseModel):
    """定理/结论组中的单项。"""

    title: str = Field(
        ..., min_length=1, description="单项标题，如：结论一（原始形式）"
    )
    desc_tokens: Optional[List[InlineToken]] = Field(
        default=None, description="说明文本，可混排"
    )
    formula_latex: str = Field(..., min_length=1, description="该条结论对应的公式")


class TheoremGroupBlock(StrictBaseModel):
    """定理组 / 等价形式组。对应你当前的 theorem-list。"""

    id: str = Field(..., min_length=1, description="块 ID")
    type: Literal["theorem_group"] = Field(
        default="theorem_group", description="块类型：定理/结论组"
    )
    items: List[TheoremItem] = Field(..., min_length=1, description="定理/结论项列表")


class StepContentParagraph(StrictBaseModel):
    """证明步骤内部的段落块。"""

    type: Literal["paragraph"] = Field(
        default="paragraph", description="步骤内容子块类型：段落"
    )
    tokens: List[InlineToken] = Field(
        ..., min_length=1, description="步骤段落 token 列表"
    )


class StepContentMath(StrictBaseModel):
    """证明步骤内部的公式块。"""

    type: Literal["math_block"] = Field(
        default="math_block", description="步骤内容子块类型：公式"
    )
    latex: str = Field(..., min_length=1, description="步骤中的独立 LaTeX 公式")
    align: Literal["left", "center", "right"] = Field(
        default="center", description="公式对齐方式"
    )


class StepContentBulletList(StrictBaseModel):
    """证明步骤内部的列表块。"""

    type: Literal["bullet_list"] = Field(
        default="bullet_list", description="步骤内容子块类型：列表"
    )
    items: List[BulletListItem] = Field(..., min_length=1, description="步骤中的列表项")


StepContentBlock = Annotated[
    Union[
        StepContentParagraph,
        StepContentMath,
        StepContentBulletList,
    ],
    Field(discriminator="type"),
]


class ProofStep(StrictBaseModel):
    """证明中的单步。"""

    title: str = Field(
        ..., min_length=1, description="步骤标题，如：步骤一（乘积形式）"
    )
    content: List[StepContentBlock] = Field(
        ..., min_length=1, description="步骤内容，由段落/公式/列表构成"
    )


class ProofStepsBlock(StrictBaseModel):
    """证明步骤组。"""

    id: str = Field(..., min_length=1, description="块 ID")
    type: Literal["proof_steps"] = Field(
        default="proof_steps", description="块类型：证明步骤组"
    )
    steps: List[ProofStep] = Field(..., min_length=1, description="证明步骤列表")


class WarningBlock(StrictBaseModel):
    """警告/易错提醒块。"""

    id: str = Field(..., min_length=1, description="块 ID")
    type: Literal["warning"] = Field(default="warning", description="块类型：警告/提示")
    level: Literal["info", "warning", "error"] = Field(
        default="warning", description="提示等级"
    )
    title: str = Field(..., min_length=1, description="提示标题")
    content: List[StepContentBlock] = Field(..., min_length=1, description="提示正文")


class SummaryBoxBlock(StrictBaseModel):
    """总结框块。"""

    id: str = Field(..., min_length=1, description="块 ID")
    type: Literal["summary_box"] = Field(
        default="summary_box", description="块类型：总结框"
    )
    title: str = Field(..., min_length=1, description="总结框标题")
    content: List[StepContentBlock] = Field(..., min_length=1, description="总结框内容")


class ExampleBlock(StrictBaseModel):
    """例题块。"""

    id: str = Field(..., min_length=1, description="块 ID")
    type: Literal["example"] = Field(default="example", description="块类型：例题")
    title: str = Field(..., min_length=1, description="例题标题，如：例 1（基础）")
    problem: List[StepContentBlock] = Field(..., min_length=1, description="题目部分")
    solution: List[Union[StepContentBlock, ProofStepsBlock]] = Field(
        ..., min_length=1, description="解答部分，可包含证明步骤组"
    )
    answer: Optional[List[StepContentBlock]] = Field(
        default=None, description="答案部分，可选"
    )


ContentBlock = Annotated[
    Union[
        ParagraphBlock,
        MathBlock,
        DividerBlock,
        BulletListBlock,
        TheoremGroupBlock,
        ProofStepsBlock,
        WarningBlock,
        SummaryBoxBlock,
        ExampleBlock,
    ],
    Field(discriminator="type"),
]


# ============================================================
# Section 层
# ============================================================


class ContentSection(StrictBaseModel):
    """
    详情页中的一个主分区。

    说明:
    - key 为稳定业务键，便于前端识别与排序
    - title 为展示标题
    - block_type 为该 section 的主风格提示，便于前端快速选择组件
    - blocks 为实际渲染块数组
    """

    key: str = Field(
        ...,
        min_length=1,
        description="分区稳定键，如 core_formula / statement / explanation / proof / traps",
    )
    title: str = Field(..., min_length=1, description="分区展示标题")
    block_type: Literal[
        "rich_text",
        "math_block",
        "theorem_group",
        "proof_steps",
        "example_group",
        "summary",
        "warning_group",
    ] = Field(..., description="分区主类型提示")
    blocks: List[ContentBlock] = Field(
        ..., min_length=1, description="该 section 下的具体内容块列表"
    )


# ============================================================
# 结构化业务内容
# ============================================================


class VariableDef(StrictBaseModel):
    """变量定义。"""

    name: str = Field(
        ..., min_length=1, description="变量名的人类可读表示，如 M / N / f(x)"
    )
    latex: str = Field(..., min_length=1, description="变量的 LaTeX 形式")
    description: str = Field(..., min_length=1, description="变量说明")
    required: bool = Field(default=True, description="该变量是否为当前命题的必要变量")


class ConditionItem(StrictBaseModel):
    """适用条件项。"""

    id: str = Field(..., min_length=1, description="条件项 ID")
    title: str = Field(..., min_length=1, description="条件标题")
    content: List[InlineToken] = Field(
        ..., min_length=1, description="条件内容，支持混排"
    )
    required: bool = Field(default=True, description="是否为必要条件")
    scope: Optional[str] = Field(
        default=None, description="适用范围说明，如 reciprocal_form_only"
    )


class ConclusionItem(StrictBaseModel):
    """结论项。"""

    id: str = Field(..., min_length=1, description="结论项 ID")
    title: str = Field(..., min_length=1, description="结论标题")
    content: List[InlineToken] = Field(
        ..., min_length=1, description="结论内容，支持混排"
    )


class PlainContent(StrictBaseModel):
    """
    纯文本兜底层。

    用途:
    - 搜索摘要
    - 调试
    - 导出 markdown/txt
    - 降级展示
    - 迁移阶段兼容
    """

    statement: Optional[str] = Field(default=None, description="清洗后的命题表述纯文本")
    explanation: Optional[str] = Field(
        default=None, description="清洗后的理解与直觉纯文本"
    )
    proof: Optional[str] = Field(default=None, description="清洗后的证明纯文本")
    examples: Optional[str] = Field(default=None, description="清洗后的例题纯文本")
    traps: Optional[str] = Field(default=None, description="清洗后的易错点纯文本")
    summary: Optional[str] = Field(default=None, description="清洗后的总结纯文本")


class ContentBodyV2(StrictBaseModel):
    """
    content 主体。

    这是整个 schema v2 的核心层。
    """

    render_schema_version: Literal[2] = Field(
        default=2, description="跨端渲染协议版本，当前固定为 2"
    )
    primary_formula: Optional[str] = Field(
        default=None, description="主公式 / 核心命题"
    )
    variables: List[VariableDef] = Field(
        default_factory=list, description="变量定义列表"
    )
    conditions: List[ConditionItem] = Field(
        default_factory=list, description="适用条件列表"
    )
    conclusions: List[ConclusionItem] = Field(
        default_factory=list, description="主要结论列表"
    )
    sections: List[ContentSection] = Field(
        default_factory=list, description="主展示源：结构化 section 列表"
    )
    plain: PlainContent = Field(
        default_factory=PlainContent, description="纯文本兜底层"
    )

    @model_validator(mode="after")
    def validate_content_source(self) -> "ContentBodyV2":
        """
        约束:
        - sections 和 plain 不能同时都为空
        - 至少要有一种可用内容源
        """
        has_sections = len(self.sections) > 0
        has_plain = any(
            getattr(self.plain, field) not in (None, "")
            for field in self.plain.model_fields
        )
        if not has_sections and not has_plain:
            raise ValueError("content.sections 与 content.plain 不能同时为空")
        return self


# ============================================================
# 顶层 identity / meta / assets / ext
# ============================================================


class IdentityInfo(StrictBaseModel):
    """身份与稳定定位字段。"""

    slug: Optional[str] = Field(
        default=None, description="稳定 slug，可用于 URL / SEO / 前端路由"
    )
    module: str = Field(
        ..., min_length=1, description="所属模块，如 inequality / function / conic"
    )
    knowledge_node: Optional[str] = Field(default=None, description="主知识树节点")
    alt_nodes: List[str] = Field(
        default_factory=list, description="可选的其它知识树节点"
    )


class MetaInfo(StrictBaseModel):
    """业务元数据层。"""

    title: str = Field(..., min_length=1, description="内容标题")
    aliases: List[str] = Field(default_factory=list, description="别名列表")
    difficulty: Optional[int] = Field(
        default=None, ge=0, le=10, description="难度等级，建议 0~10"
    )
    category: Optional[str] = Field(default=None, description="一级分类")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    summary: Optional[str] = Field(
        default=None, description="简短摘要，用于卡片/SEO/推荐"
    )
    is_pro: bool = Field(default=False, description="是否为付费内容")
    remarks: Optional[str] = Field(default=None, description="编辑备注")


class ExtraAsset(StrictBaseModel):
    """扩展资源引用。"""

    kind: str = Field(
        ...,
        min_length=1,
        description="资源类型，如 geogebra / appendix / image / attachment",
    )
    url: str = Field(..., min_length=1, description="资源地址")
    meta: Dict[str, Any] = Field(default_factory=dict, description="资源附加元信息")


class AssetInfo(StrictBaseModel):
    """静态资源层。"""

    cover: Optional[str] = Field(default=None, description="封面资源")
    svg: Optional[str] = Field(default=None, description="SVG 资源路径")
    png: Optional[str] = Field(default=None, description="PNG 资源路径")
    pdf: Optional[str] = Field(default=None, description="PDF 资源路径")
    mp4: Optional[str] = Field(default=None, description="视频资源路径")
    extra: List[ExtraAsset] = Field(default_factory=list, description="扩展资源列表")


class ShareExt(StrictBaseModel):
    """分享扩展信息。"""

    title: Optional[str] = Field(default=None, description="分享标题")
    desc: Optional[str] = Field(default=None, description="分享描述")


class RelationsExt(StrictBaseModel):
    """关联关系扩展信息。"""

    prerequisites: List[str] = Field(default_factory=list, description="前置知识列表")
    related_ids: List[str] = Field(default_factory=list, description="相关内容 ID 列表")
    similar: Optional[str] = Field(default=None, description="相似内容说明")


class ExamExt(StrictBaseModel):
    """考试维度扩展信息。"""

    frequency: Optional[float] = Field(
        default=None, ge=0, description="考试出现频率，可按你自己的尺度定义"
    )
    score: Optional[float] = Field(default=None, ge=0, description="相关分值参考")


class ExtInfo(StrictBaseModel):
    """
    扩展信息层。

    说明:
    - 放非核心但常用的扩展字段
    - 避免污染顶层与 content 核心层
    """

    share: Optional[ShareExt] = Field(default=None, description="分享信息")
    relations: Optional[RelationsExt] = Field(default=None, description="关联关系信息")
    exam: Optional[ExamExt] = Field(default=None, description="考试维度信息")
    extra: Dict[str, Any] = Field(
        default_factory=dict, description="其它尚未结构化的扩展数据"
    )


# ============================================================
# 顶层 Conclusion Record
# ============================================================


class ConclusionRecordV2(StrictBaseModel):
    """
    高中数学二级结论内容的顶层记录模型。

    顶层只保留 1 份 canonical record。
    """

    id: str = Field(
        ..., min_length=1, description="稳定内容 ID，例如 I001 / F023 / C116"
    )
    schema_version: Literal[2] = Field(
        default=2, description="顶层 schema 版本，当前固定为 2"
    )
    type: Literal["conclusion"] = Field(
        default="conclusion", description="记录类型，当前固定为 conclusion"
    )
    status: Literal["draft", "published", "archived"] = Field(
        default="published", description="发布状态"
    )

    identity: IdentityInfo = Field(..., description="身份与定位字段")
    meta: MetaInfo = Field(..., description="业务元数据")
    content: ContentBodyV2 = Field(..., description="结构化内容主体")
    assets: AssetInfo = Field(default_factory=AssetInfo, description="静态资源信息")
    ext: ExtInfo = Field(default_factory=ExtInfo, description="扩展信息")
