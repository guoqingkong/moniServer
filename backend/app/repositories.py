from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import mean
from typing import Optional

from app.config import Settings
from app.db import get_connection
from app.schemas.monitor import (
    AlertEventResponse,
    HistoricalSeriesResponse,
    MetricComparisonResponse,
    MetricSeries,
    MetricWindowSummary,
    TimePoint,
)


@dataclass
class PollRunRecord:
    job_name: str
    resource_type: str
    started_at: str
    finished_at: Optional[str] = None
    status: str = "running"
    error_message: Optional[str] = None
    points_written: int = 0


class MonitorRepository:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def save_metric_series(self, resource_type: str, resource_id: str, series: MetricSeries) -> int:
        rows = [
            (
                resource_type,
                resource_id,
                series.key,
                series.label,
                series.unit,
                point.timestamp.isoformat(),
                point.value,
                series.period,
            )
            for point in series.points
        ]
        if not rows:
            return 0

        with get_connection(self._settings) as connection:
            cursor = connection.executemany(
                """
                INSERT OR IGNORE INTO metric_points (
                    resource_type, resource_id, metric_key, metric_label, unit, timestamp, value, period
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            return cursor.rowcount or 0

    def get_historical_series(
        self,
        resource_type: str,
        resource_id: str,
        metric_key: str,
        start_time: str,
        end_time: str,
    ) -> Optional[HistoricalSeriesResponse]:
        with get_connection(self._settings) as connection:
            rows = connection.execute(
                """
                SELECT metric_label, unit, timestamp, value
                FROM metric_points
                WHERE resource_type = ?
                  AND resource_id = ?
                  AND metric_key = ?
                  AND timestamp >= ?
                  AND timestamp <= ?
                ORDER BY timestamp ASC
                """,
                (resource_type, resource_id, metric_key, start_time, end_time),
            ).fetchall()

        if not rows:
            return None

        points = [
            TimePoint(timestamp=row["timestamp"], value=row["value"])
            for row in rows
        ]
        values = [point.value for point in points if point.value is not None]

        return HistoricalSeriesResponse(
            resourceType=resource_type,
            resourceId=resource_id,
            metricKey=metric_key,
            metricLabel=rows[0]["metric_label"],
            unit=rows[0]["unit"],
            startTime=start_time,
            endTime=end_time,
            points=points,
            latest=values[-1] if values else None,
            average=round(mean(values), 2) if values else None,
            peak=max(values) if values else None,
        )

    def compare_metric_windows(
        self,
        resource_type: str,
        resource_id: str,
        metric_key: str,
        current_start: str,
        current_end: str,
        previous_start: str,
        previous_end: str,
    ) -> Optional[MetricComparisonResponse]:
        current_series = self.get_historical_series(resource_type, resource_id, metric_key, current_start, current_end)
        previous_series = self.get_historical_series(resource_type, resource_id, metric_key, previous_start, previous_end)

        if current_series is None and previous_series is None:
            return None

        base_series = current_series or previous_series
        assert base_series is not None

        def build_summary(series: Optional[HistoricalSeriesResponse], start_time: str, end_time: str) -> MetricWindowSummary:
            if series is None:
                return MetricWindowSummary(
                    startTime=start_time,
                    endTime=end_time,
                    latest=None,
                    average=None,
                    peak=None,
                    pointCount=0,
                )

            return MetricWindowSummary(
                startTime=start_time,
                endTime=end_time,
                latest=series.latest,
                average=series.average,
                peak=series.peak,
                pointCount=len(series.points),
            )

        current_window = build_summary(current_series, current_start, current_end)
        previous_window = build_summary(previous_series, previous_start, previous_end)

        average_delta = None
        if current_window.average is not None and previous_window.average is not None:
            average_delta = round(current_window.average - previous_window.average, 2)

        peak_delta = None
        if current_window.peak is not None and previous_window.peak is not None:
            peak_delta = round(current_window.peak - previous_window.peak, 2)

        return MetricComparisonResponse(
            resourceType=resource_type,
            resourceId=resource_id,
            metricKey=metric_key,
            metricLabel=base_series.metric_label,
            unit=base_series.unit,
            currentWindow=current_window,
            previousWindow=previous_window,
            averageDelta=average_delta,
            peakDelta=peak_delta,
        )


class AlertRepository:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def save_event(
        self,
        resource_type: str,
        resource_id: str,
        metric_key: str,
        metric_label: str,
        threshold_value: float,
        current_value: float,
        triggered_at: str,
        notify_email: str,
        notify_status: str,
        message: str,
    ) -> None:
        with get_connection(self._settings) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO alert_events (
                    resource_type, resource_id, metric_key, metric_label, threshold_value, current_value,
                    triggered_at, notify_email, notify_status, message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resource_type,
                    resource_id,
                    metric_key,
                    metric_label,
                    threshold_value,
                    current_value,
                    triggered_at,
                    notify_email,
                    notify_status,
                    message,
                ),
            )

    def list_recent(self, limit: int = 20) -> list[AlertEventResponse]:
        with get_connection(self._settings) as connection:
            rows = connection.execute(
                """
                SELECT resource_id, metric_key, metric_label, threshold_value, current_value, triggered_at
                FROM alert_events
                ORDER BY triggered_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            AlertEventResponse(
                instanceId=row["resource_id"],
                metricKey=row["metric_key"],
                metricLabel=row["metric_label"],
                thresholdMbps=row["threshold_value"],
                currentValue=row["current_value"],
                timestamp=row["triggered_at"],
            )
            for row in rows
        ]


class PollRunRepository:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(self, record: PollRunRecord) -> int:
        with get_connection(self._settings) as connection:
            cursor = connection.execute(
                """
                INSERT INTO poll_runs (job_name, resource_type, started_at, finished_at, status, error_message, points_written)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.job_name,
                    record.resource_type,
                    record.started_at,
                    record.finished_at,
                    record.status,
                    record.error_message,
                    record.points_written,
                ),
            )
            return int(cursor.lastrowid)

    def update(
        self,
        run_id: int,
        *,
        finished_at: str,
        status: str,
        error_message: Optional[str],
        points_written: int,
    ) -> None:
        with get_connection(self._settings) as connection:
            connection.execute(
                """
                UPDATE poll_runs
                SET finished_at = ?, status = ?, error_message = ?, points_written = ?
                WHERE id = ?
                """,
                (finished_at, status, error_message, points_written, run_id),
            )
