"use client";

import { useCallback, useState } from "react";
import { appendMockTurn, createMockRun, type SimMockRun } from "@/lib/sim-mock";

export function useSimMock(initialPrompt: string) {
  const [run, setRun] = useState<SimMockRun>(() => createMockRun(initialPrompt));
  const send = useCallback((prompt: string) => {
    setRun((current) => appendMockTurn(current, prompt));
  }, []);
  return { run, send };
}
