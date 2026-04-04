from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean
from typing import Dict, List, Optional, Tuple

from app.clients.tencent_monitor import TencentMonitorClient
from app.config import Settings
from app.repositories import MonitorRepository
from app.schemas.monitor import DashboardResponse, MetricCard, MetricSeries, TimePoint


@dataclass(frozen=True)
class CosMetricDefinition:
    key: str
    label: str
    metric_name: str
    unit: str
    divisor: float = 1.0


COS_METRICS: Tuple[CosMetricDefinition, ...] = (
    CosMetricDefinition("storage_size", "标准存储容量", "StdStorage", "MB"),
    CosMetricDefinition("object_count", "标准对象数量", "StdObjectNumber", "个"),
    CosMetricDefinition("network_out", "外网下行带宽", "InternetTrafficBandwidth", "Mbps", divisor=1_000_000),
    CosMetricDefinition("network_in", "外网上行带宽", "InternetTrafficUpBandwidth", "Mbps", divisor=1_000_000),
    CosMetricDefinition("request_get", "GET 请求数", "GetRequests", "次"),
    CosMetricDefinition("request_put", "PUT 请求数", "PutRequests", "次"),
)


class CosMonitorService:
    namespace = "QCE/COS"

    def __init__(self, client: TencentMonitorClient, settings: Optional[Settings] = None) -> None:
        self._client = client
        self._repository = MonitorRepository(settings) if settings else None

    def get_dashboard(
        self,
        bucket_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        period: Optional[int] = None,
        range_hours: int = 24,
    ) -> DashboardResponse:
        resolved_end = end_time or datetime.now().astimezone()
        resolved_start = start_time or (resolved_end - timedelta(hours=range_hours))
        resolved_period = period or self._select_period(resolved_start, resolved_end)

        series = [
            self._get_series_with_cache(
                definition=definition,
                bucket_name=bucket_name,
                period=resolved_period,
                start_time=resolved_start,
                end_time=resolved_end,
            )
            for definition in COS_METRICS
        ]

        cards = [
            MetricCard(
                key=item.key,  # type: ignore[arg-type]
                label=item.label,
                unit=item.unit,
                latest=item.latest,
                average=item.average,
                peak=item.peak,
            )
            for item in series
        ]

        return DashboardResponse(
            instanceId=bucket_name,
            startTime=resolved_start,
            endTime=resolved_end,
            period=resolved_period,
            cards=cards,
            series=series,
        )

    def get_metric_series(
        self,
        bucket_name: str,
        metric_key: str,
        start_time: datetime,
        end_time: datetime,
        period: int,
    ) -> MetricSeries:
        definition = next((item for item in COS_METRICS if item.key == metric_key), None)
        if definition is None:
            raise ValueError(f"Unsupported metric key: {metric_key}")

        return self._build_series(
            definition=definition,
            bucket_name=bucket_name,
            period=period,
            start_time=start_time,
            end_time=end_time,
        )

    def _get_series_with_cache(
        self,
        definition: CosMetricDefinition,
        bucket_name: str,
        period: int,
        start_time: datetime,
        end_time: datetime,
    ) -> MetricSeries:
        cached = self._get_cached_series(
            resource_type="cos",
            resource_id=bucket_name,
            definition_key=definition.key,
            start_time=start_time,
            end_time=end_time,
            freshness_seconds=max(period * 2, 900),
        )
        if cached is not None:
            return cached

        return self._build_series(
            definition=definition,
            bucket_name=bucket_name,
            period=period,
            start_time=start_time,
            end_time=end_time,
        )

    def _build_series(
        self,
        definition: CosMetricDefinition,
        bucket_name: str,
        period: int,
        start_time: datetime,
        end_time: datetime,
    ) -> MetricSeries:
        raw_points = self._client.get_monitor_data(
            namespace=self.namespace,
            metric_name=definition.metric_name,
            dimensions=[{"Name": "bucket", "Value": bucket_name}],
            period=period,
            start_time=start_time,
            end_time=end_time,
        )
        parsed_points = self._normalize_points(raw_points, definition.divisor)
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
            self._repository.save_metric_series("cos", bucket_name, series)
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

    def _normalize_points(self, raw_points: List[Dict], divisor: float) -> List[TimePoint]:
        normalized: List[TimePoint] = []

        for item in raw_points:
            timestamps = item.get("Timestamps") or []
            values = item.get("Values") or []
            for ts, value in zip(timestamps, values):
                normalized.append(
                    TimePoint(
                        timestamp=datetime.fromtimestamp(ts).astimezone(),
                        value=round(float(value) / divisor, 2) if value is not None else None,
                    )
                )

        normalized.sort(key=lambda point: point.timestamp)
        return normalized

    def _select_period(self, start_time: datetime, end_time: datetime) -> int:
        total_seconds = (end_time - start_time).total_seconds()
        if total_seconds <= 24 * 3600:
            return 300
        return 3600
