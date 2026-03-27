from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


MetricKey = Literal["cpu", "memory", "network_in", "network_out", "disk_usage"]


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
