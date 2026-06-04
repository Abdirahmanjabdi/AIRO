from __future__ import annotations

import os
import tempfile
import uuid
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

try:
    import boto3
    from botocore.client import BaseClient
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal test envs
    boto3 = None  # type: ignore[assignment]
    BaseClient = object  # type: ignore[assignment,misc]

from sentinel.infra.db import list_behavioral_logs_for_export


class BehavioralDataLakeExporter:
    """Exports anonymized behavioral telemetry from Postgres to S3 Parquet."""

    def __init__(self) -> None:
        self.bucket = os.getenv("DATA_LAKE_BUCKET", os.getenv("S3_BUCKET", "sentinel-models"))
        self.prefix = os.getenv("DATA_LAKE_PREFIX", "behavioral_logs")
        self.region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        self.client: BaseClient | None
        if boto3 is None:
            self.client = None
        else:
            self.client = boto3.client(
                "s3",
                endpoint_url=os.getenv("S3_ENDPOINT"),
                region_name=self.region,
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            )

    async def export_day(
        self,
        session: AsyncSession,
        export_date: date | None = None,
    ) -> str | None:
        target_date = export_date or (date.today() - timedelta(days=1))
        logs = await list_behavioral_logs_for_export(session, target_date)
        if not logs:
            return None

        frame = pd.DataFrame(
            [
                {
                    "user_hash": log.user_hash,
                    "audit_id": log.audit_id,
                    "symbol": log.symbol,
                    "hour_decimal": log.hour_decimal,
                    "losing_streak": log.losing_streak,
                    "drawdown_state": log.drawdown_state,
                    "lot_deviation": log.lot_deviation,
                    "revenge_timer": log.revenge_timer,
                    "lots": log.lots,
                    "rr_ratio": log.rr_ratio,
                    "realized_vol_20": log.realized_vol_20,
                    "trend_momentum": log.trend_momentum,
                    "decision": log.decision,
                    "risk_score": log.risk_score,
                    "size_multiplier": log.size_multiplier,
                    "is_anomaly": log.is_anomaly,
                    "created_at": log.created_at.isoformat(),
                    "dt": target_date.isoformat(),
                }
                for log in logs
            ]
        )

        key = f"{self.prefix}/dt={target_date.isoformat()}/behavioral-{uuid.uuid4().hex}.parquet"

        with tempfile.NamedTemporaryFile(delete=False, suffix=".parquet") as handle:
            path = Path(handle.name)

        try:
            frame.to_parquet(path, index=False, engine="pyarrow")
            if self.client is None:
                return key
            self.client.upload_file(str(path), self.bucket, key)
            return key
        finally:
            path.unlink(missing_ok=True)


data_lake_exporter = BehavioralDataLakeExporter()
