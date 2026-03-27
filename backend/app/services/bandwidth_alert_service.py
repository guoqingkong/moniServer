import asyncio
import json
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from app.config import Settings
from app.schemas.monitor import AlertEventResponse
from app.services.email_service import EmailService
from app.services.monitor_service import MonitorService


@dataclass
class BandwidthAlertEvent:
    instance_id: str
    metric_key: str
    metric_label: str
    threshold_mbps: float
    current_value: float
    timestamp: str


class BandwidthAlertService:
    def __init__(
        self,
        settings: Settings,
        monitor_service: MonitorService,
        email_service: EmailService,
    ) -> None:
        self._settings = settings
        self._monitor_service = monitor_service
        self._email_service = email_service
        self._running = False
        self._task = None
        self._state_path = Path(self._settings.bandwidth_alert_state_path)
        self._log_path = Path(self._settings.bandwidth_alert_log_path)
        self._known_alerts = self._load_state()

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
                await self.check_once()
            except Exception:
                traceback.print_exc()
            await asyncio.sleep(self._settings.bandwidth_alert_poll_seconds)

    async def check_once(self) -> List[BandwidthAlertEvent]:
        return await asyncio.to_thread(self._check_once_sync)

    def _check_once_sync(self) -> List[BandwidthAlertEvent]:
        events: List[BandwidthAlertEvent] = []
        lookback_end = datetime.now().astimezone()
        lookback_start = lookback_end - timedelta(minutes=5)

        for instance_id in self._settings.monitor_instance_id_list:
            for metric_key in ("network_in", "network_out"):
                series = self._monitor_service.get_metric_series(
                    instance_id=instance_id,
                    metric_key=metric_key,
                    start_time=lookback_start,
                    end_time=lookback_end,
                    period=60,
                )
                for point in series.points:
                    if point.value is None or point.value <= self._settings.bandwidth_alert_threshold_mbps:
                        continue

                    alert_key = f"{instance_id}:{metric_key}:{point.timestamp.isoformat()}"
                    if alert_key in self._known_alerts:
                        continue

                    event = BandwidthAlertEvent(
                        instance_id=instance_id,
                        metric_key=metric_key,
                        metric_label=series.label,
                        threshold_mbps=self._settings.bandwidth_alert_threshold_mbps,
                        current_value=point.value,
                        timestamp=point.timestamp.isoformat(),
                    )
                    self._record_event(event)
                    self._send_email(event)
                    self._known_alerts[alert_key] = event.timestamp
                    events.append(event)

        self._save_state()
        return events

    def _record_event(self, event: BandwidthAlertEvent) -> None:
        self._ensure_parent(self._log_path)
        with self._log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")

    def _send_email(self, event: BandwidthAlertEvent) -> None:
        if not self._email_service.is_configured:
            return

        subject = f"[CVM Bandwidth Alert] {event.instance_id} {event.metric_label} exceeded {event.threshold_mbps:.0f} Mbps"
        body = (
            "检测到公网带宽告警。\n\n"
            f"实例: {event.instance_id}\n"
            f"指标: {event.metric_label}\n"
            f"阈值: {event.threshold_mbps:.2f} Mbps\n"
            f"当前值: {event.current_value:.2f} Mbps\n"
            f"时间: {event.timestamp}\n"
        )
        try:
            self._email_service.send(subject=subject, body=body, recipient=self._settings.bandwidth_alert_recipient)
        except Exception:
            traceback.print_exc()

    def _load_state(self) -> Dict[str, str]:
        if not self._state_path.exists():
            return {}
        try:
            with self._state_path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except json.JSONDecodeError:
            return {}

    def _save_state(self) -> None:
        self._ensure_parent(self._state_path)
        with self._state_path.open("w", encoding="utf-8") as file:
            json.dump(self._known_alerts, file, ensure_ascii=False, indent=2)

    def _ensure_parent(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

    def list_recent_events(self, limit: int = 20) -> List[AlertEventResponse]:
        if not self._log_path.exists():
            return []

        results: List[AlertEventResponse] = []
        with self._log_path.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                results.append(
                    AlertEventResponse(
                        instanceId=payload["instance_id"],
                        metricKey=payload["metric_key"],
                        metricLabel=payload["metric_label"],
                        thresholdMbps=payload["threshold_mbps"],
                        currentValue=payload["current_value"],
                        timestamp=payload["timestamp"],
                    )
                )

        results.sort(key=lambda item: item.timestamp, reverse=True)
        return results[:limit]
