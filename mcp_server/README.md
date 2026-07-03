# ton-quant-harness — собственный MCP-сервер

Универсальный каркас: один `server.py`, инструменты — модулями в `tools/`.
Полная инструкция (что такое MCP, как писать инструменты, отладка,
подключение к Claude): **[docs/CUSTOM-MCP.md](../docs/CUSTOM-MCP.md)**.

## Quick start

```bash
cd mcp_server
uv run --with "mcp[cli]" mcp dev server.py   # отладка в MCP Inspector
```

Подключение к Claude Code — уже настроено через `.mcp.json` в корне репо.
Добавить свой инструмент: скопируйте `tools/example.py`, переименуйте,
напишите функцию с `@mcp.tool()` — она подхватится автоматически.
