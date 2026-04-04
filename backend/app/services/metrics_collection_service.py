import asyncio
import traceback
from datetime import datetime, timedelta

from app.config import Settings
from app.repositories import PollRunRecord, PollRunRepository
from app.services.cos_monitor_service import COS_METRICS, CosMonitorService
from app.services.monitor_service import METRICS, MonitorService


class MetricsCollectionService:
    def __init__(
        self,
        settings: Settings,
        monitor_service: MonitorService,
        cos_monitor_service: CosMonitorService,
    ) -> None:
        self._settings = settings
        self._monitor_service = monitor_service
        self._cos_monitor_service = cos_monitor_service
        self._poll_run_repository = PollRunRepository(settings)
        self._running = False
        self._task = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self.collect_once()
            except Exception:
                traceback.print_exc()
            await asyncio.sleep(self._settings.metrics_collection_poll_seconds)

    async def collect_once(self) -> int:
        return await asyncio.to_thread(self._collect_once_sync)

    def _collect_once_sync(self) -> int:
        started_at = datetime.now().astimezone().isoformat()
        run_id = self._poll_run_repository.create(
            PollRunRecord(
                job_name="metric_collection",
                resource_type="all",
                started_at=started_at,
            )
        )
        points_written = 0

        try:
            lookback_end = datetime.now().astimezone()
            lookback_start = lookback_end - timedelta(minutes=self._settings.metrics_collection_lookback_minutes)

            for instance_id in self._settings.monitor_instance_id_list:
                for definition in METRICS:
                    series = self._monitor_service.get_metric_series(
                        instance_id=instance_id,
                        metric_key=definition.key,
                        start_time=lookback_start,
                        end_time=lookback_end,
                        period=300,
                    )
                    points_written += len(series.points)

            for bucket_name in self._settings.monitor_cos_bucket_name_list:
                for definition in COS_METRICS:
                    series = self._cos_monitor_service.get_metric_series(
                        bucket_name=bucket_name,
                        metric_key=definition.key,
                        start_time=lookback_start,
                        end_time=lookback_end,
                        period=300,
                    )
                    points_written += len(series.points)

            self._poll_run_repository.update(
                run_id,
                finished_at=datetime.now().astimezone().isoformat(),
                status="success",
                error_message=None,
                points_written=points_written,
            )
            return points_written
        except Exception as exc:
            self._poll_run_repository.update(
                run_id,
                finished_at=datetime.now().astimezone().isoformat(),
                status="failed",
                error_message=str(exc),
                points_written=points_written,
            )
            raise
