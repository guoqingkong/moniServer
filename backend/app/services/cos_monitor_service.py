from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean
from typing import Dict, List, Optional, Tuple

from app.clients.tencent_monitor import TencentMonitorClient
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

    def __init__(self, client: TencentMonitorClient) -> None:
        self._client = client

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
            self._build_series(
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

        return MetricSeries(
            key=definition.key,  # type: ignore[arg-type]
            label=definition.label,
            unit=definition.unit,
            period=period,
            points=parsed_points,
            latest=values[-1] if values else None,
            average=round(mean(values), 2) if values else None,
            peak=max(values) if values else None,
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
