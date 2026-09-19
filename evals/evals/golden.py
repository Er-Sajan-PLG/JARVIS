"""Golden-dataset evals (Sprint 10.4).

A small curated dataset of "facts that must hold" for the comms/chat surfaces,
judged deterministically (no model call) so the gate stays fast and stable.
Each case is a behavioral contract: intent classification, brief shape,
notify channel validation. A regression here is a real contract break.
"""

from __future__ import annotations

from evals.eval import EvalResult, EvalStatus

# Curated behavioral contracts, no network.
GOLDEN_CASES = [
    # (name, intent-trigger message, should_be_email_context, should_be_brief)
    ("email_ask", "What important email did I miss?", True, False),
    ("email_inbox", "check my inbox", True, False),
    ("brief_ask", "send me today's brief", False, True),
    ("brief_morning", "morning briefing please", False, True),
    ("plain_chat", "hello JARVIS", False, False),
    ("no_false_email", "write a poem about blackmail", False, False),
]


class GoldenIntentEval:
    """Chat context-injection triggers match the golden dataset."""

    name = "golden_intent"

    async def run(self) -> EvalResult:
        from app.adapters.web.router import _wants_brief, _wants_email_context

        failures = []
        for name, msg, want_email, want_brief in GOLDEN_CASES:
            got_email = _wants_email_context(msg)
            got_brief = _wants_brief(msg)
            if got_email != want_email or got_brief != want_brief:
                failures.append(
                    f"{name}: email={got_email}/{want_email}, brief={got_brief}/{want_brief}"
                )
        if failures:
            return EvalResult(
                name=self.name,
                status=EvalStatus.FAIL,
                message="golden intent mismatches: " + "; ".join(failures),
            )
        return EvalResult(
            name=self.name,
            status=EvalStatus.PASS,
            score=1.0,
            message=f"{len(GOLDEN_CASES)} golden intent cases hold",
        )


class GoldenBriefShapeEval:
    """The brief always has the four sections."""

    name = "golden_brief_shape"

    async def run(self) -> EvalResult:
        from app.integrations.brief import BriefConfig, BriefService

        service = BriefService(BriefConfig(enabled=True))
        try:
            brief = await service.generate_brief()
        except Exception as e:  # noqa: BLE001
            return EvalResult(
                name=self.name,
                status=EvalStatus.FAIL,
                message=f"brief generation failed: {e}",
            )
        titles = [s["title"] for s in brief.get("sections", [])]
        expected = {"Memory", "Pending Approvals", "Recent Activity", "Email"}
        missing = expected - set(titles)
        if missing:
            return EvalResult(
                name=self.name,
                status=EvalStatus.FAIL,
                message=f"brief missing sections: {sorted(missing)}",
            )
        return EvalResult(
            name=self.name,
            status=EvalStatus.PASS,
            score=1.0,
            message="brief has all four sections",
        )


class GoldenNotifyChannelsEval:
    """Notify dispatcher accepts only the known channels."""

    name = "golden_notify_channels"

    async def run(self) -> EvalResult:
        from app.adapters.web.notify_routes import VALID_CHANNELS

        expected = {"push", "telegram", "whatsapp"}
        if set(VALID_CHANNELS) != expected:
            return EvalResult(
                name=self.name,
                status=EvalStatus.FAIL,
                message=f"VALID_CHANNELS={VALID_CHANNELS}, expected {expected}",
            )
        return EvalResult(
            name=self.name,
            status=EvalStatus.PASS,
            score=1.0,
            message=f"{len(VALID_CHANNELS)} notify channels registered",
        )
