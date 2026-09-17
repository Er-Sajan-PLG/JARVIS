"""Eval runner — loads evals, executes them, reports results."""

from __future__ import annotations

import asyncio
import importlib
import logging
import pkgutil
import time
from typing import Any

from evals.eval import EvalResult, EvalStatus, EvalSuite

logger = logging.getLogger(__name__)


def discover_evals(package: str = "evals.evals") -> list[Any]:
    """Import all modules in the evals.evals package and collect Eval instances."""
    evals: list[Any] = []
    try:
        pkg = importlib.import_module(package)
    except ModuleNotFoundError:
        return evals

    for _importer, modname, _ispkg in pkgutil.iter_modules(pkg.__path__):
        full = f"{package}.{modname}"
        try:
            module = importlib.import_module(full)
        except Exception as e:
            logger.warning("Failed to import eval module %s: %s", full, e)
            evals.append(
                EvalResult(
                    name=modname,
                    status=EvalStatus.SKIP,
                    message=f"import failed: {e}",
                )
            )
            continue

        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if isinstance(obj, type) and attr_name.endswith("Eval") and attr_name != "Eval":
                try:
                    evals.append(obj())
                except Exception as e:
                    logger.warning("Failed to instantiate %s: %s", attr_name, e)
                    evals.append(
                        EvalResult(
                            name=attr_name,
                            status=EvalStatus.SKIP,
                            message=f"instantiation failed: {e}",
                        )
                    )
    return evals


async def run_eval(eval_obj: Any) -> EvalResult:
    """Run a single eval and return its result."""
    name = getattr(eval_obj, "name", type(eval_obj).__name__)
    start = time.monotonic()
    try:
        if hasattr(eval_obj, "run"):
            result = await eval_obj.run()
        else:
            result = EvalResult(
                name=name,
                status=EvalStatus.FAIL,
                message="eval has no run() method",
            )
    except Exception as e:
        result = EvalResult(
            name=name,
            status=EvalStatus.FAIL,
            message=f"exception: {e}",
        )
    result.duration_ms = (time.monotonic() - start) * 1000
    return result


async def run_suite(
    name: str = "jarvis-suite",
    package: str = "evals.evals",
) -> EvalSuite:
    """Discover and run all evals, returning an aggregate suite."""
    evals = discover_evals(package)
    results = await asyncio.gather(*(run_eval(e) for e in evals))
    return EvalSuite(name=name, results=list(results))
