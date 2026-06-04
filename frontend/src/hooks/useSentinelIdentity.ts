import { useEffect, useState } from "react";

export interface SentinelIdentity {
  userId: string;
  brokerServer: string;
  accountId: string;
  apiKey: string;
}

const STORAGE_KEY = "sentinel-zero.identity";
const MAX_AGE_MS = 1000 * 60 * 60 * 23;

interface StoredIdentity {
  identity: SentinelIdentity;
  savedAt: number;
}

function readStoredIdentity(): SentinelIdentity | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as StoredIdentity | SentinelIdentity;
    const identity = "identity" in parsed ? parsed.identity : parsed;
    const savedAt = "savedAt" in parsed ? parsed.savedAt : 0;

    if (!identity.userId || !identity.brokerServer || !identity.accountId || !identity.apiKey) {
      return null;
    }

    if (savedAt && Date.now() - savedAt > MAX_AGE_MS) {
      window.localStorage.removeItem(STORAGE_KEY);
      return null;
    }

    return identity;
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
      const payload: StoredIdentity = {
        identity,
        savedAt: Date.now(),
      };
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
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
