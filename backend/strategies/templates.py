"""Base class and registry for strategy templates."""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuleSpec:
    """Specification for a single monitor rule to be created."""
    name: str
    trigger_type: str
    trigger_config: dict[str, Any]
    action_type: str
    action_config: dict[str, Any]
    max_fires: int | None = 1
    expires: str | None = "today"
    # Placeholder for cross-referencing rules within a strategy.
    # "sl", "target", "trailing", "entry", "squareoff" etc.
    role: str = ""
    # Whether the rule starts enabled. Exit rules in bidirectional strategies
    # (e.g. ORB) start disabled and are activated when their entry fires.
    enabled: bool = True
    # Kill chain: when this rule fires, disable rules with these roles.
    # Resolved to actual rule IDs at deploy time.
    kills_roles: list[str] = field(default_factory=list)
    # Activate chain: when this rule fires, enable rules with these roles.
    # Resolved to actual rule IDs at deploy time.
    activates_roles: list[str] = field(default_factory=list)


@dataclass
class StrategyPlan:
    """Complete plan for a strategy deployment — rules to create."""
    template_name: str
    symbol: str
    group_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    rules: list[RuleSpec] = field(default_factory=list)
    summary: str = ""
    params: dict[str, Any] = field(default_factory=dict)


class StrategyTemplate(ABC):
    """Base class for strategy templates."""

    name: str = ""
    description: str = ""
    category: str = "equity"
    # Required params the user must provide
    required_params: list[str] = []
    # Optional params with defaults
    optional_params: dict[str, Any] = {}

    @abstractmethod
    def plan(self, symbol: str, params: dict[str, Any]) -> StrategyPlan:
        """Generate a StrategyPlan (list of RuleSpecs) from parameters.

        This does NOT create rules in the DB — it returns a plan that can be
        previewed (dry-run) or executed.
        """
        ...

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate and fill defaults for strategy parameters."""
        merged = dict(self.optional_params)
        merged.update(params)
        missing = [p for p in self.required_params if p not in merged]
        if missing:
            raise ValueError(f"Missing required parameters: {', '.join(missing)}")
        return merged

    def info(self) -> dict[str, Any]:
        """Return template metadata for listing."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "required_params": self.required_params,
            "optional_params": self.optional_params,
        }


# ── Template Registry ─────────────────────────────────────────────────────

_registry: dict[str, StrategyTemplate] = {}


def register(template: StrategyTemplate) -> None:
    _registry[template.name] = template


def get_template(name: str) -> StrategyTemplate | None:
    return _registry.get(name)


def list_templates() -> list[dict[str, Any]]:
    return [t.info() for t in _registry.values()]


def _register_all() -> None:
    """Import and register all built-in templates."""
    from strategies.orb import ORBTemplate
    from strategies.breakout import BreakoutTemplate
    from strategies.mean_reversion import MeanReversionTemplate
    from strategies.vwap_bounce import VWAPBounceTemplate
    from strategies.scalp import ScalpTemplate
    from strategies.straddle import StraddleTemplate
    from strategies.strangle import StrangleTemplate
    from strategies.bull_call_spread import BullCallSpreadTemplate
    from strategies.bear_put_spread import BearPutSpreadTemplate
    from strategies.iron_condor import IronCondorTemplate
    from strategies.ema_cross import EMACrossLongTemplate, EMACrossShortTemplate, EMACrossPairTemplate
    from strategies.ema_stochastic_scalper import EMAStochasticScalperTemplate

    for cls in (
        ORBTemplate, BreakoutTemplate, MeanReversionTemplate,
        VWAPBounceTemplate, ScalpTemplate,
        StraddleTemplate, StrangleTemplate, BullCallSpreadTemplate,
        BearPutSpreadTemplate, IronCondorTemplate,
        EMACrossLongTemplate, EMACrossShortTemplate, EMACrossPairTemplate,
        EMAStochasticScalperTemplate,
    ):
        register(cls())


# Auto-register on first import
_register_all()
