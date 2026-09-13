"""Settings, model routing and budgets (docs/01 §3).

Credentials are read unprefixed (TAVILY_API_KEY, ...), which is both what
.env.example ships and what the vendor SDKs read from os.environ themselves.
Everything else takes PRIME_-prefixed, __-nested overrides (PRIME_MODELS__ROOT).
pydantic-settings does not apply env_prefix to a field carrying an explicit
alias, which is what lets both forms coexist.
"""

from __future__ import annotations

import difflib
import os
import warnings
from collections.abc import Mapping
from functools import lru_cache

from pydantic import AliasChoices, BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelRouting(BaseModel):
    """Verified Nebius Token Factory IDs (docs/01 §4). `make smoke` decides
    fallbacks; never switch silently."""

    root: str = "nvidia/nemotron-3-super-120b-a12b"
    critic: str = "nvidia/nemotron-3-super-120b-a12b"
    subagent: str = "moonshotai/Kimi-K2.6"
    judge: str = "deepseek-ai/DeepSeek-V4-Flash-0731"  # reports/model-selection.md; 2026-09-13
    extractor: str = "moonshotai/Kimi-K2.6"
    evaluator: str = "moonshotai/Kimi-K2.6"
    baseline: str = "moonshotai/Kimi-K2.6"  # starter default; do not change


class Budget(BaseModel):
    max_searches: int = 30
    max_fetches: int = 20
    max_deep_reads: int = 10  # search_within calls
    max_agents: int = 6  # sub-agents per round
    max_rounds: int = 3  # all search rounds, the initial one included; the critic may add one
    max_tokens: int = 150_000
    max_seconds: int = 180


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="PRIME_",  # -> PRIME_MODELS__ROOT, PRIME_BUDGET_DEEP__MAX_SEARCHES
        env_nested_delimiter="__",
        case_sensitive=False,  # required for the uppercase AliasChoices below
        extra="ignore",
    )

    # env_prefix is skipped for aliased fields, so these stay unprefixed while
    # still accepting the prefixed form; first match wins.
    tavily_api_key: str = Field(
        ..., validation_alias=AliasChoices("PRIME_TAVILY_API_KEY", "TAVILY_API_KEY")
    )
    nebius_api_key: str = Field(
        ..., validation_alias=AliasChoices("PRIME_NEBIUS_API_KEY", "NEBIUS_API_KEY")
    )
    langsmith_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PRIME_LANGSMITH_API_KEY", "LANGSMITH_API_KEY"),
    )
    langsmith_project: str = Field(
        default="prime-search",
        validation_alias=AliasChoices("PRIME_LANGSMITH_PROJECT", "LANGSMITH_PROJECT"),
    )

    models: ModelRouting = ModelRouting()
    # Round 0's sub-agents alone spend ~175-195k tokens and all ten deep reads on a deep
    # question (measured live, 2026-09-13); these leave room for a judge round and the
    # critic's (docs/11). Deep reads are local BM25 over fetched text, not Tavily calls.
    budget_deep: Budget = Budget(max_tokens=400_000, max_deep_reads=30)
    budget_fast: Budget = Budget(
        max_searches=3, max_fetches=2, max_agents=1, max_rounds=1, max_seconds=30
    )
    tavily_cache: bool = True  # cache search/extract by args (used in bench + GEPA)
    tavily_cache_dir: str = ".cache/tavily"

    def budget(self, depth: str) -> Budget:
        return self.budget_fast if depth == "fast" else self.budget_deep

    def export_sdk_env(self) -> None:
        """Push .env-loaded credentials back into os.environ.

        pydantic-settings reads .env without exporting it, but the langsmith
        client and langchain-tavily's default client read os.environ directly.
        setdefault, so a real shell variable always wins.
        """
        os.environ.setdefault("TAVILY_API_KEY", self.tavily_api_key)
        os.environ.setdefault("NEBIUS_API_KEY", self.nebius_api_key)
        os.environ.setdefault("LANGSMITH_PROJECT", self.langsmith_project)
        if self.langsmith_api_key:
            os.environ.setdefault("LANGSMITH_API_KEY", self.langsmith_api_key)

    @property
    def tracing_enabled(self) -> bool:
        return bool(self.langsmith_api_key)


def _known_override_names() -> set[str]:
    """Every PRIME_-prefixed variable this Settings actually reads."""
    names = set()
    for field, info in Settings.model_fields.items():
        names.add(f"PRIME_{field}".upper())
        annotation = info.annotation
        nested = getattr(annotation, "model_fields", None)
        if nested:  # ModelRouting, Budget -> PRIME_MODELS__ROOT, PRIME_BUDGET_DEEP__...
            for sub in nested:
                names.add(f"PRIME_{field}__{sub}".upper())
    return names


def unknown_overrides(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """PRIME_-prefixed variables that match no field, with the nearest real name.

    `extra="ignore"` means a mistyped override is dropped in silence — which is how
    `PRIME_MODELS__SUB` sat in a .env doing nothing while looking deliberate. The
    field is `subagent`, so the working name is `PRIME_MODELS__SUBAGENT`.
    """
    environ = os.environ if environ is None else environ
    known = _known_override_names()
    found: dict[str, str] = {}
    for name in environ:
        upper = name.upper()
        if not upper.startswith("PRIME_") or upper in known:
            continue
        closest = difflib.get_close_matches(upper, sorted(known), n=1, cutoff=0.6)
        found[name] = closest[0] if closest else ""
    return found


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings. Raises on a missing required key, naming the field.

    Warns rather than raises on an unrecognized PRIME_ override: a stale variable in
    someone's shell should not stop a run, but it must not be invisible either.
    """
    for name, suggestion in unknown_overrides().items():
        hint = f"; did you mean {suggestion}?" if suggestion else ""
        warnings.warn(
            f"{name} is set but matches no Settings field, so it has no effect{hint}",
            RuntimeWarning,
            stacklevel=2,
        )
    settings = Settings()  # type: ignore[call-arg]  # values come from env/.env
    settings.export_sdk_env()
    return settings
