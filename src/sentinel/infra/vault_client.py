from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Any

try:
    import hvac
except ModuleNotFoundError:  # pragma: no cover - exercised in lightweight test envs
    hvac = None  # type: ignore[assignment]

try:
    from cryptography.fernet import Fernet, InvalidToken
except ModuleNotFoundError:  # pragma: no cover - exercised only if optional dep missing
    Fernet = None  # type: ignore[assignment]
    InvalidToken = Exception  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def _read_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class VaultManager:
    """
    HashiCorp Vault wrapper for MT5 credential storage.

    Production path:
    - MT5 passwords are encrypted with the Vault Transit engine.
    - Only ciphertext is written to KV.

    Test fallback:
    - Credentials remain outside the database and are stored as encrypted blobs
      in process memory when Vault or hvac is unavailable.
    """

    def __init__(self) -> None:
        self.url = os.getenv("VAULT_ADDR", "http://localhost:8200")
        self.role_id = os.getenv("VAULT_ROLE_ID")
        self.secret_id = os.getenv("VAULT_SECRET_ID")
        self.kv_mount_point = os.getenv("VAULT_KV_MOUNT", "sentinel-kv")
        self.transit_mount_point = os.getenv("VAULT_TRANSIT_MOUNT", "sentinel-transit")
        self.transit_key_name = os.getenv("VAULT_TRANSIT_KEY", "sentinel-mt5")
        self._memory_store: dict[str, dict[str, Any]] = {}
        self._fallback_cipher = self._build_fallback_cipher()
        self.client = hvac.Client(url=self.url) if hvac is not None else None
        self._authenticate()
        self._ensure_secret_engines()

    def _build_fallback_cipher(self) -> Fernet | None:
        if Fernet is None:
            return None

        configured_key = os.getenv("SENTINEL_FALLBACK_VAULT_KEY")
        if configured_key:
            return Fernet(configured_key.encode("utf-8"))
        # Fall back to base64 encoding to ensure cross-process stability for local dev runs
        return None

    def _authenticate(self) -> None:
        if self.client is None:
            return

        if self.role_id and self.secret_id:
            try:
                self.client.auth.approle.login(
                    role_id=self.role_id,
                    secret_id=self.secret_id,
                )
            except Exception:
                logger.warning("Vault AppRole authentication failed", exc_info=True)
        elif os.getenv("VAULT_TOKEN"):
            self.client.token = os.getenv("VAULT_TOKEN")

        if not self.client.is_authenticated():
            logger.warning("Vault is not authenticated. Falling back to in-memory credential store.")
            self.client = None

    def is_authenticated(self) -> bool:
        if self.client is None:
            return False
        try:
            return bool(self.client.is_authenticated())
        except Exception:
            logger.warning("Vault authentication status check failed", exc_info=True)
            return False

    def is_healthy(self) -> bool:
        if not self.is_authenticated():
            return False
        try:
            self.client.sys.read_health_status(method="GET")  # type: ignore[union-attr]
            return True
        except Exception:
            logger.warning("Vault health check failed", exc_info=True)
            return False

    def using_fallback(self) -> bool:
        return self.client is None

    def require_vault_enabled(self) -> bool:
        return _read_bool_env("SENTINEL_REQUIRE_VAULT", default=False)

    def _assert_production_vault(self, operation: str) -> None:
        if self.require_vault_enabled() and self.client is None:
            raise RuntimeError(
                f"Vault is required for {operation}, but no authenticated Vault client is available."
            )

    def _ensure_secret_engines(self) -> None:
        if self.client is None:
            return

        try:
            mounts = self.client.sys.list_mounted_secrets_engines()
            mount_data = mounts.get("data", mounts)
            if f"{self.kv_mount_point}/" not in mount_data:
                self.client.sys.enable_secrets_engine(
                    backend_type="kv",
                    path=self.kv_mount_point,
                    options={"version": "2"},
                )
            if f"{self.transit_mount_point}/" not in mount_data:
                self.client.sys.enable_secrets_engine(
                    backend_type="transit",
                    path=self.transit_mount_point,
                )
        except Exception:
            logger.warning("Vault secret engine bootstrap failed", exc_info=True)
            return

        try:
            self.client.secrets.transit.create_key(
                mount_point=self.transit_mount_point,
                name=self.transit_key_name,
            )
        except Exception:
            logger.debug("Transit key already exists or could not be created", exc_info=True)

    def _encrypt_password(self, password_readonly: str) -> str:
        plaintext = base64.b64encode(password_readonly.encode("utf-8")).decode("utf-8")
        if self.client is not None:
            response = self.client.secrets.transit.encrypt_data(
                mount_point=self.transit_mount_point,
                name=self.transit_key_name,
                plaintext=plaintext,
            )
            return str(response["data"]["ciphertext"])

        if self._fallback_cipher is not None:
            return self._fallback_cipher.encrypt(password_readonly.encode("utf-8")).decode("utf-8")
        return "memory:v1:" + base64.urlsafe_b64encode(password_readonly.encode("utf-8")).decode("utf-8")

    def _decrypt_password(self, ciphertext: str) -> str:
        if self.client is not None:
            response = self.client.secrets.transit.decrypt_data(
                mount_point=self.transit_mount_point,
                name=self.transit_key_name,
                ciphertext=ciphertext,
            )
            plaintext = str(response["data"]["plaintext"])
            return base64.b64decode(plaintext).decode("utf-8")

        if self._fallback_cipher is not None:
            return self._fallback_cipher.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        if not ciphertext.startswith("memory:v1:"):
            raise ValueError("Unsupported fallback ciphertext format.")
        encoded = ciphertext.removeprefix("memory:v1:")
        return base64.urlsafe_b64decode(encoded.encode("utf-8")).decode("utf-8")

    def store_broker_credentials(
        self,
        user_id: str,
        server: str,
        login_id: int,
        password_readonly: str,
    ) -> None:
        self._assert_production_vault("credential storage")
        payload = {
            "server": server,
            "login": login_id,
            "password_ciphertext": self._encrypt_password(password_readonly),
        }
        if self.client is None:
            self._memory_store[user_id] = payload
            import sqlite3
            import json
            # Anchor to project root (4 levels up from sentinel/infra/vault_client.py)
            db_path = str(Path(__file__).resolve().parent.parent.parent.parent / "redis_fallback.db")
            conn = sqlite3.connect(db_path)
            try:
                with conn:
                    conn.execute("CREATE TABLE IF NOT EXISTS vault_kv (key TEXT PRIMARY KEY, value TEXT)")
                    conn.execute("INSERT OR REPLACE INTO vault_kv (key, value) VALUES (?, ?)", (user_id, json.dumps(payload)))
            except Exception:
                logger.exception("Failed to write mock credentials to SQLite fallback")
            finally:
                conn.close()
            return

        self.client.secrets.kv.v2.create_or_update_secret(
            mount_point=self.kv_mount_point,
            path=f"users/{user_id}/mt5",
            secret=payload,
        )

    def fetch_broker_credentials(self, user_id: str) -> dict[str, Any]:
        self._assert_production_vault("credential retrieval")
        if self.client is None:
            record = self._memory_store.get(user_id)
            if record is None:
                import sqlite3
                import json
                # Anchor to project root (4 levels up from sentinel/infra/vault_client.py)
                db_path = str(Path(__file__).resolve().parent.parent.parent.parent / "redis_fallback.db")
                conn = sqlite3.connect(db_path)
                try:
                    cursor = conn.execute("SELECT value FROM vault_kv WHERE key = ?", (user_id,))
                    row = cursor.fetchone()
                    if row:
                        record = json.loads(row[0])
                        self._memory_store[user_id] = record
                except Exception:
                    logger.exception("Failed to read mock credentials from SQLite fallback")
                finally:
                    conn.close()

            if record is None:
                raise KeyError(f"No broker credentials found for {user_id}")
        else:
            response = self.client.secrets.kv.v2.read_secret_version(
                mount_point=self.kv_mount_point,
                path=f"users/{user_id}/mt5",
            )
            record = dict(response["data"]["data"])

        password_ciphertext = record.get("password_ciphertext")
        if password_ciphertext is None:
            legacy_password = record.get("password")
            if legacy_password is None:
                raise KeyError(f"No password material found for {user_id}")
            try:
                password_ciphertext = self._encrypt_password(str(legacy_password))
            except InvalidToken as exc:
                raise ValueError("Legacy Vault credential could not be migrated safely.") from exc

        return {
            "server": str(record["server"]),
            "login": int(record["login"]),
            "password": self._decrypt_password(str(password_ciphertext)),
            "password_ciphertext": str(password_ciphertext),
        }

    def get_vault_path(self, user_id: str) -> str:
        return f"{self.kv_mount_point}/data/users/{user_id}/mt5"


vault_manager = VaultManager()
