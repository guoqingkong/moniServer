from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.clients.tencent_monitor import TencentMonitorClient
from app.repositories import MonitorRepository, PollRunRepository
from app.schemas.monitor import (
    AlertEventResponse,
    DashboardResponse,
    HistoricalSeriesResponse,
    MetricComparisonResponse,
    PollRunStatusResponse,
)
from app.services.bandwidth_alert_service import BandwidthAlertService
from app.services.cos_monitor_service import CosMonitorService
from app.services.email_service import EmailService
from app.services.monitor_service import MonitorService

router = APIRouter(prefix="/api/monitor", tags=["monitor"])

AVAILABLE_INSTANCES = [
    {"id": "ins-ltludxxq", "name": "入口", "region": "ap-nanjing"},
    {"id": "ins-da3g9cte", "name": "数据", "region": "ap-nanjing"},
]
AVAILABLE_COS_BUCKETS = [
    {"name": "adp-1333737643", "label": "adp", "region": "ap-nanjing"},
    {"name": "xmmj-1333737643", "label": "xmmj", "region": "ap-nanjing"},
]


def get_monitor_service(settings: Settings = Depends(get_settings)) -> MonitorService:
    if not settings.tencent_secret_id or not settings.tencent_secret_key:
        raise HTTPException(status_code=500, detail="Tencent Cloud credentials are not configured.")
    client = TencentMonitorClient(settings)
    return MonitorService(client, settings)


def get_bandwidth_alert_service(settings: Settings = Depends(get_settings)) -> BandwidthAlertService:
    monitor_service = get_monitor_service(settings)
    email_service = EmailService(settings)
    return BandwidthAlertService(settings, monitor_service, email_service)


def get_cos_monitor_service(settings: Settings = Depends(get_settings)) -> CosMonitorService:
    client = TencentMonitorClient(settings, region="ap-guangzhou")
    return CosMonitorService(client, settings)


def get_monitor_repository(settings: Settings = Depends(get_settings)) -> MonitorRepository:
    return MonitorRepository(settings)


def get_poll_run_repository(settings: Settings = Depends(get_settings)) -> PollRunRepository:
    return PollRunRepository(settings)


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    instance_id: str = Query(alias="instanceId"),
    start_time: Optional[datetime] = Query(default=None, alias="startTime"),
    end_time: Optional[datetime] = Query(default=None, alias="endTime"),
    period: Optional[int] = Query(default=None, ge=60, le=3600),
    range_hours: int = Query(default=6, alias="rangeHours", ge=1, le=72),
    service: MonitorService = Depends(get_monitor_service),
) -> DashboardResponse:
    try:
        return service.get_dashboard(
            instance_id=instance_id,
            start_time=start_time,
            end_time=end_time,
            period=period,
            range_hours=range_hours,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/config")
def get_monitor_config(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "defaultInstanceId": settings.default_instance_id,
        "instances": AVAILABLE_INSTANCES,
        "cosBuckets": AVAILABLE_COS_BUCKETS,
        "supportedMetrics": ["cpu", "memory", "network_in", "network_out", "disk_usage"],
        "defaultRangeHours": 6,
    }


@router.get("/cos/dashboard", response_model=DashboardResponse)
def get_cos_dashboard(
    bucket_name: str = Query(alias="bucketName"),
    start_time: Optional[datetime] = Query(default=None, alias="startTime"),
    end_time: Optional[datetime] = Query(default=None, alias="endTime"),
    period: Optional[int] = Query(default=None, ge=300, le=3600),
    range_hours: int = Query(default=24, alias="rangeHours", ge=1, le=168),
    service: CosMonitorService = Depends(get_cos_monitor_service),
) -> DashboardResponse:
    try:
        return service.get_dashboard(
            bucket_name=bucket_name,
            start_time=start_time,
            end_time=end_time,
            period=period,
            range_hours=range_hours,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/alerts/recent", response_model=list[AlertEventResponse])
def get_recent_alerts(
    limit: int = Query(default=20, ge=1, le=100),
    service: BandwidthAlertService = Depends(get_bandwidth_alert_service),
) -> list[AlertEventResponse]:
    return service.list_recent_events(limit=limit)


@router.get("/history", response_model=HistoricalSeriesResponse)
def get_history(
    resource_type: str = Query(alias="resourceType"),
    resource_id: str = Query(alias="resourceId"),
    metric_key: str = Query(alias="metricKey"),
    start_time: datetime = Query(alias="startTime"),
    end_time: datetime = Query(alias="endTime"),
    repository: MonitorRepository = Depends(get_monitor_repository),
) -> HistoricalSeriesResponse:
    result = repository.get_historical_series(
        resource_type=resource_type,
        resource_id=resource_id,
        metric_key=metric_key,
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="No historical metric data found for the given query.")
    return result


@router.get("/compare", response_model=MetricComparisonResponse)
def compare_history(
    resource_type: str = Query(alias="resourceType"),
    resource_id: str = Query(alias="resourceId"),
    metric_key: str = Query(alias="metricKey"),
    current_start: datetime = Query(alias="currentStart"),
    current_end: datetime = Query(alias="currentEnd"),
    previous_start: datetime = Query(alias="previousStart"),
    previous_end: datetime = Query(alias="previousEnd"),
    repository: MonitorRepository = Depends(get_monitor_repository),
) -> MetricComparisonResponse:
    result = repository.compare_metric_windows(
        resource_type=resource_type,
        resource_id=resource_id,
        metric_key=metric_key,
        current_start=current_start.isoformat(),
        current_end=current_end.isoformat(),
        previous_start=previous_start.isoformat(),
        previous_end=previous_end.isoformat(),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="No metric comparison data found for the given query.")
    return result


@router.get("/collector/status", response_model=PollRunStatusResponse)
def get_collector_status(
    repository: PollRunRepository = Depends(get_poll_run_repository),
    settings: Settings = Depends(get_settings),
) -> PollRunStatusResponse:
    result = repository.get_latest("metric_collection", settings.metrics_collection_poll_seconds)
    if result is None:
        raise HTTPException(status_code=404, detail="No collection runs found.")
    return result
