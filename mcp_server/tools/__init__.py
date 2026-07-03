"""Реестр модулей харнеса.

Каждый .py-файл в этой папке (кроме начинающихся с "_") должен экспортировать
функцию register(mcp: FastMCP). Она вызывается автоматически при старте —
чтобы добавить инструмент, достаточно положить сюда новый файл.
"""

import importlib
import logging
import pkgutil

log = logging.getLogger(__name__)


def register_all(mcp) -> None:
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        register = getattr(module, "register", None)
        if register is None:
            log.warning("tools/%s.py не содержит register(mcp) — пропущен", info.name)
            continue
        register(mcp)
        log.info("модуль tools/%s.py зарегистрирован", info.name)
