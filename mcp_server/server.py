"""Точка входа MCP-сервера (харнеса).

Запуск (stdio, по умолчанию):
    uv run --with "mcp[cli]" python server.py
или, если зависимости уже стоят:
    python server.py

Отладка в MCP Inspector:
    uv run --with "mcp[cli]" mcp dev server.py

ВАЖНО: сервер общается с клиентом по stdout. Никогда не print()-уйте в
инструментах — логируйте в stderr (logging так и делает по умолчанию).
"""

import logging
import sys

from mcp.server.fastmcp import FastMCP

import tools

logging.basicConfig(stream=sys.stderr, level=logging.INFO)

mcp = FastMCP(
    "ton-quant-harness",
    instructions=(
        "Личный харнес: инструменты добавляются модулями в tools/. "
        "Каждый модуль решает одну прикладную задачу."
    ),
)

tools.register_all(mcp)


def main() -> None:
    mcp.run()  # stdio; для HTTP: mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
