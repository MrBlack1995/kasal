"""Service: learn reusable domain context from customer-corrected UCMVs.

The flywheel. Kasal generates UC Metric View YAML → the customer validates, fixes
and deploys it → this service fetches our ORIGINAL output for the same views from
conversion history (through the OWNING ``ConverterService`` — never its
repository), pairs it with the customer's corrected YAML by view name, diffs them,
and asks the LLM to distil the recurring corrections into a domain-context README
(the free text the generator's ``domain_context`` field consumes). The next
generation then starts closer to what the customer actually wants.

The pure diff/prompt logic lives in
``metric_view_utils.correction_learning``; this layer owns the orchestration:
fetching originals and running the (async) LLM call.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.schemas.conversion import ConversionHistoryFilter
from src.services.llm.manager import LLMManager
from src.services.powerbi.conversions import ConverterService
from src.services.tools.metric_view_utils.correction_learning import (
    diff_all,
    distillation_messages,
)
from src.utils.user_context import GroupContext

logger = logging.getLogger(__name__)

_DISTILL_MODEL = "databricks-claude-sonnet-4-5"


class UCMVCorrectionLearningService:
    """Distil a reusable domain-context README from customer-corrected UCMVs."""

    def __init__(self, session, group_context: Optional[GroupContext] = None):
        # Accept the request session; reach conversion history through its owning
        # service (never open a session or build its repository here).
        self.session = session
        self.group_context = group_context

    async def _fetch_original_yaml(self, execution_id: Optional[str]) -> Dict[str, str]:
        """Our original generated UCMV YAML ({view -> yaml}) for this group.

        Prefers a specific ``execution_id``; otherwise takes the most recent
        PowerBI→UC-metrics conversion for the group (history is DESC-ordered).
        """
        converter = ConverterService(self.session, group_context=self.group_context)
        if execution_id:
            flt = ConversionHistoryFilter(execution_id=execution_id)
        else:
            flt = ConversionHistoryFilter(
                source_format="powerbi_dax",
                target_format="uc_metrics",
                limit=10,
            )
        resp = await converter.list_history(flt)
        for h in resp.history:  # newest first
            output = getattr(h, "output_data", None) or {}
            yaml_map = output.get("yaml") if isinstance(output, dict) else None
            if isinstance(yaml_map, dict) and yaml_map:
                return {str(k): str(v) for k, v in yaml_map.items()}
        return {}

    async def learn(
        self,
        corrected: Dict[str, str],
        execution_id: Optional[str] = None,
        model_hint: str = "",
    ) -> Dict[str, Any]:
        """Diff uploaded corrected UCMVs against our originals and distil a README.

        ``corrected`` is ``{view_name -> corrected_yaml}``. Returns the README (or
        None when there's nothing material to learn) plus match/change counts so
        the UI can explain the outcome.
        """
        corrected = {
            str(k): str(v) for k, v in (corrected or {}).items() if v and str(v).strip()
        }
        if not corrected:
            return {"readme": None, "error": "No corrected UCMV YAML provided."}

        originals = await self._fetch_original_yaml(execution_id)
        pairs: List[Dict[str, str]] = [
            {"view": v, "original_yaml": originals.get(v, ""), "corrected_yaml": y}
            for v, y in corrected.items()
        ]
        diffs = diff_all(pairs)
        matched = sorted(v for v in corrected if v in originals)
        unmatched = sorted(v for v in corrected if v not in originals)

        base = {
            "views_analyzed": len(pairs),
            "views_with_changes": len(diffs),
            "matched_views": matched,
            "unmatched_views": unmatched,
        }

        if not diffs:
            note = "No material differences found between the uploaded UCMVs and our original output"
            if not matched:
                note += " (and no original matched by view name — check the view names or supply the execution_id)"
            return {"readme": None, "note": note + ".", **base}

        messages = distillation_messages(diffs, model_hint)
        try:
            content = await LLMManager.completion(
                messages=messages, model=_DISTILL_MODEL, max_tokens=4000
            )
        except Exception as e:  # noqa: BLE001 — surface, don't crash the request
            logger.warning(f"[UCMVLearning] distillation LLM call failed: {e}")
            return {"readme": None, "error": f"Distillation failed: {e}", **base}

        readme = content[0] if isinstance(content, tuple) else content
        return {"readme": readme, **base}
