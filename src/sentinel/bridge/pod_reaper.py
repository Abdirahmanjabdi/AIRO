"""
Sentinel MT5 Pod Reaper Daemon
==============================
Periodically checks the sentinel-users namespace for MT5 client pods.
If a pod has no active presence heartbeat in Redis, it is reaped.
"""

import asyncio
import datetime
import json
import logging
import os
import subprocess

from sentinel.infra.redis_cache import cache_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("pod_reaper")

NAMESPACE = os.getenv("SENTINEL_USERS_NAMESPACE", "sentinel-users")
REAP_INTERVAL_SECONDS = int(os.getenv("REAP_INTERVAL", "60"))

# Check if kubernetes client is installed
try:
    from kubernetes import client, config

    k8s_sdk = True
except ImportError:
    k8s_sdk = False


def get_k8s_client():
    if not k8s_sdk:
        return None
    try:
        config.load_incluster_config()
    except Exception:
        try:
            config.load_kube_config()
        except Exception:
            return None
    return client.CoreV1Api()


async def reap_stalled_pods():
    logger.info("Initializing pod reaper sweep in namespace: %s", NAMESPACE)

    # Initialize cache manager
    try:
        if not await cache_manager.ping():
            logger.error(
                "Redis is offline. Skipping reap sweep to prevent accidental pod deletion."
            )
            return
    except Exception as exc:
        logger.error("Failed to connect to Redis: %s. Skipping sweep.", exc)
        return

    k8s_api = get_k8s_client()
    pods_to_check = []

    if k8s_api:
        try:
            ret = k8s_api.list_namespaced_pod(NAMESPACE, label_selector="sentinel-user-id")
            for pod in ret.items:
                user_id = pod.metadata.labels.get("sentinel-user-id")
                pod_name = pod.metadata.name
                created_at = pod.metadata.creation_timestamp
                age = (datetime.datetime.now(datetime.UTC) - created_at).total_seconds()
                if age < 300:  # 5 minutes grace period
                    continue
                pods_to_check.append((user_id, pod_name))
        except Exception as exc:
            logger.error("Failed to query pods via K8s SDK: %s. Trying fallback to kubectl...", exc)
            k8s_api = None

    if not k8s_api:
        # Fallback to kubectl command line
        try:
            cmd = [
                "kubectl",
                "get",
                "pods",
                "-n",
                NAMESPACE,
                "-l",
                "sentinel-user-id",
                "-o",
                "json",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            for item in data.get("items", []):
                metadata = item.get("metadata", {})
                labels = metadata.get("labels", {})
                user_id = labels.get("sentinel-user-id")
                pod_name = metadata.get("name")
                created_str = metadata.get("creationTimestamp")
                try:
                    created_at = datetime.datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                    age = (datetime.datetime.now(datetime.UTC) - created_at).total_seconds()
                except Exception:
                    age = 300
                if age < 300:
                    continue
                pods_to_check.append((user_id, pod_name))
        except Exception as exc:
            logger.error("Fallback kubectl execution failed: %s. No pods reaped this sweep.", exc)
            return

    for user_id, pod_name in pods_to_check:
        if not user_id:
            continue
        try:
            has_heartbeat = await cache_manager.ping_state(user_id)
            if not has_heartbeat:
                logger.warning(
                    "Reaping stalled/orphaned pod %s for user %s (heartbeat expired).",
                    pod_name,
                    user_id,
                )
                if k8s_api:
                    k8s_api.delete_namespaced_pod(name=pod_name, namespace=NAMESPACE)
                else:
                    cmd = ["kubectl", "delete", "pod", pod_name, "-n", NAMESPACE, "--now"]
                    subprocess.run(cmd, capture_output=True, text=True, check=True)
                logger.info("Successfully deleted pod: %s", pod_name)
        except Exception as exc:
            logger.error("Error checking or reaping pod %s: %s", pod_name, exc)


async def main():
    logger.info("Starting Sentinel MT5 Pod Reaper daemon...")
    while True:
        try:
            await reap_stalled_pods()
        except Exception as exc:
            logger.error("Error in pod reaper loop: %s", exc)
        await asyncio.sleep(REAP_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
