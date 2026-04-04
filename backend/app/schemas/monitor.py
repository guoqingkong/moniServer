from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


MetricKey = Literal[
    "cpu",
    "memory",
    "network_in",
    "network_out",
    "disk_usage",
    "storage_size",
    "object_count",
    "request_get",
    "request_put",
]


class TimePoint(BaseModel):
    timestamp: datetime
    value: Optional[float] = None


class MetricSeries(BaseModel):
    key: MetricKey
    label: str
    unit: str
    period: int
    points: List[TimePoint]
    latest: Optional[float] = None
    average: Optional[float] = None
    peak: Optional[float] = None


class MetricCard(BaseModel):
    key: MetricKey
    label: str
    unit: str
    latest: Optional[float] = None
    average: Optional[float] = None
    peak: Optional[float] = None


class DashboardResponse(BaseModel):
    instance_id: str = Field(alias="instanceId")
    start_time: datetime = Field(alias="startTime")
    end_time: datetime = Field(alias="endTime")
    period: int
    cards: List[MetricCard]
    series: List[MetricSeries]


class AlertEventResponse(BaseModel):
    instance_id: str = Field(alias="instanceId")
    metric_key: str = Field(alias="metricKey")
    metric_label: str = Field(alias="metricLabel")
    threshold_mbps: float = Field(alias="thresholdMbps")
    current_value: float = Field(alias="currentValue")
    timestamp: datetime


class HistoricalSeriesResponse(BaseModel):
    resource_type: str = Field(alias="resourceType")
    resource_id: str = Field(alias="resourceId")
    metric_key: str = Field(alias="metricKey")
    metric_label: str = Field(alias="metricLabel")
    unit: str
    start_time: datetime = Field(alias="startTime")
    end_time: datetime = Field(alias="endTime")
    points: List[TimePoint]
    latest: Optional[float] = None
    average: Optional[float] = None
    peak: Optional[float] = None


class MetricWindowSummary(BaseModel):
    start_time: datetime = Field(alias="startTime")
    end_time: datetime = Field(alias="endTime")
    latest: Optional[float] = None
    average: Optional[float] = None
    peak: Optional[float] = None
    point_count: int = Field(alias="pointCount")


class MetricComparisonResponse(BaseModel):
    resource_type: str = Field(alias="resourceType")
    resource_id: str = Field(alias="resourceId")
    metric_key: str = Field(alias="metricKey")
    metric_label: str = Field(alias="metricLabel")
    unit: str
    current_window: MetricWindowSummary = Field(alias="currentWindow")
    previous_window: MetricWindowSummary = Field(alias="previousWindow")
    average_delta: Optional[float] = Field(default=None, alias="averageDelta")
    peak_delta: Optional[float] = Field(default=None, alias="peakDelta")


class PollRunStatusResponse(BaseModel):
    job_name: str = Field(alias="jobName")
    status: str
    started_at: datetime = Field(alias="startedAt")
    finished_at: Optional[datetime] = Field(default=None, alias="finishedAt")
    points_written: int = Field(alias="pointsWritten")
    error_message: Optional[str] = Field(default=None, alias="errorMessage")
    poll_seconds: int = Field(alias="pollSeconds")
    next_run_at: Optional[datetime] = Field(default=None, alias="nextRunAt")
