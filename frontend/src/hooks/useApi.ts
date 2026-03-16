// hooks/useApi.ts
"use client";
import useSWR from "swr";
import { useState, useEffect } from "react";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

async function fetcher(url: string) {
  const token = getToken();
  if (!token) throw new Error("No token");
  const res = await fetch(`${BASE_URL}${url}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 401) {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) throw new Error(`API error: ${res.status}`);
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
