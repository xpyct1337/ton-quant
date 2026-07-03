"""Образец модуля харнеса: инструмент, ресурс и промпт.

Скопируйте этот файл, переименуйте и замените содержимое под свою задачу.
Схемы (имя, описание, параметры) MCP берёт из сигнатуры и docstring —
отдельно ничего описывать не нужно.
"""

from datetime import datetime, timezone


def register(mcp) -> None:
    @mcp.tool()
    def utc_now() -> str:
        """Текущее время в UTC (ISO 8601)."""
        return datetime.now(timezone.utc).isoformat()

    @mcp.tool()
    def percent_change(old: float, new: float) -> float:
        """Процентное изменение от old к new.

        Args:
            old: базовое значение (не ноль)
            new: новое значение
        """
        if old == 0:
            # Ошибки поднимаем исключением — клиент увидит isError + текст.
            raise ValueError("old не может быть 0")
        return (new - old) / abs(old) * 100

    # Ресурс — данные только для чтения, адресуемые URI (клиент сам решает,
    # когда их подгрузить; в отличие от tool, модель его не «вызывает»).
    @mcp.resource("harness://about")
    def about() -> str:
        """Что умеет этот харнес."""
        return "Личный MCP-харнес. Модули лежат в mcp_server/tools/."

    # Промпт — переиспользуемый шаблон запроса, который пользователь
    # выбирает в клиенте (в Claude Code — как slash-команду).
    @mcp.prompt()
    def review_json(path: str) -> str:
        """Попросить модель проверить JSON-файл на аномалии."""
        return f"Проверь файл {path}: структура, пропуски, выбросы в числах."
