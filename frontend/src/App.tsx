import { useState } from "react";
import { EditableSection } from "./components/EditableSection";
import { analyzeRecord, generateFollowup } from "./lib/api";
import { sampleConversation } from "./lib/sampleData";
import type { AnalyzeResponse, StructuredTimeInfo, WorkItem } from "./lib/types";

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
      ? ` / 解析值：${schedule.normalized_value}`
      : "";
  const uncertain = schedule.is_uncertain ? " / 模糊时间" : "";
  return `${base}${normalized}${uncertain}`;
}

function summarizeWorkItem(item: WorkItem): string {
  const people = item.people.length > 0 ? item.people.join("、") : "未提及";
  return `事件：${item.summary} / 人员：${people} / 时间：${formatSchedule(item.schedule)} / 状态：${item.status}`;
}

export default function App() {
  const [rawText, setRawText] = useState(sampleConversation);
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
      const message = await generateFollowup(result);
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
                把一段长对话直接转换成前端可展示的结构化事件，包括事件摘要、详细内容、时间、人员、状态、风险和证据。
              </p>
            </div>
            <div className="rounded-2xl bg-slate-900 px-4 py-3 text-sm text-white">
              <div>展示字段：事件 / 详情 / 人员 / 时间 / 状态 / 风险 / 证据</div>
              <div className="mt-1 text-slate-300">单模型抽取 + 本地 follow-up 模板生成</div>
            </div>
          </div>
        </header>

        <section className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.02fr)_minmax(0,1fr)]">
          <div className="self-start xl:sticky xl:top-8">
            <section className="rounded-[28px] border border-line bg-white p-6 shadow-panel">
              <div className="mb-4 flex flex-wrap gap-3">
                <div className="rounded-xl border border-line bg-slate-50 px-4 py-2 text-sm text-slate-700">输入场景：微信群长对话</div>
                <button className="rounded-xl border border-line px-4 py-2 text-sm" onClick={() => setRawText(sampleConversation)}>
                  填充示例
                </button>
              </div>

              <div className="mb-3 text-sm text-slate-600">
                <div className="font-medium text-slate-800">原始对话输入</div>
                <div className="mt-1">把需要整理的聊天记录贴到这里，系统会抽取可展示的事件信息。</div>
              </div>

              <textarea
                className="h-[34rem] w-full rounded-3xl border border-line bg-slate-50 px-4 py-4 leading-7"
                value={rawText}
                onChange={(event) => setRawText(event.target.value)}
                placeholder="把长对话贴到这里，系统会提取事件摘要、详细内容、时间和人员。"
              />

              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  className="rounded-xl bg-brand px-5 py-3 font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-400"
                  onClick={handleAnalyze}
                  disabled={loadingAnalyze}
                >
                  {loadingAnalyze ? "分析中..." : "提取事件信息"}
                </button>
                <button
                  className="rounded-xl bg-accent px-5 py-3 font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-400"
                  onClick={handleGenerateFollowup}
                  disabled={loadingFollowup || !result.summary}
                >
                  {loadingFollowup ? "生成中..." : "生成汇总消息"}
                </button>
              </div>

              {error && <p className="mt-4 rounded-xl bg-orange-50 px-4 py-3 text-sm text-warn">{error}</p>}
            </section>
          </div>

          <div className="space-y-6">
            <section className="rounded-[28px] border border-line bg-white p-6 shadow-panel">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">结构化结果</h2>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">{result.work_items.length} 个事件</span>
              </div>
              <p className="mt-4 rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-700">
                {result.summary || "分析结果会显示在这里。"}
              </p>
              {result.work_items.length > 0 && (
                <div className="mt-4 rounded-2xl border border-line bg-slate-50 p-4">
                  <h3 className="text-sm font-semibold text-slate-800">事件概览</h3>
                  <ul className="mt-2 space-y-2 text-sm text-slate-600">
                    {result.work_items.map((item) => (
                      <li key={item.id}>{summarizeWorkItem(item)}</li>
                    ))}
                  </ul>
                </div>
              )}
              {result.review_flags.length > 0 && (
                <div className="mt-4 rounded-2xl border border-orange-200 bg-orange-50 p-4">
                  <h3 className="text-sm font-semibold text-orange-900">需要复核</h3>
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
              <p className="mt-1 text-sm text-slate-600">可直接复制到群里，同步当前事件、人员、时间和待确认事项。</p>
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
            placeholder="生成后的汇总消息会显示在这里。"
          />
        </section>
      </div>
    </main>
  );
}
