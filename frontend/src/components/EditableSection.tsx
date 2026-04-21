import type { StructuredTimeInfo, WorkItem } from "../lib/types";

type Props = {
  workItems: WorkItem[];
  resourceGaps: string[];
  onWorkItemsChange: (items: WorkItem[]) => void;
  onResourceGapsChange: (items: string[]) => void;
};

function updateItem<T>(items: T[], index: number, next: T): T[] {
  return items.map((item, current) => (current === index ? next : item));
}

function ensureTimeInfo(schedule: StructuredTimeInfo | null): StructuredTimeInfo {
  return (
    schedule ?? {
      raw_text: null,
      normalized_value: null,
      range_start: null,
      range_end: null,
      granularity: "unknown",
      relation: "unknown",
      is_uncertain: false,
      certainty_level: "medium"
    }
  );
}

function fieldLabel(title: string) {
  return <div className="mb-2 text-sm font-medium text-slate-800">{title}</div>;
}

export function EditableSection(props: Props) {
  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-line bg-white p-5 shadow-panel">
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-ink">事件详情</h3>
          <p className="mt-1 text-sm text-slate-500">每个事件按必要字段展开，便于快速检查和微调。</p>
        </div>

        <div className="space-y-4">
          {props.workItems.length === 0 && <p className="text-sm text-slate-500">暂时没有提取到明确事件。</p>}

          {props.workItems.map((item, index) => {
            const schedule = ensureTimeInfo(item.schedule);

            return (
              <div key={item.id} className="rounded-2xl border border-line p-4">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <div className="text-sm font-semibold text-slate-800">事件 {index + 1}</div>
                  <div className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">{item.status}</div>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    {fieldLabel("事件摘要")}
                    <input
                      className="w-full rounded-xl border border-line px-3 py-2"
                      value={item.summary}
                      placeholder="请输入事件摘要"
                      onChange={(event) =>
                        props.onWorkItemsChange(updateItem(props.workItems, index, { ...item, summary: event.target.value }))
                      }
                    />
                  </div>

                  <div>
                    {fieldLabel("相关人员")}
                    <input
                      className="w-full rounded-xl border border-line px-3 py-2"
                      value={item.people.join("、")}
                      placeholder="无"
                      onChange={(event) =>
                        props.onWorkItemsChange(
                          updateItem(props.workItems, index, {
                            ...item,
                            people: event.target.value
                              .split(/[、,，/]/)
                              .map((person) => person.trim())
                              .filter(Boolean)
                          })
                        )
                      }
                    />
                  </div>

                  <div className="md:col-span-2">
                    {fieldLabel("详细内容")}
                    <textarea
                      className="min-h-24 w-full rounded-xl border border-line px-3 py-2"
                      value={item.details}
                      placeholder="请输入详细内容"
                      onChange={(event) =>
                        props.onWorkItemsChange(updateItem(props.workItems, index, { ...item, details: event.target.value }))
                      }
                    />
                  </div>

                  <div>
                    {fieldLabel("时间原文")}
                    <input
                      className="w-full rounded-xl border border-line px-3 py-2"
                      value={schedule.raw_text ?? ""}
                      placeholder="无"
                      onChange={(event) =>
                        props.onWorkItemsChange(
                          updateItem(props.workItems, index, {
                            ...item,
                            schedule: { ...schedule, raw_text: event.target.value || null }
                          })
                        )
                      }
                    />
                  </div>

                  <div>
                    {fieldLabel("当前状态")}
                    <input
                      className="w-full rounded-xl border border-line px-3 py-2"
                      value={item.status}
                      placeholder="例如：in_progress"
                      onChange={(event) =>
                        props.onWorkItemsChange(
                          updateItem(props.workItems, index, { ...item, status: event.target.value as WorkItem["status"] })
                        )
                      }
                    />
                  </div>

                  <div className="md:col-span-2">
                    {fieldLabel("风险信息")}
                    <textarea
                      className="min-h-20 w-full rounded-xl border border-line px-3 py-2"
                      value={item.risks.join("\n")}
                      placeholder="无"
                      onChange={(event) =>
                        props.onWorkItemsChange(
                          updateItem(props.workItems, index, {
                            ...item,
                            risks: event.target.value
                              .split("\n")
                              .map((risk) => risk.trim())
                              .filter(Boolean)
                          })
                        )
                      }
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="rounded-3xl border border-line bg-white p-5 shadow-panel">
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-ink">全局风险与待确认项</h3>
          <p className="mt-1 text-sm text-slate-500">这里展示没有落到单个事件上、但会影响整体推进的风险和待确认信息。</p>
        </div>

        <div className="space-y-3">
          {props.resourceGaps.length === 0 && <p className="text-sm text-slate-500">暂时没有全局风险或待确认项。</p>}
          {props.resourceGaps.map((gap, index) => (
            <div key={`${gap}-${index}`}>
              <div className="mb-2 text-sm font-medium text-slate-800">条目 {index + 1}</div>
              <textarea
                className="min-h-20 w-full rounded-xl border border-line px-3 py-2"
                value={gap}
                onChange={(event) => props.onResourceGapsChange(updateItem(props.resourceGaps, index, event.target.value))}
              />
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
