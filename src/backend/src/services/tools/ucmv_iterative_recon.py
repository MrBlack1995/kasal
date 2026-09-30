"""Iterative UCMV generation with reconciliation feedback.

Composes the three existing tools — the UC Metric View generator, the deployer,
and the reconciliation tool — into the ``run_reconciliation_loop`` control flow:
generate → deploy → reconcile → feed the failing measures back into the next
generation cycle, up to ``max_cycles`` or until a cell-alignment target is met.

The three tools are dependency-INJECTED (any object exposing ``_run(**kwargs) ->
json_str``), so the orchestration is unit-tested with fakes and never touches
Databricks or Power BI here. The caller — a crew/flow wiring, or the generator
when ``enable_reconciliation`` is set — constructs the real tools (the
reconciliation tool needs PBI/Databricks credentials at construction) and calls
this. Without it, generation stays single-pass, exactly as before.
"""

from __future__ import annotations

import dataclasses
import json
import logging
from typing import Any, Optional

from src.services.tools.metric_view_utils.reconciliation import (
    run_reconciliation_loop,
)

logger = logging.getLogger(__name__)


def _loads(raw: Any) -> dict:
    """Parse a tool's JSON string output into a dict; {} on anything unexpected."""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def run_iterative_ucmv_generation(
    *,
    generator,
    deployer,
    reconciler,
    gen_kwargs: Optional[dict] = None,
    deploy_kwargs: Optional[dict] = None,
    recon_kwargs: Optional[dict] = None,
    max_cycles: int = 5,
    target_pct: float = 100.0,
) -> dict:
    """Run the generate→deploy→reconcile→refine loop and return a JSON-able report.

    - ``generator._run(**gen_kwargs[, refinement_feedback])`` → output with
      ``yaml`` (dict of view→YAML) and ``pbi_ucmv_mapping`` (view→mapping).
    - ``deployer._run(yaml_specs_json=..., **deploy_kwargs)`` → deployment summary.
    - ``reconciler._run(mappings_json=..., **recon_kwargs)`` → reconciliation report.

    Returns ``{stop_reason, best_cycle, best_pct, cycles[], yaml, reconciliation}``.
    """
    gen_kwargs = dict(gen_kwargs or {})
    deploy_kwargs = dict(deploy_kwargs or {})
    recon_kwargs = dict(recon_kwargs or {})

    def generate(feedback) -> dict:
        kw = dict(gen_kwargs)
        if feedback:
            # The generator normalises this into the DAX LLM's per-measure hints.
            kw["refinement_feedback"] = json.dumps(feedback)
        out = _loads(generator._run(**kw))
        return {
            "yaml": out.get("yaml") or {},
            "mappings": out.get("pbi_ucmv_mapping") or {},
        }

    def deploy(yaml_specs) -> dict:
        if not yaml_specs:
            return {"ok": False, "error": "generator produced no YAML"}
        out = _loads(
            deployer._run(yaml_specs_json=json.dumps(yaml_specs), **deploy_kwargs)
        )
        summary = out.get("summary") or {}
        # A clean deploy: at least one view deployed and no hard errors. A
        # deployed_incomplete view (truncated YAML) still counts as not-ok so the
        # loop does not reconcile a measureless view.
        ok = summary.get("deployed", 0) > 0 and summary.get("errors", 0) == 0
        return {"ok": ok, "raw": out}

    def reconcile(yaml_specs, mappings) -> dict:
        if not mappings:
            return {"views": {}, "overall": {"cells_total": 0}}
        return _loads(
            reconciler._run(mappings_json=json.dumps(mappings), **recon_kwargs)
        )

    result = run_reconciliation_loop(
        generate=generate,
        deploy=deploy,
        reconcile=reconcile,
        max_cycles=max_cycles,
        target_pct=target_pct,
    )
    return {
        "stop_reason": result.stop_reason,
        "best_cycle": result.best_cycle,
        "best_pct": result.best_pct,
        "cycles": [dataclasses.asdict(c) for c in result.cycles],
        "yaml": result.final_yaml,
        "reconciliation": result.final_reconciliation,
    }


# Power BI credential/id fields on the generator → the reconciliation tool's
# constructor kwargs (the tool keeps creds out of its LLM-facing schema).
_GEN_TO_RECON_PBI = {
    "workspace_id": "pbi_workspace_id",
    "dataset_id": "pbi_dataset_id",
    "tenant_id": "pbi_tenant_id",
    "client_id": "pbi_client_id",
    "client_secret": "pbi_client_secret",
    "username": "pbi_username",
    "password": "pbi_password",
    "auth_method": "pbi_auth_method",
    "access_token": "pbi_access_token",
}


def run_from_generator(generator_tool, kwargs: dict) -> Optional[dict]:
    """Bridge from the UC Metric View generator's ``enable_reconciliation`` toggle
    to the iterative loop. Returns the loop report, or ``None`` when prerequisites
    are missing (caller then falls back to single-pass generation).

    The generate step re-invokes the SAME generator with ``enable_reconciliation``
    off and an ``_in_recon_loop`` guard, so there is no infinite recursion.
    """

    def cfg(key):
        val = kwargs.get(key)
        if val is None:
            val = getattr(generator_tool, "_default_config", {}).get(key)
        return val

    warehouse_id = cfg("warehouse_id")
    reference_years = cfg("reference_years")
    if isinstance(reference_years, str):
        try:
            reference_years = json.loads(reference_years)
        except json.JSONDecodeError:
            reference_years = [
                y.strip() for y in reference_years.split(",") if y.strip()
            ]
    # Reconciliation deploys + queries a live view; without a warehouse and the
    # years to compare there is nothing to reconcile — degrade to single-pass.
    if not warehouse_id or not reference_years:
        logger.info(
            "[UCMV] enable_reconciliation set but warehouse_id/reference_years "
            "missing — running single-pass generation."
        )
        return None

    from src.services.tools.metric_view_deployer_tool import MetricViewDeployerTool
    from src.services.tools.ucmv_reconciliation_tool import UCMVReconciliationTool

    gen_kwargs = dict(kwargs)
    gen_kwargs["enable_reconciliation"] = False  # recursion guard
    gen_kwargs["_in_recon_loop"] = True

    recon_ctor = {
        recon_key: cfg(gen_key)
        for gen_key, recon_key in _GEN_TO_RECON_PBI.items()
        if cfg(gen_key) is not None
    }
    reconciler = UCMVReconciliationTool(**recon_ctor)

    return run_iterative_ucmv_generation(
        generator=generator_tool,
        deployer=MetricViewDeployerTool(),
        reconciler=reconciler,
        gen_kwargs=gen_kwargs,
        deploy_kwargs={
            "warehouse_id": warehouse_id,
            "catalog": cfg("catalog"),
            "schema_name": cfg("schema_name"),
            "databricks_host": cfg("llm_workspace_url"),
        },
        recon_kwargs={
            "warehouse_id": warehouse_id,
            "reference_years": reference_years,
        },
        max_cycles=int(cfg("max_reconciliation_cycles") or 5),
        target_pct=float(cfg("reconciliation_target_pct") or 100.0),
    )
