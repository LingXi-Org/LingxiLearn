"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Mission, Pack, SessionListItem } from "@/lib/types";

const LEARNER_KEY = "lingxilearn.learner";

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
      const learnerId = window.localStorage.getItem(LEARNER_KEY);
      if (learnerId) {
        const history = await api.mastery(learnerId);
        setSessions(history.sessions);
      } else {
        setSessions([]);
      }
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
    const learnerId = window.localStorage.getItem(LEARNER_KEY) ?? "";
    const created = await api.createSession(missionId, packId, learnerId);
    window.localStorage.setItem(LEARNER_KEY, created.learner_id);
    return created;
  }, []);

  const createAgentTask = useCallback(async (prompt: string) => {
    const learnerId = window.localStorage.getItem(LEARNER_KEY) ?? "";
    const created = await api.createAgentTask(prompt, learnerId);
    window.localStorage.setItem(LEARNER_KEY, created.learner_id);
    return created;
  }, []);

  return { packs, sessions, missionById, brain, error, loading, refresh, createSession, createAgentTask };
}
