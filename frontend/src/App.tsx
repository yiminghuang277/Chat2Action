import { useState } from "react";
import { EditableSection } from "./components/EditableSection";
import { analyzeRecord, generateFollowup } from "./lib/api";
import { sampleConversation } from "./lib/sampleData";
import type { AnalyzeResponse, HeadcountInfo, StructuredTimeInfo, ToneType, WorkItem } from "./lib/types";

const defaultResult: AnalyzeResponse = {
  summary: "",
  work_items: [],
  resource_gaps: [],
  review_flags: []
};

function formatSchedule(schedule: StructuredTimeInfo | null): string {
  if (!schedule) {
    return "未提及，待确认";
  }
  const base = schedule.raw_text ?? schedule.normalized_value ?? "未提及，待确认";
  const normalized =
    schedule.normalized_value && schedule.normalized_value !== schedule.raw_text
      ? ` · 解析为 ${schedule.normalized_value}`
      : "";
  const uncertain = schedule.is_uncertain ? " · 模糊时间" : "";
  return `${base}${normalized}${uncertain}`;
}

function formatHeadcount(headcount: HeadcountInfo | null): string {
  if (!headcount) {
    return "未提及，待确认";
  }
  if (headcount.raw_text) {
    return headcount.raw_text;
  }
  if (headcount.estimated_min === headcount.estimated_max && headcount.estimated_min !== null) {
    return `${headcount.estimated_min}人`;
  }
  if (headcount.estimated_min !== null || headcount.estimated_max !== null) {
    return `${headcount.estimated_min ?? 0}-${headcount.estimated_max ?? 0}人`;
  }
  return "未提及，待确认";
}

function summarizeWorkItem(item: WorkItem): string {
  return `${item.title} · ${formatHeadcount(item.headcount)} · ${formatSchedule(item.schedule)}`;
}

