"use client";

import { BUCKETS } from "@/lib/types";
import type { Attribution } from "@/lib/types";

/**
 * The learner's answer *is* this component.
 *
 * They split the wall clock into buckets and pin the frames that justify each
 * one. Both halves are graded: the split against a waterfall our parser derived
 * from the capture, and every pin against the role that frame actually plays.
 * A right number backed by the wrong frame does not pass — which is the habit
 * the whole mission exists to build.
 */
export function LatencyWaterfall({
  totalMs,
  value,
  onChange,
  activeBucket,
  onActiveBucket,
  truth,
  readOnly = false,
}: {
  totalMs: number;
  value: Attribution;
  onChange: (next: Attribution) => void;
  activeBucket: string;
  onActiveBucket: (bucket: string) => void;
  truth?: { buckets: Record<string, number>; detail?: Record<string, any> };
  readOnly?: boolean;
}) {
  const assigned = Object.values(value.allocations).reduce((a, b) => a + (b || 0), 0);
  const remaining = Math.max(0, totalMs - assigned);
  const over = assigned > totalMs * 1.02;

  const setMs = (bucket: string, ms: number) =>
    onChange({
      ...value,
      allocations: { ...value.allocations, [bucket]: Math.max(0, Math.round(ms * 10) / 10) },
    });

  const removePin = (bucket: string, frame: number) =>
    onChange({
      ...value,
      pins: { ...value.pins, [bucket]: (value.pins[bucket] ?? []).filter((f) => f !== frame) },
    });

  return (
    <div className="flex flex-col gap-3">
      {/* running total */}
      <div className="panel p-3.5">
        <div className="flex items-baseline justify-between mb-2">
          <span className="text-[12.5px] font-medium">时间预算</span>
          <span className="mono text-[11.5px] muted">
            已分配 {assigned.toFixed(1)} / 总计 {totalMs.toFixed(1)} ms
          </span>
        </div>
        <div
          className="h-3 rounded-full overflow-hidden flex"
          style={{ background: "var(--panel-2)" }}
        >
          {BUCKETS.map((bucket) => {
            const ms = value.allocations[bucket.id] || 0;
            if (ms <= 0) return null;
            return (
              <div
                key={bucket.id}
                title={`${bucket.label} ${ms.toFixed(1)} ms`}
                style={{
                  width: `${Math.min(100, (ms / totalMs) * 100)}%`,
                  background: bucket.color,
                  transition: "width .25s cubic-bezier(.22,1,.36,1)",
                }}
              />
            );
          })}
        </div>
        <p className="text-[11px] mt-1.5" style={{ color: over ? "var(--color-bad-500)" : "var(--muted)" }}>
          {over
            ? "分配总量已经超过整次加载的时长了，回头看看哪一段被重复计算了。"
            : `还剩 ${remaining.toFixed(1)} ms 未归因（少量零散间隙是正常的）。`}
        </p>
      </div>

      {/* buckets */}
      {BUCKETS.map((bucket) => {
        const ms = value.allocations[bucket.id] || 0;
        const pins = value.pins[bucket.id] ?? [];
        const isActive = activeBucket === bucket.id && !readOnly;
        const verdict = truth?.detail?.buckets?.[bucket.id];

        return (
          <div
            key={bucket.id}
            data-testid={`bucket-${bucket.id}`}
            className="panel p-3.5 transition-shadow"
            style={{
              borderColor: isActive ? bucket.color : "var(--line)",
              boxShadow: isActive ? `0 0 0 3px color-mix(in oklab, ${bucket.color} 16%, transparent)` : undefined,
            }}
          >
            <div className="flex items-center gap-2.5">
              <span
                className="w-2.5 h-2.5 rounded-sm shrink-0"
                style={{ background: bucket.color }}
              />
              <span className="text-[13px] font-medium flex-1">{bucket.label}</span>

              {truth ? (
                <span className="mono text-[11.5px]">
                  <span style={{ color: verdict?.within_tolerance ? "var(--color-ok-500)" : "var(--color-bad-500)" }}>
                    {ms.toFixed(1)}
                  </span>
                  <span className="muted"> / {(truth.buckets[bucket.id] ?? 0).toFixed(1)} ms</span>
                </span>
              ) : (
                <div className="flex items-center gap-1.5">
                  <input
                    type="number"
                    data-testid={`ms-${bucket.id}`}
                    min={0}
                    step={1}
                    value={ms || ""}
                    disabled={readOnly}
                    onChange={(e) => setMs(bucket.id, Number(e.target.value))}
                    placeholder="0"
                    className="mono w-20 h-8 px-2 text-[12.5px] text-right rounded-[8px] outline-none border"
                    style={{ background: "var(--panel-2)", borderColor: "var(--line)" }}
                  />
                  <span className="mono text-[11px] muted">ms</span>
                </div>
              )}
            </div>

            {!truth && (
              <input
                type="range"
                min={0}
                max={Math.round(totalMs)}
                step={1}
                value={ms}
                disabled={readOnly}
                onChange={(e) => setMs(bucket.id, Number(e.target.value))}
                className="w-full mt-2.5 accent-current"
                style={{ accentColor: bucket.color }}
              />
            )}

            <div className="flex items-center gap-2 mt-2.5 flex-wrap">
              <button
                data-testid={`pin-${bucket.id}`}
                disabled={readOnly}
                onClick={() => onActiveBucket(bucket.id)}
                className="text-[11px] px-2 py-1 rounded-[7px] border transition-colors disabled:opacity-50"
                style={{
                  borderColor: isActive ? bucket.color : "var(--line)",
                  color: isActive ? bucket.color : "var(--muted)",
                }}
              >
                {isActive ? "← 在时空图里点选证据帧" : "钉证据帧"}
              </button>

              {pins.map((frame) => {
                const bad = verdict?.invalid_pins?.includes(frame);
                return (
                  <span
                    key={frame}
                    className="mono text-[11px] px-1.5 py-0.5 rounded inline-flex items-center gap-1"
                    style={{
                      background: `color-mix(in oklab, ${bucket.color} 14%, transparent)`,
                      color: bad ? "var(--color-bad-500)" : bucket.color,
                      textDecoration: bad ? "line-through" : undefined,
                    }}
                  >
                    #{frame}
                    {!readOnly && !truth && (
                      <button
                        onClick={() => removePin(bucket.id, frame)}
                        className="opacity-60 hover:opacity-100"
                        aria-label={`移除第 ${frame} 帧`}
                      >
                        ×
                      </button>
                    )}
                  </span>
                );
              })}

              {!pins.length && (
                <span className="text-[11px] muted">还没有钉证据帧</span>
              )}
            </div>

            {verdict && !verdict.within_tolerance && (
              <p className="text-[11.5px] mt-2" style={{ color: "var(--color-bad-500)" }}>
                差了 {verdict.delta_ms > 0 ? "+" : ""}
                {verdict.delta_ms} ms
              </p>
            )}
            {verdict?.invalid_pins?.length > 0 && (
              <p className="text-[11.5px] mt-1" style={{ color: "var(--color-bad-500)" }}>
                第 {verdict.invalid_pins.join("、")} 帧不承担这个角色。
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
