"""Memory subsystem evals — verify MemoryItem, LLM extractor, dedup, and hybrid retrieval."""

from __future__ import annotations

from evals.eval import EvalResult, EvalStatus


class MemoryItemSchemaEval:
    """MemoryItem has all contract-required fields with sensible defaults."""

    name = "memory_item_schema"

    async def run(self) -> EvalResult:
        try:
            from app.domain import DraftStatus, MemoryItem, MemoryKind, MemoryScope

            item = MemoryItem(id="test", content="likes coffee")
            checks = [
                ("kind", item.kind == MemoryKind.FACT),
                ("scope", item.scope == MemoryScope.USER),
                ("draft_status", item.draft_status == DraftStatus.CANONICAL),
                ("confidence", item.confidence == 1.0),
                ("keywords", item.keywords == []),
                ("lhs_entity_ids", item.lhs_entity_ids == []),
                ("expires_at", item.expires_at is None),
            ]
            failed = [name for name, ok in checks if not ok]
            if failed:
                return EvalResult(
                    name=self.name,
                    status=EvalStatus.FAIL,
                    message=f"field defaults wrong: {failed}",
                )
            return EvalResult(
                name=self.name,
                status=EvalStatus.PASS,
                score=1.0,
                message="MemoryItem schema matches contract",
            )
        except Exception as e:
            return EvalResult(
                name=self.name,
                status=EvalStatus.FAIL,
                message=f"exception: {e}",
            )


class MemoryDedupEval:
    """Near-duplicate detection collapses rephrased statements."""

    name = "memory_dedup"

    async def run(self) -> EvalResult:
        try:
            from app.domain import MemoryItem
            from app.memory.dedup import deduplicate, is_near_duplicate

            existing = [MemoryItem(id="1", content="I like coffee")]
            dup = MemoryItem(id="2", content="I really like coffee")
            not_dup = MemoryItem(id="3", content="I prefer tea")

            if not is_near_duplicate(dup, existing, threshold=0.7):
                return EvalResult(
                    name=self.name,
                    status=EvalStatus.FAIL,
                    message="near-duplicate not detected",
                )
            if is_near_duplicate(not_dup, existing, threshold=0.7):
                return EvalResult(
                    name=self.name,
                    status=EvalStatus.FAIL,
                    message="unrelated flagged as duplicate",
                )

            items = [
                MemoryItem(id="a", content="likes coffee"),
                MemoryItem(id="b", content="likes coffee"),
                MemoryItem(id="c", content="prefers tea"),
            ]
            result = deduplicate(items, threshold=0.9)
            if len(result) != 2:
                return EvalResult(
                    name=self.name,
                    status=EvalStatus.FAIL,
                    message=f"expected 2 unique, got {len(result)}",
                )

            return EvalResult(
                name=self.name,
                status=EvalStatus.PASS,
                score=1.0,
                message="dedup works correctly",
            )
        except Exception as e:
            return EvalResult(
                name=self.name,
                status=EvalStatus.FAIL,
                message=f"exception: {e}",
            )


class HybridWeightsEval:
    """HybridRetriever has configurable 0.6/0.4 default weights."""

    name = "hybrid_weights"

    async def run(self) -> EvalResult:
        try:
            from app.memory.hybrid_retriever import (
                DEFAULT_DENSE_WEIGHT,
                DEFAULT_SPARSE_WEIGHT,
            )

            if DEFAULT_DENSE_WEIGHT != 0.6:
                return EvalResult(
                    name=self.name,
                    status=EvalStatus.FAIL,
                    message=f"dense weight is {DEFAULT_DENSE_WEIGHT}, expected 0.6",
                )
            if DEFAULT_SPARSE_WEIGHT != 0.4:
                return EvalResult(
                    name=self.name,
                    status=EvalStatus.FAIL,
                    message=f"sparse weight is {DEFAULT_SPARSE_WEIGHT}, expected 0.4",
                )
            return EvalResult(
                name=self.name,
                status=EvalStatus.PASS,
                score=1.0,
                message="hybrid weights 0.6/0.4",
            )
        except Exception as e:
            return EvalResult(
                name=self.name,
                status=EvalStatus.FAIL,
                message=f"exception: {e}",
            )
