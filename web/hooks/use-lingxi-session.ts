"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, subscribeEvents } from "@/lib/api";
import type { RunEvent, SessionSnapshot } from "@/lib/types";

export function useLingxiSession(sessionId: string) {
  const [session, setSession] = useState<SessionSnapshot | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [error, setError] = useState<string>();
  const [submitting, setSubmitting] = useState(false);
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refresh = useCallback(async () => {
    if (!sessionId) return;
    try {
      const snapshot = await api.session(sessionId);
      setSession(snapshot);
      setSubmitting(snapshot.status === "running");
      setError(undefined);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
      setSubmitting(false);
    }
  }, [sessionId]);

  useEffect(() => {
    setSession(null);
    setEvents([]);
    setError(undefined);
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!sessionId) return;
    return subscribeEvents(sessionId, (event) => {
      setEvents((current) => current.some((item) => item.sequence === event.sequence)
        ? current
        : [...current, event].sort((a, b) => a.sequence - b.sequence));
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
      refreshTimer.current = setTimeout(() => void refresh(), 160);
    }, { onEnd: () => void refresh() });
  }, [sessionId, refresh]);

  useEffect(() => {
    if (session?.status !== "running") return;
    const timer = setInterval(() => void refresh(), 1600);
    return () => clearInterval(timer);
  }, [session?.status, refresh]);

  useEffect(() => () => {
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
  }, []);

  const submit = useCallback(async (answer: unknown) => {
    setSubmitting(true);
    setError(undefined);
    try {
      await api.answer(sessionId, answer);
      setTimeout(() => void refresh(), 220);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
      setSubmitting(false);
      throw cause;
    }
  }, [refresh, sessionId]);

  return { session, events, error, submitting, submit, refresh };
}
