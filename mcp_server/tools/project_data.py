"""Пример «инструмента над своими данными»: чтение JSON-снапшотов из data/.

Показывает главный паттерн харнеса — дать модели структурированный доступ
к вашим локальным данным без сети и ключей. Путь к данным можно переопределить
переменной окружения TON_QUANT_DATA.
"""

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("TON_QUANT_DATA", REPO_ROOT / "data"))

MAX_CHARS = 40_000  # защита контекста модели от гигантских файлов


def _resolve(rel_path: str) -> Path:
    p = (DATA_DIR / rel_path).resolve()
    if not p.is_relative_to(DATA_DIR.resolve()):
        raise ValueError(f"путь выходит за пределы {DATA_DIR}")
    if not p.is_file():
        raise FileNotFoundError(f"нет файла {rel_path} в {DATA_DIR}")
    return p


def register(mcp) -> None:
    @mcp.tool()
    def list_data_files(subdir: str = "") -> list[str]:
        """Список JSON-файлов в data/ (или в её подпапке), с размерами.

        Args:
            subdir: подпапка внутри data/, например "desk" или "snapshots"
        """
        base = (DATA_DIR / subdir).resolve()
        if not base.is_relative_to(DATA_DIR.resolve()) or not base.is_dir():
            raise ValueError(f"нет папки {subdir!r} в {DATA_DIR}")
        return sorted(
            f"{p.relative_to(DATA_DIR)} ({p.stat().st_size:,} B)"
            for p in base.rglob("*.json")
        )

    @mcp.tool()
    def query_json(path: str, keys: str = "", head: int = 20) -> str:
        """Прочитать JSON из data/ с выборкой по ключам и ограничением размера.

        Args:
            path: путь относительно data/, например "index.json" или "desk/state.json"
            keys: точечный путь внутри JSON, например "tokens.0.symbol" или
                  "summary" (пусто = весь документ)
            head: если результат — список, вернуть только первые head элементов
        """
        doc = json.loads(_resolve(path).read_text(encoding="utf-8"))
        for key in filter(None, keys.split(".")):
            if isinstance(doc, list):
                doc = doc[int(key)]
            elif isinstance(doc, dict):
                if key not in doc:
                    raise KeyError(f"нет ключа {key!r}; есть: {list(doc)[:30]}")
                doc = doc[key]
            else:
                raise TypeError(f"нельзя взять {key!r} из {type(doc).__name__}")
        if isinstance(doc, list) and head > 0:
            doc = doc[:head]
        text = json.dumps(doc, ensure_ascii=False, indent=1)
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + f"\n… обрезано, всего {len(text):,} символов; сузьте keys/head"
        return text
