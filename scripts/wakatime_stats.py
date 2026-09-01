from __future__ import annotations

import base64
import sys
from pathlib import Path
from typing import Any, Callable

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.http_json import HttpJsonTransportError, request_json

WAKA_URL = "https://wakatime.com/api/v1/users/current/stats/last_7_days"
BAR_WIDTH = 25
WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
HOUR_LABELS = (
    ("morning", "🌞 Morning"),
    ("daytime", "🌆 Daytime"),
    ("evening", "🌃 Evening"),
    ("night", "🌙 Night"),
)


class WakaCollectionError(Exception):
    """Raised when WakaTime stats cannot be collected."""


HttpCallable = Callable[..., dict[str, Any]]


def default_http(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        return request_json(url, method=method, headers=headers, json_body=json_body)
    except HttpJsonTransportError as exc:
        raise WakaCollectionError("WakaTime request failed") from exc


def _top_entries(items: Any, limit: int = 5) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        try:
            percent = float(item.get("percent") or 0)
        except (TypeError, ValueError):
            percent = 0.0
        cleaned.append(
            {
                "name": str(item["name"]),
                "text": str(item.get("text") or ""),
                "percent": percent,
            }
        )
    cleaned.sort(key=lambda entry: (-entry["percent"], entry["name"]))
    return cleaned[:limit]


def retrieve(http: HttpCallable, api_key: str) -> dict[str, Any]:
    token = base64.b64encode(f"{api_key}:".encode("utf-8")).decode("ascii")
    headers = {
        "Authorization": f"Basic {token}",
        "Accept": "application/json",
        "User-Agent": "aaronedev-readme",
    }
    response = http(WAKA_URL, method="GET", headers=headers, json_body=None)
    status = response.get("status")
    if status not in {200, 202}:
        raise WakaCollectionError(f"WakaTime request failed with HTTP {status}")
    payload = response.get("json")
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise WakaCollectionError("WakaTime returned an unexpected payload")
    data = payload["data"]
    return {
        "timezone": str(data.get("timezone") or ""),
        "languages": _top_entries(data.get("languages")),
        "editors": _top_entries(data.get("editors")),
        "operating_systems": _top_entries(data.get("operating_systems")),
    }


def _bar(percent: float) -> str:
    filled = int(round((percent / 100.0) * BAR_WIDTH))
    filled = max(0, min(BAR_WIDTH, filled))
    return ("█" * filled) + ("░" * (BAR_WIDTH - filled))


def _fmt_percent(percent: float) -> str:
    text = f"{percent:.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


def _row(name: str, text: str, percent: float) -> str:
    return f"{name:<24} {text:<18} {_bar(percent)}   {_fmt_percent(percent)}"


def _count_row(label: str, count: int, percent: float) -> str:
    unit = "commit" if count == 1 else "commits"
    return f"{label:<13}{count} {unit:<12}{_bar(percent)}   {_fmt_percent(percent)}"


def _percent(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return (part / total) * 100.0


def render(
    stats: dict[str, Any],
    commit_hours: dict[str, int] | None = None,
    commit_weekdays: dict[str, int] | None = None,
) -> str:
    lines: list[str] = []
    if commit_hours:
        morning = int(commit_hours.get("morning") or 0)
        daytime = int(commit_hours.get("daytime") or 0)
        evening = int(commit_hours.get("evening") or 0)
        night = int(commit_hours.get("night") or 0)
        total = morning + daytime + evening + night
        title = (
            "I'm an Early 🐤"
            if (morning + daytime) >= (evening + night)
            else "I'm a Night 🦉"
        )
        lines.append(f"**{title}**")
        lines.append("")
        lines.append("```text")
        for key, label in HOUR_LABELS:
            count = int(commit_hours.get(key) or 0)
            lines.append(_count_row(label, count, _percent(count, total)))
        lines.append("")
        lines.append("```")
        lines.append("")

    if commit_weekdays:
        ordered = [(name, int(commit_weekdays.get(name) or 0)) for name in WEEKDAYS]
        total = sum(count for _, count in ordered)
        best_name = max(ordered, key=lambda item: (item[1], -WEEKDAYS.index(item[0])))[
            0
        ]
        lines.append(f"📅 **I'm Most Productive on {best_name}**")
        lines.append("")
        lines.append("```text")
        for name, count in ordered:
            lines.append(_count_row(name, count, _percent(count, total)))
        lines.append("")
        lines.append("```")
        lines.append("")

    lines.append("📊 **This Week I Spent My Time On**")
    lines.append("")
    lines.append("```text")
    timezone = stats.get("timezone") or ""
    if timezone:
        lines.append(f"⌚︎ Time Zone: {timezone}")
        lines.append("")
    lines.append("💬 Programming Languages: ")
    for entry in stats.get("languages") or []:
        lines.append(_row(entry["name"], entry["text"], entry["percent"]))
    lines.append("")
    lines.append("🔥 Editors: ")
    for entry in stats.get("editors") or []:
        lines.append(_row(entry["name"], entry["text"], entry["percent"]))
    lines.append("")
    lines.append("💻 Operating System: ")
    for entry in stats.get("operating_systems") or []:
        lines.append(_row(entry["name"], entry["text"], entry["percent"]))
    lines.append("")
    lines.append("```")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"
