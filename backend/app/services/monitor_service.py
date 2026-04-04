from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean
from typing import Dict, List, Optional, Tuple

from app.clients.tencent_monitor import TencentMonitorClient
from app.config import Settings
from app.repositories import MonitorRepository
from app.schemas.monitor import DashboardResponse, MetricCard, MetricSeries, TimePoint


@dataclass(frozen=True)
class MetricDefinition:
    key: str
    label: str
    metric_name: str
    unit: str


METRICS: Tuple[MetricDefinition, ...] = (
    MetricDefinition("cpu", "CPU 使用率", "CpuUsage", "%"),
    MetricDefinition("memory", "内存使用率", "MemUsage", "%"),
    MetricDefinition("network_in", "公网入带宽", "WanIntraffic", "Mbps"),
    MetricDefinition("network_out", "公网出带宽", "WanOuttraffic", "Mbps"),
    MetricDefinition("disk_usage", "磁盘使用率", "CvmDiskUsage", "%"),
)


class MonitorService:
    namespace = "QCE/CVM"

    def __init__(self, client: TencentMonitorClient, settings: Optional[Settings] = None) -> None:
        self._client = client
        self._repository = MonitorRepository(settings) if settings else None

    def get_dashboard(
        self,
        instance_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        period: Optional[int] = None,
        range_hours: int = 6,
    ) -> DashboardResponse:
        resolved_end = end_time or datetime.now().astimezone()
        resolved_start = start_time or (resolved_end - timedelta(hours=range_hours))
        resolved_period = period or self._select_period(resolved_start, resolved_end)

        series = [
            self._get_series_with_cache(
                definition=definition,
                instance_id=instance_id,
                period=resolved_period,
                start_time=resolved_start,
                end_time=resolved_end,
            )
            for definition in METRICS
        ]

        cards = [
            MetricCard(
                key=item.key,
                label=item.label,
                unit=item.unit,
                latest=item.latest,
                average=item.average,
                peak=item.peak,
            )
            for item in series
        ]

        return DashboardResponse(
            instanceId=instance_id,
            startTime=resolved_start,
            endTime=resolved_end,
            period=resolved_period,
            cards=cards,
            series=series,
        )

    def get_metric_series(
        self,
        instance_id: str,
        metric_key: str,
        start_time: datetime,
        end_time: datetime,
        period: int,
    ) -> MetricSeries:
        definition = next((item for item in METRICS if item.key == metric_key), None)
        if definition is None:
            raise ValueError(f"Unsupported metric key: {metric_key}")

        return self._build_series(
            definition=definition,
            instance_id=instance_id,
            period=period,
            start_time=start_time,
            end_time=end_time,
        )

    def _get_series_with_cache(
        self,
        definition: MetricDefinition,
        instance_id: str,
        period: int,
        start_time: datetime,
        end_time: datetime,
    ) -> MetricSeries:
        cached = self._get_cached_series(
            resource_type="cvm",
            resource_id=instance_id,
            definition_key=definition.key,
            start_time=start_time,
            end_time=end_time,
            freshness_seconds=max(period * 2, 180),
        )
        if cached is not None:
            return cached

        return self._build_series(
            definition=definition,
            instance_id=instance_id,
            period=period,
            start_time=start_time,
            end_time=end_time,
        )

    def _build_series(
        self,
        definition: MetricDefinition,
        instance_id: str,
        period: int,
        start_time: datetime,
        end_time: datetime,
    ) -> MetricSeries:
        raw_points = self._client.get_monitor_data(
            namespace=self.namespace,
            metric_name=definition.metric_name,
            dimensions=[{"Name": "InstanceId", "Value": instance_id}],
            period=period,
            start_time=start_time,
            end_time=end_time,
        )
        parsed_points = self._normalize_points(raw_points)
        values = [point.value for point in parsed_points if point.value is not None]

        series = MetricSeries(
            key=definition.key,  # type: ignore[arg-type]
            label=definition.label,
            unit=definition.unit,
            period=period,
            points=parsed_points,
            latest=values[-1] if values else None,
            average=round(mean(values), 2) if values else None,
            peak=max(values) if values else None,
        )
        if self._repository:
            self._repository.save_metric_series("cvm", instance_id, series)
        return series

    def _get_cached_series(
        self,
        resource_type: str,
        resource_id: str,
        definition_key: str,
        start_time: datetime,
        end_time: datetime,
        freshness_seconds: int,
    ) -> Optional[MetricSeries]:
        if not self._repository:
            return None

        historical = self._repository.get_historical_series(
            resource_type=resource_type,
            resource_id=resource_id,
            metric_key=definition_key,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
        )
        if historical is None or not historical.points:
            return None

        latest_point = historical.points[-1].timestamp
        if isinstance(latest_point, str):
            latest_point = datetime.fromisoformat(latest_point)

        if (end_time - latest_point).total_seconds() > freshness_seconds:
            return None

        return MetricSeries(
            key=historical.metric_key,  # type: ignore[arg-type]
            label=historical.metric_label,
            unit=historical.unit,
            period=self._select_period(start_time, end_time),
            points=historical.points,
            latest=historical.latest,
            average=historical.average,
            peak=historical.peak,
        )

    def _normalize_points(self, raw_points: List[Dict]) -> List[TimePoint]:
        normalized: List[TimePoint] = []

        for item in raw_points:
            timestamps = item.get("Timestamps") or []
            values = item.get("Values") or []
            pairs = zip(timestamps, values)
            for ts, value in pairs:
                normalized.append(
                    TimePoint(
                        timestamp=datetime.fromtimestamp(ts).astimezone(),
                        value=round(float(value), 2) if value is not None else None,
                    )
                )

        normalized.sort(key=lambda point: point.timestamp)
        return normalized

    def _select_period(self, start_time: datetime, end_time: datetime) -> int:
        total_seconds = (end_time - start_time).total_seconds()
        if total_seconds <= 6 * 3600:
            return 60
        if total_seconds <= 3 * 24 * 3600:
            return 300
        return 3600
