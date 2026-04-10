from __future__ import annotations

import os
import tempfile
from pathlib import Path

try:
    import boto3
    from botocore.client import BaseClient
    from botocore.exceptions import ClientError
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal test envs
    boto3 = None  # type: ignore[assignment]
    BaseClient = object  # type: ignore[assignment,misc]
    ClientError = Exception  # type: ignore[assignment]


class ModelStore:
    """S3/MinIO-backed storage for per-user joblib models."""

    def __init__(self) -> None:
        endpoint_url = os.getenv("S3_ENDPOINT")
        self.bucket = os.getenv("S3_BUCKET", "sentinel-models")
        self.region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        self._memory_models: dict[str, bytes] = {}
        self.client: BaseClient | None
        if boto3 is None:
            self.client = None
        else:
            self.client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                region_name=self.region,
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            )

    def ensure_bucket(self) -> None:
        if self.client is None:
            return
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            params: dict[str, object] = {"Bucket": self.bucket}
            if self.region != "us-east-1":
                params["CreateBucketConfiguration"] = {
                    "LocationConstraint": self.region,
                }
            self.client.create_bucket(**params)

    def build_model_key(self, user_id: str) -> str:
        return f"models/{user_id}/brain_v5.joblib"

    def upload_model(self, user_id: str, path: Path) -> str:
        key = self.build_model_key(user_id)
        if self.client is None:
            self._memory_models[key] = path.read_bytes()
            return key

        self.client.upload_file(str(path), self.bucket, key)
        return key

    def download_model_to_temp(self, key: str) -> Path:
        suffix = Path(key).suffix or ".joblib"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
            temp_path = Path(handle.name)
        if self.client is None:
            temp_path.write_bytes(self._memory_models[key])
            return temp_path

        self.client.download_file(self.bucket, key, str(temp_path))
        return temp_path

    def model_exists(self, key: str) -> bool:
        if self.client is None:
            return key in self._memory_models
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False


model_store = ModelStore()
