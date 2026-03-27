import json
from collections.abc import Sequence
from datetime import datetime

from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.monitor.v20180724 import monitor_client, models

from app.config import Settings


class TencentMonitorClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._credential = credential.Credential(
            settings.tencent_secret_id,
            settings.tencent_secret_key,
        )
        self._client = monitor_client.MonitorClient(self._credential, settings.tencent_region)
        self._client.request.conn._session.trust_env = False

    def get_monitor_data(
        self,
        namespace: str,
        metric_name: str,
        dimensions: Sequence[dict[str, str]],
        period: int,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict]:
        request = models.GetMonitorDataRequest()
        request.Namespace = namespace
        request.MetricName = metric_name
        instance = models.Instance()
        instance.Dimensions = []
        for item in dimensions:
            dimension = models.Dimension()
            dimension.Name = item["Name"]
            dimension.Value = item["Value"]
            instance.Dimensions.append(dimension)
        request.Instances = [instance]
        request.Period = period
        request.StartTime = self._to_datetime_iso(start_time)
        request.EndTime = self._to_datetime_iso(end_time)

        try:
            response = self._client.GetMonitorData(request)
        except TencentCloudSDKException as exc:
            raise RuntimeError(f"Tencent Cloud monitor request failed: {exc}") from exc

        payload = json.loads(response.to_json_string())
        return payload.get("DataPoints") or []

    def _to_datetime_iso(self, value: datetime) -> str:
        return value.astimezone().isoformat(timespec="seconds")
