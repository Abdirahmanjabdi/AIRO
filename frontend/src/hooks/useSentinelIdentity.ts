import { useEffect, useState } from "react";

export interface SentinelIdentity {
  userId: string;
  brokerServer: string;
  accountId: string;
}

const STORAGE_KEY = "sentinel-zero.identity";

function readStoredIdentity(): SentinelIdentity | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as SentinelIdentity;
    if (!parsed.userId || !parsed.brokerServer || !parsed.accountId) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function useSentinelIdentity() {
  const [identity, setIdentityState] = useState<SentinelIdentity | null>(() => readStoredIdentity());

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    if (identity) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(identity));
      return;
    }

    window.localStorage.removeItem(STORAGE_KEY);
  }, [identity]);

  return {
    identity,
    setIdentity(identityValue: SentinelIdentity) {
      setIdentityState(identityValue);
    },
    clearIdentity() {
      setIdentityState(null);
    },
  };
}
