from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from groq import APIError, Groq

MODEL = "llama-3.3-70b-versatile"
MAX_TOKENS = 600

SYSTEM_PROMPT = (
    "Ты — ассистент-аналитик. По тексту новости верни строго ОДИН JSON-объект "
    "без какого-либо текста до или после, без markdown-обёрток. "
    "Схема: {"
    '"summary": "краткое содержание в 2–3 предложениях на русском", '
    '"category": "одно из: politics, economy, sports, science, technology, society, culture, incident, other", '
    '"keywords": ["3–6 ключевых слов на русском, существительные в им. падеже"], '
    '"sentiment": "одно из: positive, neutral, negative"'
    "}."
)

USER_TEMPLATE = "Заголовок: {title}\n\nТекст: {text}\n\nВерни JSON."


def extract_json(raw: str) -> dict[str, Any]:
    """Достаёт JSON-объект из ответа модели, переживая ```json ... ``` и мусор по краям."""
    cleaned = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    else:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def summarize_one(client: Groq, title: str, text: str, retries: int = 2) -> dict[str, Any]:
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_TEMPLATE.format(title=title, text=text)},
                ],
            )
            raw = resp.choices[0].message.content or ""
            return extract_json(raw)
        except (json.JSONDecodeError, APIError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
            else:
                break
    raise RuntimeError(f"Не удалось получить валидный JSON после {retries + 1} попыток: {last_err}")


def read_news(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    required = {"id", "title", "text"}
    if not rows or not required.issubset(rows[0].keys()):
        raise ValueError(f"CSV должен содержать колонки {required}. Найдено: {rows[0].keys() if rows else 'пусто'}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Саммаризация новостей через Groq API")
    parser.add_argument("--input", default="data/news.csv", help="путь к входному CSV")
    parser.add_argument("--output", default="output/summaries.json", help="путь к выходному JSON")
    args = parser.parse_args()

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("ERROR: переменная окружения GROQ_API_KEY не задана.", file=sys.stderr)
        return 2

    root = Path(__file__).resolve().parent
    input_path = (root / args.input).resolve()
    output_path = (root / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = read_news(input_path)
    print(f"Прочитано новостей: {len(rows)}. Модель: {MODEL}")

    client = Groq(api_key=api_key)
    results: list[dict[str, Any]] = []
    errors = 0

    for i, row in enumerate(rows, 1):
        nid, title, text = row["id"], row["title"], row["text"]
        print(f"[{i}/{len(rows)}] id={nid} — {title[:60]}")
        try:
            data = summarize_one(client, title, text)
            results.append({"id": nid, "title": title, **data})
        except Exception as e:
            errors += 1
            results.append({"id": nid, "title": title, "error": str(e)})
            print(f"  ! ошибка: {e}", file=sys.stderr)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump({"model": MODEL, "count": len(results), "items": results}, f, ensure_ascii=False, indent=2)

    print(f"\nГотово. Записано в {output_path}. Ошибок: {errors}.")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
