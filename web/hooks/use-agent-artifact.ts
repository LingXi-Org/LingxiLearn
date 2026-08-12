"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export function useAgentArtifact(taskId: string | undefined, kind: "background" | "visual", enabled: boolean) {
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

    void api.fetchArtifact(api.agentArtifactUrl(taskId, kind))
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
  }, [enabled, kind, taskId]);

  return { content, loading, error };
}
