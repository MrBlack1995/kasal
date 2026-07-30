"""Unit tests for best-effort UCMV generation (thin-report fallback).

Covers `UCMetricViewGeneratorTool._build_best_effort_views` — the opt-in path that
drafts thin metric views for a report-layer model (no M-Query source tables) from
measures that already resolved to real aggregatable SQL. Key guarantees:
  * never emits unresolved / TODO SQL (correctness contract),
  * skips tables with no supplied source and surfaces them in the report,
  * flags every emitted measure `TODO: verify`,
  * empty / absent fact_source_map → no views (gate).
"""
import pytest

from src.engines.crewai.tools.custom.uc_metric_view_generator_tool import (
    UCMetricViewGeneratorTool,
)


def _config(resolutions):
    return {"measure_resolutions": resolutions}


def _measures(pairs):
    # pairs: list of (measure_name, allocated_pbi_table)
    return [{"measure_name": n, "proposed_allocation": t} for n, t in pairs]


class TestBuildBestEffortViews:
    def test_emits_view_for_resolved_measure_with_source(self):
        views, report = UCMetricViewGeneratorTool._build_best_effort_views(
            fact_source_map={"sat_roi_main": "cat.sch.sat_roi"},
            config=_config({
                "cm_abs": {"base_expr": "SUM(source.customer_margin_abs)", "base_filters": []},
            }),
            measures=_measures([("cm_abs", "sat_roi_main")]),
        )
        assert "sat_roi_main" in views
        v = views["sat_roi_main"]
        assert v["source"] == "cat.sch.sat_roi"
        assert v["version"] == "1.1"
        assert len(v["measures"]) == 1
        m = v["measures"][0]
        assert m["expr"] == "SUM(source.customer_margin_abs)"
        assert m["name"] == "cm_abs"
        # every drafted measure must be flagged for review
        assert "TODO: verify" in m["comment"]
        # view comment must warn about missing content
        assert "MISSING" in v["comment"]
        assert report["tables_emitted"] == 1
        assert report["measures_emitted"] == 1
        assert report["mode"] == "best_effort"

    def test_never_emits_todo_or_nonagg_sql(self):
        views, report = UCMetricViewGeneratorTool._build_best_effort_views(
            fact_source_map={"t": "cat.sch.t"},
            config=_config({
                "good": {"base_expr": "SUM(source.x)", "base_filters": []},
                "todo": {"base_expr": "TODO: fill SQL expression", "base_filters": []},
                "selector": {"base_expr": "SELECTEDVALUE(foo)", "base_filters": []},
                "empty": {"base_expr": "", "base_filters": []},
            }),
            measures=_measures([("good", "t"), ("todo", "t"), ("selector", "t"), ("empty", "t")]),
        )
        emitted = {m["name"] for m in views["t"]["measures"]}
        assert emitted == {"good"}  # only the real aggregate
        assert report["measures_emitted"] == 1
        assert report["measures_skipped_unresolved"] == 3
        assert set(report["skipped_measures"]) == {"todo", "selector", "empty"}

    def test_applies_base_filters(self):
        views, _ = UCMetricViewGeneratorTool._build_best_effort_views(
            fact_source_map={"t": "cat.sch.t"},
            config=_config({
                "m": {"base_expr": "SUM(source.v)", "base_filters": ["source.flag = 1", "source.reg = 'X'"]},
            }),
            measures=_measures([("m", "t")]),
        )
        assert views["t"]["measures"][0]["expr"] == \
            "SUM(source.v) FILTER (WHERE source.flag = 1 AND source.reg = 'X')"

    def test_table_without_source_is_skipped_and_reported(self):
        views, report = UCMetricViewGeneratorTool._build_best_effort_views(
            fact_source_map={"has_source": "cat.sch.a"},
            config=_config({
                "m1": {"base_expr": "SUM(source.x)", "base_filters": []},   # alloc -> has_source
                "m2": {"base_expr": "SUM(source.y)", "base_filters": []},   # alloc -> no_source (not mapped)
            }),
            measures=_measures([("m1", "has_source"), ("m2", "no_source")]),
        )
        # only the mapped table is emitted; m2's table isn't in fact_source_map
        assert set(views) == {"has_source"}
        assert report["measures_emitted"] == 1

    def test_mapped_table_with_no_resolved_measures_reported_missing(self):
        views, report = UCMetricViewGeneratorTool._build_best_effort_views(
            fact_source_map={"empty_table": "cat.sch.e"},
            config=_config({}),
            measures=_measures([]),
        )
        assert views == {}
        assert "empty_table" in report["tables_without_source"]

    @pytest.mark.parametrize("fsm", [None, {}, "not-a-dict-and-not-json"])
    def test_no_source_map_gate_returns_no_views(self, fsm):
        views, report = UCMetricViewGeneratorTool._build_best_effort_views(
            fact_source_map=fsm,
            config=_config({"m": {"base_expr": "SUM(source.x)", "base_filters": []}}),
            measures=_measures([("m", "t")]),
        )
        assert views == {}
        assert report["tables_emitted"] == 0

    def test_report_carries_missing_warning(self):
        _, report = UCMetricViewGeneratorTool._build_best_effort_views(
            fact_source_map={"t": "cat.sch.t"},
            config=_config({"m": {"base_expr": "SUM(source.x)", "base_filters": []}}),
            measures=_measures([("m", "t")]),
        )
        assert "may be MISSING" in report["warning"]
        assert "upstream semantic model" in report["warning"]
