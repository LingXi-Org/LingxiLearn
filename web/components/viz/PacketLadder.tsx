"use client";

import { useMemo } from "react";
import type { LadderData } from "@/lib/types";
import { ROLE_COLORS } from "@/lib/types";

/**
 * Time–space diagram of the capture.
 *
 * Time runs down the page on a **linear** scale, deliberately: the long empty
 * stretch where nothing moves is not noise to be compressed away, it is the
 * single most important thing in this capture. A student who sees that gap at
 * true scale has already half-solved the mission.
 */
export function PacketLadder({
  data,
  roles = {},
  selected,
  onSelect,
  highlight = [],
}: {
  data: LadderData;
  roles?: Record<string, string>;
  selected?: number;
  onSelect?: (frame: number) => void;
  highlight?: number[];
}) {
  const LEFT = 14;
  const RIGHT = 86;

  const layout = useMemo(() => {
    const hosts = data.hosts ?? [];
    const span = Math.max(data.span_ms || 1, 1);
    const pxPerMs = Math.min(1.6, Math.max(0.55, 620 / span));
    const height = Math.max(320, span * pxPerMs + 90);
    return { hosts, span, pxPerMs, height };
  }, [data]);

  const { hosts, pxPerMs, height } = layout;

  const x = (host: string) => {
    if (hosts.length <= 1) return 50;
    const index = Math.max(0, hosts.indexOf(host));
    return LEFT + (index * (RIGHT - LEFT)) / (hosts.length - 1);
  };
  const y = (ms: number) => 56 + ms * pxPerMs;

  /**
   * Labels are nudged apart, the geometry is not.
   *
   * The arrows stay exactly where their timestamps put them — that fidelity is
   * the whole point of a linear axis. Only the text is pushed down when it
   * would collide, so a burst of back-to-back frames stays readable without
   * lying about when they happened.
   */
  const labelY = useMemo(() => {
    const MIN_GAP = 13;
    const positions = new Map<number, number>();
    let previous = -Infinity;
    for (const arrow of data.arrows ?? []) {
      const wanted = y(arrow.t_ms) - 15;
      const placed = Math.max(wanted, previous + MIN_GAP);
      positions.set(arrow.frame, placed);
      previous = placed;
    }
    return positions;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, pxPerMs]);

  if (!hosts.length) return null;

  const ticks = niceTicks(data.span_ms || 1);
  const highlightSet = new Set(highlight);

  return (
    <div className="relative h-full overflow-auto">
      <svg
        viewBox={`0 0 100 ${height}`}
        preserveAspectRatio="none"
        className="w-full block"
        style={{ height }}
      >
        {/* time gridlines */}
        {ticks.map((ms) => (
          <line
            key={ms}
            x1={0}
            x2={100}
            y1={y(ms)}
            y2={y(ms)}
            stroke="var(--line)"
            strokeWidth={0.12}
            vectorEffect="non-scaling-stroke"
          />
        ))}

        {/* host lanes */}
        {hosts.map((host) => (
          <line
            key={host}
            x1={x(host)}
            x2={x(host)}
            y1={44}
            y2={height - 10}
            stroke="var(--line)"
            strokeWidth={1}
            vectorEffect="non-scaling-stroke"
          />
        ))}

        {/* arrows */}
        {data.arrows.map((arrow) => {
          const x1 = x(arrow.src);
          const x2 = x(arrow.dst);
          const yy = y(arrow.t_ms);
          const role = roles[String(arrow.frame)];
          const color = ROLE_COLORS[role] ?? "var(--color-ink-400)";
          const isSelected = selected === arrow.frame;
          const isHighlighted = highlightSet.has(arrow.frame);
          const dimmed = highlightSet.size > 0 && !isHighlighted && !isSelected;
          const dir = x2 > x1 ? 1 : -1;

          return (
            <g
              key={arrow.frame}
              onClick={() => onSelect?.(arrow.frame)}
              style={{ cursor: onSelect ? "pointer" : "default" }}
              opacity={dimmed ? 0.24 : 1}
            >
              {/* generous invisible hit area */}
              <rect x={Math.min(x1, x2)} y={yy - 7} width={Math.abs(x2 - x1)} height={14} fill="transparent" />
              <line
                x1={x1}
                x2={x2 - dir * 1.4}
                y1={yy}
                y2={yy}
                stroke={color}
                strokeWidth={isSelected ? 2.5 : 1.6}
                vectorEffect="non-scaling-stroke"
              />
              <polygon
                points={`${x2},${yy} ${x2 - dir * 1.6},${yy - 3.2} ${x2 - dir * 1.6},${yy + 3.2}`}
                fill={color}
              />
              {isSelected && (
                <circle cx={x1} cy={yy} r={1.1} fill={color} />
              )}
            </g>
          );
        })}
      </svg>

      {/* HTML overlays keep text unstretched despite the non-uniform viewBox */}
      <div className="absolute inset-0 pointer-events-none">
        {hosts.map((host) => (
          <div
            key={host}
            className="absolute mono text-[10.5px] px-1.5 py-0.5 rounded"
            style={{
              left: `${x(host)}%`,
              top: 12,
              transform: "translateX(-50%)",
              background: "var(--panel-2)",
              color: "var(--muted)",
              whiteSpace: "nowrap",
            }}
          >
            {host}
          </div>
        ))}

        {ticks.map((ms) => (
          <div
            key={ms}
            className="absolute mono text-[9.5px] muted"
            style={{ left: 2, top: y(ms) - 12 }}
          >
            {ms} ms
          </div>
        ))}

        {data.arrows.map((arrow) => {
          const isSelected = selected === arrow.frame;
          const isHighlighted = highlightSet.has(arrow.frame);
          const dimmed = highlightSet.size > 0 && !isHighlighted && !isSelected;
          const midpoint = (x(arrow.src) + x(arrow.dst)) / 2;
          return (
            <div
              key={arrow.frame}
              data-testid={`frame-label-${arrow.frame}`}
              onClick={() => onSelect?.(arrow.frame)}
              className="absolute mono text-[10px] whitespace-nowrap px-1 rounded pointer-events-auto"
              style={{
                left: `${midpoint}%`,
                top: labelY.get(arrow.frame) ?? y(arrow.t_ms) - 15,
                transform: "translateX(-50%)",
                opacity: dimmed ? 0.28 : 1,
                color: isSelected ? "var(--text)" : "var(--muted)",
                fontWeight: isSelected || isHighlighted ? 600 : 400,
                background: isSelected || isHighlighted ? "var(--panel-2)" : "var(--panel)",
                cursor: onSelect ? "pointer" : "default",
                zIndex: isSelected ? 3 : 1,
              }}
            >
              #{arrow.frame} {shorten(arrow.label)}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function shorten(label: string): string {
  return label.length > 42 ? `${label.slice(0, 40)}…` : label;
}

function niceTicks(span: number): number[] {
  const target = 8;
  const raw = span / target;
  const magnitude = 10 ** Math.floor(Math.log10(Math.max(raw, 1)));
  const step = [1, 2, 5, 10].map((m) => m * magnitude).find((s) => s >= raw) ?? magnitude * 10;
  const out: number[] = [];
  for (let ms = 0; ms <= span; ms += step) out.push(Math.round(ms));
  return out;
}
