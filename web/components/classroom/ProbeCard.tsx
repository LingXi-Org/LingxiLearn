"use client";

import { useState } from "react";
import type { Item } from "@/lib/types";

/** Pre-test and post-test. The same component; only the framing changes. */
export function ProbeCard({
  title,
  items,
  kind,
  onSubmit,
  busy,
}: {
  title: string;
  items: Item[];
  kind: "probe" | "verify";
  onSubmit: (answers: Record<string, { choice: string }>) => void;
  busy?: boolean;
}) {
  const [picked, setPicked] = useState<Record<string, string>>({});
  const complete = items.every((item) => picked[item.id]);

  return (
    <div className="max-w-2xl mx-auto w-full p-6 flex flex-col gap-5">
      <header>
        <h2 className="text-[20px] font-semibold tracking-tight">{title}</h2>
        <p className="text-[13px] muted mt-1.5 leading-relaxed">
          {kind === "probe"
            ? "答错没有关系——这几题只是用来决定接下来带你走哪条路。答对的部分会被跳过。"
            : "最后确认一下：刚才那些证据，你是不是真的读懂了。"}
        </p>
      </header>

      {items.map((item, index) => (
        <article
          key={item.id}
          className="panel p-4 rise"
          style={{ animationDelay: `${index * 50}ms` }}
        >
          <div className="flex items-baseline gap-2 mb-3">
            <span className="mono text-[11px] muted shrink-0">{index + 1}</span>
            <p className="text-[14px] leading-relaxed flex-1">{item.prompt}</p>
          </div>
          <div className="flex flex-col gap-1.5">
            {item.choices.map((choice) => {
              const chosen = picked[item.id] === choice.value;
              return (
                <button
                  key={choice.value}
                  data-testid={`item-${item.id}-${choice.value}`}
                  onClick={() => setPicked((prev) => ({ ...prev, [item.id]: choice.value }))}
                  className="flex items-start gap-2.5 text-left px-3 py-2 rounded-[9px] border transition-colors"
                  style={{
                    borderColor: chosen ? "var(--color-accent-500)" : "var(--line)",
                    background: chosen
                      ? "color-mix(in oklab, var(--color-accent-500) 8%, transparent)"
                      : "transparent",
                  }}
                >
                  <span
                    className="mono text-[11px] mt-0.5 shrink-0"
                    style={{ color: chosen ? "var(--color-accent-600)" : "var(--muted)" }}
                  >
                    {choice.value.toUpperCase()}
                  </span>
                  <span className="text-[13.5px] leading-relaxed">{choice.label}</span>
                </button>
              );
            })}
          </div>
          <span className="mono text-[10px] muted mt-2.5 block">{item.concept}</span>
        </article>
      ))}

      <button
        data-testid="submit-items"
        onClick={() =>
          onSubmit(
            Object.fromEntries(items.map((i) => [i.id, { choice: picked[i.id] ?? "" }])),
          )
        }
        disabled={!complete || busy}
        className="h-11 rounded-[10px] text-white font-medium text-[14px] disabled:opacity-50"
        style={{ background: "var(--color-accent-500)" }}
      >
        {busy ? "正在判定…" : complete ? "提交" : `还有 ${items.filter((i) => !picked[i.id]).length} 题未作答`}
      </button>
    </div>
  );
}
