"use client";

import { useMemo } from "react";
import type { Frame } from "@/lib/types";
import { ROLE_COLORS } from "@/lib/types";

/**
 * A frame, decoded.
 *
 * Every field shown here came out of our own parser, which is the point: when
 * the coach cites a sequence number, the learner can open the frame and check
 * it — and can open the same capture in Wireshark and check us.
 */
export function FrameInspector({
  frame,
  role,
  onClose,
}: {
  frame: Frame | null;
  role?: string;
  onClose?: () => void;
}) {
  if (!frame) return null;
  const color = role ? (ROLE_COLORS[role] ?? "var(--color-ink-400)") : "var(--color-ink-400)";

  return (
    <div className="panel overflow-hidden flex flex-col max-h-full">
      <header
        className="flex items-center gap-2 px-3.5 py-2.5 border-b shrink-0"
        style={{ borderColor: "var(--line)" }}
      >
        <span className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
        <span className="mono text-[12.5px] font-semibold">第 {frame.number} 帧</span>
        {role && (
          <span className="mono text-[10.5px] px-1.5 py-0.5 rounded" style={{ background: "var(--panel-2)", color }}>
            {role}
          </span>
        )}
        <span className="mono text-[10.5px] muted ml-auto">{frame.length} 字节</span>
        {onClose && (
          <button onClick={onClose} className="muted hover:opacity-70 text-[15px] leading-none px-1">
            ×
          </button>
        )}
      </header>

      <div className="overflow-auto p-3.5 flex flex-col gap-3">
        <p className="mono text-[11.5px]" style={{ color }}>
          {frame.summary}
        </p>

        {Object.entries(frame.layers).map(([name, fields]) => (
          <section key={name}>
            <h4 className="mono text-[10.5px] uppercase tracking-wide muted mb-1">{name}</h4>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
              {Object.entries(fields as Record<string, unknown>).map(([key, val]) => (
                <div key={key} className="contents">
                  <dt className="mono text-[11px] muted">{key}</dt>
                  <dd className="mono text-[11px] break-all">{format(val)}</dd>
                </div>
              ))}
            </dl>
          </section>
        ))}

        {frame.hex && <HexDump hex={frame.hex} />}
      </div>
    </div>
  );
}

function format(value: unknown): string {
  if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

function HexDump({ hex }: { hex: string }) {
  const rows = useMemo(() => {
    const bytes = hex.match(/.{2}/g) ?? [];
    const out: { offset: string; cells: string[]; ascii: string }[] = [];
    for (let i = 0; i < bytes.length; i += 16) {
      const slice = bytes.slice(i, i + 16);
      out.push({
        offset: i.toString(16).padStart(4, "0"),
        cells: slice,
        ascii: slice
          .map((b) => {
            const code = parseInt(b, 16);
            return code >= 32 && code < 127 ? String.fromCharCode(code) : ".";
          })
          .join(""),
      });
    }
    return out;
  }, [hex]);

  return (
    <section>
      <h4 className="mono text-[10.5px] uppercase tracking-wide muted mb-1">raw bytes</h4>
      <div className="mono text-[10.5px] leading-[1.6] overflow-x-auto">
        {rows.map((row) => (
          <div key={row.offset} className="flex gap-3 whitespace-pre">
            <span className="muted">{row.offset}</span>
            <span>{row.cells.join(" ").padEnd(47, " ")}</span>
            <span className="muted">{row.ascii}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
