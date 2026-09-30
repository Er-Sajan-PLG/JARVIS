# app/models/client.py
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class ModelResponse:
    content: str
    model: str
    tokens_used: int | None = None
    finish_reason: str | None = None


@runtime_checkable
class ModelClient(Protocol):
    """Protocol defining the model client interface.

    ``@runtime_checkable`` exists so a test or an adapter can assert that an
    object actually satisfies this Protocol instead of merely looking like it
    does. Without it, ``isinstance(x, ModelClient)`` raises TypeError, and the
    only way to "check" was to mock the class under test -- which is how
    ``ModelSwitcher`` spent months calling methods on a ``ModelRouter`` that has
    never had them, with a green suite.

    Note what this does and does not buy: ``isinstance`` checks that the named
    members are present, not that their signatures match. It catches a renamed
    or missing method; it will not catch a changed parameter list.
    """

    def generate(
        self,
        messages: list[dict],
        stream: bool = False,
        on_token: Callable[[str], None] = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate a response. If stream=True, calls on_token for each chunk."""
        ...

    @property
    def model_name(self) -> str: ...

    @property
    def role(self) -> str: ...
