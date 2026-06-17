# Задание 2 — API-пайплайн: новости → LLM → JSON

Скрипт читает CSV с новостями, отправляет каждую в LLM через Groq API
и сохраняет структурированный JSON-ответ (краткое содержание, категория,
ключевые слова, тональность) в файл.

## Стек

- Python 3.10+
- Библиотека `groq` (официальный SDK, OpenAI-совместимый протокол)
- Модель: `llama-3.3-70b-versatile` на бесплатном tier Groq
  (хорошо понимает русский, поддерживает `response_format=json_object`).
  Можно сменить в константе `MODEL` в `summarize.py`.

## Структура

```
Задание 2/
├── summarize.py          # сам пайплайн
├── requirements.txt
├── .env.example          # шаблон, как задать ключ
├── data/
│   └── news.csv          # вход: 10 русскоязычных новостей
└── output/
    └── summaries.json    # результат (создаётся после запуска)
```

## Формат входа (`data/news.csv`)

CSV с колонками `id, title, text` в UTF-8.

```csv
id,title,text
1,Запуск нового спутника связи,"Российская компания «Спутникс»..."
```

## Формат выхода (`output/summaries.json`)

```json
{
  "model": "llama-3.3-70b-versatile",
  "count": 10,
  "items": [
    {
      "id": "1",
      "title": "Запуск нового спутника связи",
      "summary": "Российская компания «Спутникс» вывела на орбиту спутник «Заря-3» ...",
      "category": "science",
      "keywords": ["спутник", "связь", "Арктика", "Восточный"],
      "sentiment": "positive"
    }
  ]
}
```

## Запуск (Windows / PowerShell)

```powershell
cd "Задание 2"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:GROQ_API_KEY = "gsk_..."   # groq
python summarize.py
```

## Запуск (Windows / cmd)

```cmd
cd "Задание 2"
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt

set GROQ_API_KEY=gsk_...
python summarize.py
```

## Параметры

```
python summarize.py --input data/news.csv --output output/summaries.json
```

## Как проверить, что всё работает

**1. Посмотреть результат глазами.** Открыть `output/summaries.json` — там
должно быть 10 объектов в `items`, у каждого `summary`, `category`,
`keywords`, `sentiment`. Категории и тональность должны соответствовать
тексту новости (например, про шахматы → `sports`, про засуху → `incident`).

**2. Прогнать пайплайн заново с нуля.** В PowerShell:

```powershell
cd "Задание 2"
Remove-Item output\summaries.json -ErrorAction SilentlyContinue
$env:GROQ_API_KEY = "gsk_..."
python summarize.py
```

В конце должна быть строка `Готово. Записано в ... Ошибок: 0.` и обновлённый
файл `output/summaries.json`.

**3. Проверить, что JSON валидный** (а не "просто похож на JSON"):

```powershell
python -c "import json; d = json.load(open('output/summaries.json', encoding='utf-8')); print('items:', len(d['items']), '| sample:', d['items'][0]['category'], '/', d['items'][0]['sentiment'])"
```

Ожидаемый вывод: `items: 10 | sample: technology / positive`.

**4. Поведение без ключа.** Если запустить без `GROQ_API_KEY` —
скрипт не падает стектрейсом, а печатает понятную ошибку и возвращает
exit code 2:

```powershell
Remove-Item Env:GROQ_API_KEY -ErrorAction SilentlyContinue
python summarize.py
echo $LASTEXITCODE   # ожидается 2
```

## Что делает скрипт

1. Читает CSV (`utf-8-sig`, чтобы пережить BOM от Excel).
2. Для каждой строки формирует запрос к LLM с system-prompt'ом,
   жёстко описывающим JSON-схему (`summary`, `category`, `keywords`,
   `sentiment`), и `response_format={"type":"json_object"}`.
3. Парсит JSON (с фоллбэком на случай, если модель обернёт его в
   ```` ```json ... ``` ````).
4. При ошибке парсинга или API делает до 2 повторов с backoff.
5. Складывает все результаты в один JSON-файл вместе с именем модели
   и счётчиком.

## Возможные ошибки

- **BOM в CSV из Excel** → читаем как `utf-8-sig`.
- **Модель оборачивает JSON в markdown** → достаём содержимое между
  фигурными скобками или из ```` ``` ```` блока.
- **Сетевая или временная ошибка API** → ретраи с задержкой.
- **Ошибка на одной новости не должна терять остальные** → пишем
  `{"error": "..."}` в эту запись и продолжаем.
- **Кириллица в JSON** → `ensure_ascii=False`.
- **Ключ не задан** → внятное сообщение и `exit code 2`.
