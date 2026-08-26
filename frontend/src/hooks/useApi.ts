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

async function fetcher(url: string) {
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

export function useApi<T = Record<string, unknown>>(path: string | null) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setReady(!!localStorage.getItem("token"));
  }, []);

  return useSWR<T>(ready ? path : null, fetcher, {
    revalidateOnFocus: false,
    errorRetryCount: 0,
    shouldRetryOnError: false,
  });
}
