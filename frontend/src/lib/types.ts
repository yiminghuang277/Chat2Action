export type ToneType = "formal" | "concise";

export type TimeGranularity = "year" | "month" | "day" | "hour" | "range" | "unknown";
export type TimeRelation = "deadline" | "start_time" | "sync_time" | "unknown";
export type CertaintyLevel = "high" | "medium" | "low";

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

export type HeadcountInfo = {
  raw_text: string | null;
  estimated_min: number | null;
  estimated_max: number | null;
  is_uncertain: boolean;
};

export type WorkItem = {
  id: string;
  title: string;
  description: string;
  headcount: HeadcountInfo | null;
  roles: string[];
  schedule: StructuredTimeInfo | null;
  priority: "high" | "medium" | "low";
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
