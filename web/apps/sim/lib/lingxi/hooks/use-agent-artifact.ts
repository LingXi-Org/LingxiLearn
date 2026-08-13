"use client";

import { useEffect, useState } from "react";
import { api } from '@/lib/lingxi/api'

export function useAgentArtifact(
  taskId: string | undefined,
  kind: "lesson-intro" | "lecture-deck" | "visual",
  enabled: boolean,
  version?: string | null,
) {
  const [content, setContent] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    if (!taskId || !enabled) return;
    let cancelled = false;
    let objectUrl: string | undefined;
    setLoading(true);
    setError(undefined);
    setContent(undefined);

    const baseUrl = api.agentArtifactUrl(taskId, kind)
    const url = version ? `${baseUrl}?v=${encodeURIComponent(version)}` : baseUrl
    void api.fetchArtifact(url)
      .then(async (blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setContent(objectUrl);
      })
      .catch((cause) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [enabled, kind, taskId, version]);

  return { content, loading, error };
}