export default function App() {
  const [rawText, setRawText] = useState(sampleConversation);
  const [tone, setTone] = useState<ToneType>("formal");
  const [result, setResult] = useState<AnalyzeResponse>(defaultResult);
  const [followup, setFollowup] = useState("");
  const [loadingAnalyze, setLoadingAnalyze] = useState(false);
  const [loadingFollowup, setLoadingFollowup] = useState(false);
  const [error, setError] = useState("");

  const handleAnalyze = async () => {
    try {
      setError("");
      setLoadingAnalyze(true);
      const payload = await analyzeRecord({
        raw_text: rawText,
        language: "zh-CN"
      });
      setResult(payload);
      setFollowup("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "分析失败");
    } finally {
      setLoadingAnalyze(false);
    }
  };

  const handleGenerateFollowup = async () => {
    try {
      setError("");
      setLoadingFollowup(true);
      const message = await generateFollowup({ ...result, tone });
      setFollowup(message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成失败");
    } finally {
      setLoadingFollowup(false);
    }
  };

  const copyFollowup = async () => {
    await navigator.clipboard.writeText(followup);
  };

  return (
    <main className="min-h-screen px-4 py-8 text-ink md:px-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="rounded-[28px] border border-white/70 bg-white/80 p-6 shadow-panel backdrop-blur">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-sm font-medium uppercase tracking-[0.24em] text-accent">chat2action</p>
              <h1 className="mt-2 text-3xl font-semibold">chat2action</h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
                把一段长对话直接转成当前待办事项、预计人手、时间要求和资源缺口。对话里未提及的信息会明确标注为待确认，而不是凭空补全。
              </p>
            </div>
            <div className="rounded-2xl bg-slate-900 px-4 py-3 text-sm text-white">
              <div>输出重点：事项 / 需求描述 / 预计人数 / 时间 / 资源缺口</div>
              <div className="mt-1 text-slate-300">缺失信息默认标注为“未提及，待确认”</div>
            </div>
          </div>
        </header>

        <section className="grid gap-6 xl:grid-cols-[1.05fr_1fr]">
          <div className="rounded-[28px] border border-line bg-white p-6 shadow-panel">
            <div className="mb-4 flex flex-wrap gap-3">
              <div className="rounded-xl border border-line bg-slate-50 px-4 py-2 text-sm text-slate-700">输入场景：微信长对话</div>
              <button className="rounded-xl border border-line px-4 py-2 text-sm" onClick={() => setRawText(sampleConversation)}>
                填充示例
              </button>
            </div>
            <textarea
              className="min-h-[420px] w-full rounded-3xl border border-line bg-slate-50 px-4 py-4 leading-7"
              value={rawText}
              onChange={(event) => setRawText(event.target.value)}
              placeholder="把长对话贴到这里，系统会提取当前任务需求、排期和人手需要"
            />
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                className="rounded-xl bg-brand px-5 py-3 font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-400"
                onClick={handleAnalyze}
                disabled={loadingAnalyze}
              >
                {loadingAnalyze ? "分析中..." : "提取任务需求"}
              </button>
              <button
                className="rounded-xl bg-accent px-5 py-3 font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-400"
                onClick={handleGenerateFollowup}
                disabled={loadingFollowup || !result.summary}
              >
                {loadingFollowup ? "生成中..." : "生成汇总消息"}
              </button>
              <select
                className="rounded-xl border border-line px-3 py-2"
                value={tone}
                onChange={(event) => setTone(event.target.value as ToneType)}
              >
                <option value="formal">正式版</option>
                <option value="concise">简洁版</option>
              </select>
            </div>
            {error && <p className="mt-4 rounded-xl bg-orange-50 px-4 py-3 text-sm text-warn">{error}</p>}
          </div>

          <div className="space-y-6">
            <section className="rounded-[28px] border border-line bg-white p-6 shadow-panel">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">结构化结果</h2>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                  {result.work_items.length} Work Items
                </span>
              </div>
              <p className="mt-4 rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-700">
                {result.summary || "分析结果会显示在这里。"}
              </p>
              {result.work_items.length > 0 && (
                <div className="mt-4 rounded-2xl border border-line bg-slate-50 p-4">
                  <h3 className="text-sm font-semibold text-slate-800">事项摘要</h3>
                  <ul className="mt-2 space-y-2 text-sm text-slate-600">
                    {result.work_items.map((item) => (
                      <li key={item.id}>{summarizeWorkItem(item)}</li>
                    ))}
                  </ul>
                </div>
              )}
              {result.review_flags.length > 0 && (
                <div className="mt-4 rounded-2xl border border-orange-200 bg-orange-50 p-4">
                  <h3 className="text-sm font-semibold text-orange-900">Review Flags</h3>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-orange-800">
                    {result.review_flags.map((flag) => (
                      <li key={flag}>{flag}</li>
                    ))}
                  </ul>
                </div>
              )}
            </section>

            <EditableSection
              workItems={result.work_items}
              resourceGaps={result.resource_gaps}
              onWorkItemsChange={(items) => setResult((current) => ({ ...current, work_items: items }))}
              onResourceGapsChange={(items) => setResult((current) => ({ ...current, resource_gaps: items }))}
            />
          </div>
        </section>

        <section className="rounded-[28px] border border-line bg-white p-6 shadow-panel">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold">汇总消息</h2>
              <p className="mt-1 text-sm text-slate-600">可直接复制到群里做当前任务需求和资源排期同步。</p>
            </div>
            <button
              className="rounded-xl border border-line px-4 py-2 text-sm disabled:cursor-not-allowed disabled:text-slate-400"
              onClick={copyFollowup}
              disabled={!followup}
            >
              一键复制
            </button>
          </div>
          <textarea
            className="mt-4 min-h-48 w-full rounded-3xl border border-line bg-slate-50 px-4 py-4 leading-7"
            value={followup}
            onChange={(event) => setFollowup(event.target.value)}
            placeholder="生成后的汇总消息会显示在这里"
          />
        </section>
      </div>
    </main>
  );
}
