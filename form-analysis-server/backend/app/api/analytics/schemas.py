"""Pydantic models for analytics API endpoints."""

from typing import Any, Literal
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """Request payload for returning analysis JSON produced by an external analytics package."""

    start_date: str | None = Field(default=None, description="YYYY-MM-DD")
    end_date: str | None = Field(default=None, description="YYYY-MM-DD")
    product_id: str | None = Field(default=None, description="客戶退貨產品編號")
    product_ids: list[str] = Field(default_factory=list, description="客訴 product_id 清單")
    stations: list[Literal["P2", "P3", "ALL"]] = Field(
        default_factory=list,
        description="站點篩選（作為 query 參數傳給分析 package）",
    )


class ArtifactListItem(BaseModel):
    key: str
    filename: str
    exists: bool
    size_bytes: int | None = None
    mtime_epoch: float | None = None


class ArtifactInputResolveResponse(BaseModel):
    requested: list[str]
    requested_count: int | None = None
    normalized_inputs: dict[str, list[str]] = Field(default_factory=dict)
    resolved: list[str]
    resolved_count: int | None = None
    unmatched: list[str]
    unmatched_count: int | None = None
    matches: dict[str, list[str]]
    match_diagnostics: dict[str, dict[str, Any]] = Field(default_factory=dict)
    trace_tokens: dict[str, list[str]] = Field(default_factory=dict)
    trace_attempted_count: int | None = None
    trace_resolved_count: int | None = None
    unmatched_reason_counts: dict[str, int] = Field(default_factory=dict)
    elapsed_ms: float | None = None


class ArtifactSnapshotBucket(BaseModel):
    name: str
    count: int


class ArtifactUnifiedSnapshotResponse(BaseModel):
    artifact_key: str
    sample_count: int
    station_distribution: list[ArtifactSnapshotBucket] = Field(default_factory=list)
    machine_distribution: list[ArtifactSnapshotBucket] = Field(default_factory=list)
    top_features: list[ArtifactSnapshotBucket] = Field(default_factory=list)
    metrics: dict[str, int] = Field(default_factory=dict)


class ComplaintAnalysisRequest(BaseModel):
    product_ids: list[str] = Field(default_factory=list, description="客訴 product_id 清單")
    include_basic_stats: bool = Field(
        default=True,
        description="是否包含基本統計",
    )
    include_outliers: bool = Field(
        default=True,
        description="是否包含異常檢測",
    )
    include_contribution: bool = Field(
        default=False,
        description="是否包含 PCA 貢獻度分析（較耗時）",
    )


class ComplaintAnalysisResponse(BaseModel):
    requested_ids: list[str] = Field(default_factory=list)
    mapping: dict[str, dict[str, Any]] = Field(default_factory=dict)
    source_scope: dict[str, int] = Field(default_factory=dict)
    analysis: dict[str, Any] = Field(default_factory=dict)
    machine_distribution: list[dict[str, Any]] = Field(default_factory=list)
    winder_distribution: list[dict[str, Any]] = Field(default_factory=list)
    timing: dict[str, float] = Field(default_factory=dict)
    elapsed_ms: float | None = None


class RealtimeAnalysisRequest(BaseModel):
    """即時 Analytical-Four 分析請求"""
    station: str = Field(default="P2", description="分析站點 (P1/P2/P3)")
    start_date: str | None = Field(default=None, description="開始日期 (YYYY-MM-DD)")
    end_date: str | None = Field(default=None, description="結束日期 (YYYY-MM-DD)")
    include_basic_stats: bool = Field(default=True, description="包含基本統計")
    include_outliers: bool = Field(default=True, description="包含異常檢測")
    include_contribution: bool = Field(default=False, description="包含 PCA 貢獻度分析（較耗時）")


class ExtractionAnalysisRequest(BaseModel):
    product_ids: list[str] = Field(default_factory=list, description="product_id 清單")
    start_date: str | None = Field(default=None, description="開始日期 YYYY-MM-DD")
    end_date: str | None = Field(default=None, description="結束日期 YYYY-MM-DD")
    station: str = Field(default="P2", description="站點代碼 (P1/P2/P3)")


class ExtractionAnalysisResponse(BaseModel):
    station: str
    boundary_count: dict[str, int] = Field(default_factory=dict)
    spe_score: dict[str, float] = Field(default_factory=dict)
    t2_score: dict[str, float] = Field(default_factory=dict)
    final_raw_score: dict[str, float] = Field(default_factory=dict)
    features_used: list[str] = Field(default_factory=list)
    sample_counts: dict[str, int] = Field(default_factory=dict)
    elapsed_ms: float | None = None
