from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.clients.tencent_monitor import TencentMonitorClient
from app.schemas.monitor import DashboardResponse
from app.services.monitor_service import MonitorService

router = APIRouter(prefix="/api/monitor", tags=["monitor"])

AVAILABLE_INSTANCES = [
    {"id": "ins-ltludxxq", "name": "入口", "region": "ap-nanjing"},
    {"id": "ins-da3g9cte", "name": "数据", "region": "ap-nanjing"},
]


def get_monitor_service(settings: Settings = Depends(get_settings)) -> MonitorService:
    if not settings.tencent_secret_id or not settings.tencent_secret_key:
        raise HTTPException(status_code=500, detail="Tencent Cloud credentials are not configured.")
    client = TencentMonitorClient(settings)
    return MonitorService(client)


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
        "supportedMetrics": ["cpu", "memory", "network_in", "network_out", "disk_usage"],
        "defaultRangeHours": 6,
    }
