// hooks/useApi.ts
"use client";
import useSWR from "swr";
import { useState, useEffect } from "react";
import { toAppError } from "@/lib/errors";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

/** Id of the signed-in user, from the stored session; "" when signed out or unreadable. */
export function currentUserKey(): string {
  if (typeof window === "undefined") return "";
  try {
    const user = JSON.parse(localStorage.getItem("user") || "null");
    return user && user.id != null ? String(user.id) : "";
  } catch {
    return "";
  }
}

/** SWR key for a path: scoped to the user so two logins in one tab never share an entry (B-44). */
export function apiKey(path: string, userKey: string): [string, string] {
  return [path, userKey];
}

async function fetcher([url]: [string, string]) {
  const token = getToken();
  if (!token) throw new Error("No token");

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${url}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch (cause) {
    throw toAppError({ code: "ERR_NETWORK", message: String(cause) });
  }

  if (res.status === 401) {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.href = `/login?next=${next}`;
    throw toAppError({ response: { status: 401 } });
  }

  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw toAppError({
      response: {
        status: res.status,
        data,
        headers: { "x-request-id": res.headers.get("X-Request-ID") ?? "" },
      },
    });
  }

  return res.json();
}

export interface UseApiOptions {
  /** Poll every n ms (B-16: dashboard KPIs, system status, the bell). Off by default. */
  refreshInterval?: number;
}

export function useApi<T = Record<string, unknown>>(path: string | null, options: UseApiOptions = {}) {
  const [userKey, setUserKey] = useState<string | null>(null);

  useEffect(() => {
    setUserKey(localStorage.getItem("token") ? currentUserKey() : "");
  }, []);

  return useSWR<T>(userKey && path ? apiKey(path, userKey) : null, fetcher, {
    revalidateOnFocus: false,
    errorRetryCount: 0,
    shouldRetryOnError: false,
    refreshInterval: options.refreshInterval ?? 0,
    // One request per key per mount burst: the dashboard mounts four readers of
    // /classify/info at once and used to fire four requests.
    dedupingInterval: 5_000,
  });
}
