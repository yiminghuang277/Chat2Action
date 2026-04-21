export type ToneType = "formal" | "concise";

export type TimeGranularity = "year" | "month" | "day" | "hour" | "range" | "unknown";
export type TimeRelation = "deadline" | "start_time" | "sync_time" | "unknown";
export type CertaintyLevel = "high" | "medium" | "low";
export type WorkStatus = "in_progress" | "pending" | "blocked" | "unknown";

export type StructuredTimeInfo = {
  raw_text: string | null;
  normalized_value: string | null;
  range_start: string | null;
  range_end: string | null;
  granularity: TimeGranularity;
  relation: TimeRelation;
  is_uncertain: boolean;
  certainty_level: CertaintyLevel;
};

export type WorkItem = {
  id: string;
  summary: string;
  details: string;
  people: string[];
  schedule: StructuredTimeInfo | null;
  priority: "high" | "medium" | "low";
  status: WorkStatus;
  risks: string[];
  confidence: number;
  evidence: string;
};

export type AnalyzeResponse = {
  summary: string;
  work_items: WorkItem[];
  resource_gaps: string[];
  review_flags: string[];
};
