import { useEffect, useRef, useState } from "react";

// Sim apps/sim/hooks/use-smooth-text.ts @ ce2dff3c.
const SNAP = /[\s.,!?;:)\]]/;
const DRAIN_HORIZON_MS = 400;
const MIN_CPS = 45;
const MAX_CPS = 2400;
const drainRate = (remaining: number) => Math.min(MAX_CPS, Math.max(MIN_CPS, (remaining * 1000) / DRAIN_HORIZON_MS));
function nextIndex(text: string, start: number, budget: number): number {
  const limit = Math.min(text.length, start + Math.floor(budget));
  for (let index = limit; index > start; index -= 1) if (SNAP.test(text[index - 1] ?? "")) return index;
  return limit >= Math.min(text.length, start + 24) ? limit : start;
}
export const RESUME_SKIP_THRESHOLD = 60;

export function useSmoothText(content: string, isStreaming: boolean): string {
  const [revealed, setRevealed] = useState(() => isStreaming && content.length <= RESUME_SKIP_THRESHOLD ? 0 : content.length);
  const contentRef = useRef(content);
  const revealedRef = useRef(revealed);
  const rafRef = useRef<number | null>(null);
  const budgetRef = useRef(0);
  const lastFrameAtRef = useRef(0);
  contentRef.current = content;
  const hasBacklog = revealed < content.length;
  useEffect(() => {
    const run = (now: number) => {
      rafRef.current = null;
      const target = contentRef.current.length;
      if (revealedRef.current > target) { revealedRef.current = target; budgetRef.current = 0; setRevealed(target); }
      const current = revealedRef.current;
      if (current >= target) return;
      const delta = Math.min(now - lastFrameAtRef.current, 100);
      lastFrameAtRef.current = now;
      budgetRef.current += (drainRate(target - current) * delta) / 1000;
      const next = nextIndex(contentRef.current, current, budgetRef.current);
      if (next > current) { budgetRef.current -= next - current; revealedRef.current = next; setRevealed(next); }
      if (revealedRef.current < target) rafRef.current = requestAnimationFrame(run);
    };
    if (hasBacklog && rafRef.current === null) { lastFrameAtRef.current = performance.now(); rafRef.current = requestAnimationFrame(run); }
  });
  useEffect(() => () => { if (rafRef.current !== null) cancelAnimationFrame(rafRef.current); }, []);
  return revealed >= content.length ? content : content.slice(0, revealed);
}
