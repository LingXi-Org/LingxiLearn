"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Mission, Pack, SessionListItem } from "@/lib/types";

export function useCatalogue() {
  const [packs, setPacks] = useState<Pack[]>([]);
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [brain, setBrain] = useState<string>();
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [catalogue, health] = await Promise.all([api.packs(), api.health()]);
      setPacks(catalogue.packs);
      setBrain(health.brain);
      const history = await api.mastery();
      setSessions(history.sessions);
      setError(undefined);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const missionById = useMemo(() => {
    const map = new Map<string, Mission>();
    for (const pack of packs) for (const mission of pack.missions) map.set(mission.id, mission);
    return map;
  }, [packs]);

  const createSession = useCallback(async (missionId: string, packId: string) => {
    return api.createSession(missionId, packId);
  }, []);

  const createAgentTask = useCallback(async (prompt: string) => {
    return api.createAgentTask(prompt);
  }, []);

  return { packs, sessions, missionById, brain, error, loading, refresh, createSession, createAgentTask };
}
