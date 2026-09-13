"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { api } from "@/lib/api";
import type { Depth } from "@/lib/events";
import type { BenchQuestion } from "@/lib/types";

export type AskRequest = { question: string; depth: Depth; questionId: string | null };

const CUSTOM = "custom";

/** Question, presets from SearchBench, depth and prompt set (docs/07 §3). */
export function QuestionBar({
  onAsk,
  busy,
  error,
}: {
  onAsk: (request: AskRequest) => void;
  busy: boolean;
  error: string | null;
}) {
  const [question, setQuestion] = useState("");
  const [preset, setPreset] = useState(CUSTOM);
  const [depth, setDepth] = useState<Depth>("deep");
  const presets = useQuery({ queryKey: ["bench-questions"], queryFn: () => api.benchQuestions() });

  // Grouped by domain and tier, as the spec asks; the answer key never reaches the UI.
  const groups = useMemo(() => {
    const byGroup = new Map<string, BenchQuestion[]>();
    for (const item of presets.data ?? []) {
      const label = `${item.domain} · tier ${item.tier}`;
      byGroup.set(label, [...(byGroup.get(label) ?? []), item]);
    }
    return [...byGroup.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [presets.data]);

  const choosePreset = (id: string) => {
    setPreset(id);
    const found = presets.data?.find((item) => item.id === id);
    if (found) setQuestion(found.question);
  };

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || busy) return;
    onAsk({ question: trimmed, depth, questionId: preset === CUSTOM ? null : preset });
  };

  return (
    <form onSubmit={submit} className="rounded-lg border border-line bg-panel p-4">
      <div className="flex gap-3">
        <label className="sr-only" htmlFor="question">
          Question
        </label>
        <input
          id="question"
          value={question}
          onChange={(event) => {
            setQuestion(event.target.value);
            if (preset !== CUSTOM) setPreset(CUSTOM);
          }}
          placeholder="Ask a Medicare coverage policy question…"
          className="min-w-0 flex-1 rounded-md border border-line bg-background px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <button
          type="submit"
          disabled={busy || !question.trim()}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          {busy ? "Starting…" : "Ask ▶"}
        </button>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
        <label className="flex items-center gap-2">
          <span className="text-muted">Presets</span>
          <select
            value={preset}
            onChange={(event) => choosePreset(event.target.value)}
            className="max-w-[28rem] rounded-md border border-line bg-background px-2 py-1"
          >
            <option value={CUSTOM}>custom</option>
            {groups.map(([label, items]) => (
              <optgroup key={label} label={label}>
                {items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.id} ({item.split}): {item.question.slice(0, 70)}
                    {item.question.length > 70 ? "…" : ""}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>

        <fieldset className="flex items-center gap-3">
          <legend className="sr-only">Depth</legend>
          <span className="text-muted">Depth</span>
          {(["deep", "fast"] as const).map((value) => (
            <label key={value} className="flex items-center gap-1">
              <input type="radio" name="depth" checked={depth === value} onChange={() => setDepth(value)} />
              {value}
            </label>
          ))}
        </fieldset>

        <fieldset className="flex items-center gap-3">
          <legend className="sr-only">Prompts</legend>
          <span className="text-muted">Prompts</span>
          <label className="flex items-center gap-1">
            <input type="radio" name="prompts" checked readOnly />
            base
          </label>
          {/* docs/11: `optimized` has no prompt files yet and would silently run base. */}
          <label className="flex items-center gap-1 text-muted" title="GEPA has not produced optimized prompts yet (Day 3)">
            <input type="radio" name="prompts" disabled />
            opt
          </label>
        </fieldset>
      </div>

      {error && (
        <p role="alert" className="mt-3 rounded-md border border-bad bg-bad-soft px-3 py-2 text-sm text-bad">
          {error}
        </p>
      )}
      {presets.isError && (
        <p className="mt-2 text-xs text-muted">Presets unavailable: {String(presets.error)}</p>
      )}
    </form>
  );
}
