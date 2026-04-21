import type { HeadcountInfo, StructuredTimeInfo, WorkItem } from "../lib/types";

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

function ensureHeadcount(headcount: HeadcountInfo | null): HeadcountInfo {
  return (
    headcount ?? {
      raw_text: null,
      estimated_min: null,
      estimated_max: null,
      is_uncertain: true
    }
  );
}

export function EditableSection(props: Props) {
  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-line bg-white p-5 shadow-panel">
        <h3 className="mb-4 text-lg font-semibold text-ink">当前待办事项</h3>
        <div className="space-y-3">
          {props.workItems.length === 0 && <p className="text-sm text-slate-500">暂无事项。</p>}
          {props.workItems.map((item, index) => {
            const schedule = ensureTimeInfo(item.schedule);
            const headcount = ensureHeadcount(item.headcount);
            return (
              <div key={item.id} className="grid gap-3 rounded-2xl border border-line p-4 md:grid-cols-2">
                <input
                  className="rounded-xl border border-line px-3 py-2"
                  value={item.title}
                  placeholder="事项名称"
                  onChange={(event) =>
                    props.onWorkItemsChange(updateItem(props.workItems, index, { ...item, title: event.target.value }))
                  }
                />
                <input
                  className="rounded-xl border border-line px-3 py-2"
                  value={headcount.raw_text ?? ""}
                  placeholder="预计人数，例如 1人 / 1-2人"
                  onChange={(event) =>
                    props.onWorkItemsChange(
                      updateItem(props.workItems, index, {
                        ...item,
                        headcount: { ...headcount, raw_text: event.target.value || null }
                      })
                    )
                  }
                />
                <textarea
                  className="min-h-24 rounded-xl border border-line px-3 py-2 md:col-span-2"
                  value={item.description}
                  placeholder="需求描述"
                  onChange={(event) =>
                    props.onWorkItemsChange(updateItem(props.workItems, index, { ...item, description: event.target.value }))
                  }
                />
                <input
                  className="rounded-xl border border-line px-3 py-2"
                  value={schedule.raw_text ?? ""}
                  placeholder="时间原文，例如 明天下午 / 下周左右"
                  onChange={(event) =>
                    props.onWorkItemsChange(
                      updateItem(props.workItems, index, {
                        ...item,
                        schedule: { ...schedule, raw_text: event.target.value || null }
                      })
                    )
                  }
                />
                <input
                  className="rounded-xl border border-line px-3 py-2"
                  value={item.roles.join("、")}
                  placeholder="建议角色"
                  onChange={(event) =>
                    props.onWorkItemsChange(
                      updateItem(props.workItems, index, {
                        ...item,
                        roles: event.target.value
                          .split(/[、,]/)
                          .map((role) => role.trim())
                          .filter(Boolean)
                      })
                    )
                  }
                />
                <div className="rounded-xl border border-dashed border-line bg-slate-50 px-3 py-2 text-sm text-slate-600 md:col-span-2">
                  排期：{schedule.raw_text || "待确认"} · 解析值：{schedule.normalized_value || "无"} · 粒度：{schedule.granularity} ·
                  {schedule.is_uncertain ? " 模糊时间" : ` 置信度 ${schedule.certainty_level}`}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="rounded-3xl border border-line bg-white p-5 shadow-panel">
        <h3 className="mb-4 text-lg font-semibold text-ink">资源缺口 / 风险</h3>
        <div className="space-y-3">
          {props.resourceGaps.length === 0 && <p className="text-sm text-slate-500">暂无资源缺口。</p>}
          {props.resourceGaps.map((gap, index) => (
            <textarea
              key={`${gap}-${index}`}
              className="min-h-20 w-full rounded-xl border border-line px-3 py-2"
              value={gap}
              onChange={(event) =>
                props.onResourceGapsChange(
                  updateItem(props.resourceGaps, index, event.target.value)
                )
              }
            />
          ))}
        </div>
      </section>
    </div>
  );
}
