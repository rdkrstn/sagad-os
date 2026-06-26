"""RevOps tiered auto-send "safe lane".

The guardrail (`graph.run_guardrail`) only ever emits `needs_review` or `blocked` -- never
`pass` -- so the auto-send gate in `_maybe_auto_send_universal` (which requires
`compliance_status == "pass"`) was dormant dead code: every conversation landed in
`needs_approval` and nothing ever auto-sent.

This module defines a narrow, explicit allowlist that may PROMOTE a `needs_review` verdict to
`pass` so a low-risk, high-confidence, allowlisted-intent reply can auto-send without a
supervisor round-trip. The promotion is applied in `_run_universal_inbound` AFTER the graph
runs and BEFORE the record is built, and only when the guardrail did NOT say "blocked" -- so a
block always wins. With the default EMPTY allowlist, no promotion ever happens and the prior
needs_approval behavior is unchanged.

Safety posture: worst case the allowlist is too narrow and we over-queue (a human approves);
we can never over-send past a guardrail block. Start conservative (`pricing_faq`,
`business_hours`, `status_check`) and watch `eval_tags` / `quality_signals`.
"""

from __future__ import annotations

from typing import Any, Mapping


def revops_autosend_decision(state: Mapping[str, Any], settings: Any) -> str | None:
    """Return "pass" when this state is eligible for the auto-send safe lane, else None.

    Eligibility (all required):
      * `revops_autosend_enabled` is True (kill-switch);
      * `intent` is in `revops_autosend_intents` (empty by default -> never eligible);
      * `risk_level == "low"`;
      * confidence (`final_confidence_score`, falling back to `retrieval_confidence`)
        >= `revops_autosend_confidence`;
      * a non-empty `draft_reply`.

    The caller is responsible for the "guardrail blocked always wins" rule: this function does
    not inspect `compliance_status`, so it must only be consulted when compliance != "blocked".
    """
    if not getattr(settings, "revops_autosend_enabled", True):
        return None
    allowlist = getattr(settings, "revops_autosend_intents", None) or []
    if not allowlist:
        return None
    intent = str(state.get("intent") or "")
    if intent not in allowlist:
        return None
    if str(state.get("risk_level") or "") != "low":
        return None
    confidence = state.get("final_confidence_score")
    if confidence is None:
        confidence = state.get("retrieval_confidence")
    if confidence is None:
        return None
    threshold = float(getattr(settings, "revops_autosend_confidence", 0.88))
    try:
        if float(confidence) < threshold:
            return None
    except (TypeError, ValueError):
        return None
    if not str(state.get("draft_reply") or "").strip():
        return None
    return "pass"