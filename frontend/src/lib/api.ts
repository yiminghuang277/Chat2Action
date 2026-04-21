import type { AnalyzeResponse } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function analyzeRecord(payload: {
  raw_text: string;
  language: string;
}): Promise<AnalyzeResponse> {
  const response = await fetch(`${API_BASE_URL}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source_type: "wechat",
      raw_text: payload.raw_text,
      language: payload.language
    })
  });
  if (!response.ok) {
    throw new Error("分析失败，请检查后端服务或输入内容。");
  }
  return response.json();
}

export async function generateFollowup(payload: AnalyzeResponse): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/api/followup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error("汇总消息生成失败。");
  }
  const data = (await response.json()) as { message: string };
  return data.message;
}
