from __future__ import annotations

import re
from dataclasses import dataclass


LINE_NOISE_PATTERN = re.compile(r"^\s*(已读|收到|好的+|ok|okk+|嗯+|哈哈+)\s*$", re.IGNORECASE)
QUOTE_MARK_PATTERN = re.compile(r"^[>＞]\s*")
EMOJI_PATTERN = re.compile(r"\[[^\]]{1,10}\]")
SPEAKER_PATTERN = re.compile(r"^(?P<speaker>[\u4e00-\u9fa5A-Za-z0-9_-]{1,20})\s*[:：]\s*(?P<content>.+)$")


@dataclass
class MessageTurn:
    speaker: str | None
    content: str
    raw: str


def normalize_text(raw_text: str) -> str:
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = QUOTE_MARK_PATTERN.sub("", line)
        line = EMOJI_PATTERN.sub("", line)
        if LINE_NOISE_PATTERN.match(line):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def split_turns(text: str) -> list[MessageTurn]:
    turns: list[MessageTurn] = []
    for line in text.splitlines():
        match = SPEAKER_PATTERN.match(line)
        if match:
            turns.append(
                MessageTurn(
                    speaker=match.group("speaker"),
                    content=match.group("content").strip(),
                    raw=line,
                )
            )
        else:
            turns.append(MessageTurn(speaker=None, content=line.strip(), raw=line.strip()))
    return turns


def has_explicit_speakers(turns: list[MessageTurn]) -> bool:
    return any(turn.speaker for turn in turns)
