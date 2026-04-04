from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.monitor import router as monitor_router
from app.config import get_settings
from app.clients.tencent_monitor import TencentMonitorClient
from app.db import init_db
from app.services.bandwidth_alert_service import BandwidthAlertService
from app.services.cos_monitor_service import CosMonitorService
from app.services.email_service import EmailService
from app.services.metrics_collection_service import MetricsCollectionService
from app.services.monitor_service import MonitorService

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db(settings)
    monitor_service = MonitorService(TencentMonitorClient(settings), settings)
    cos_monitor_service = CosMonitorService(TencentMonitorClient(settings, region="ap-guangzhou"), settings)
    email_service = EmailService(settings)
    alert_service = BandwidthAlertService(settings, monitor_service, email_service)
    metrics_collection_service = MetricsCollectionService(settings, monitor_service, cos_monitor_service)
    await metrics_collection_service.start()
    await alert_service.start()
    try:
        yield
    finally:
        await metrics_collection_service.stop()
        await alert_service.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "bandwidthAlertThresholdMbps": settings.bandwidth_alert_threshold_mbps,
        "bandwidthAlertRecipient": settings.bandwidth_alert_recipient,
        "monitoredInstances": settings.monitor_instance_id_list,
        "monitoredCosBuckets": settings.monitor_cos_bucket_name_list,
        "metricsCollectionPollSeconds": settings.metrics_collection_poll_seconds,
        "metricsCollectionLookbackMinutes": settings.metrics_collection_lookback_minutes,
    }


app.include_router(monitor_router)
