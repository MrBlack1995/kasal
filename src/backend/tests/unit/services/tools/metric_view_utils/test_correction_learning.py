"""Core of the 'learn from customer-corrected UCMVs' flywheel: diff + distill."""

from src.services.tools.metric_view_utils.correction_learning import (
    build_distillation_prompt,
    diff_all,
    diff_view,
    distill_corrections_to_readme,
)

_ORIG = """
source: cat.sch.fact_sales
filter: ""
measures:
  - name: revenue
    expr: SUM(source.amount)
  - name: cost
    expr: SUM(source.cost_components)
  - name: legacy_only
    expr: SUM(source.x)
"""

_CORR = """
source: cat.sch.fact_sales_v2
filter: "source.version = '0000'"
measures:
  - name: revenue
    expr: SUM(source.amount)
  - name: cost
    expr: SUM(source.booked_cost)
  - name: margin
    expr: MEASURE(revenue) - MEASURE(cost)
"""


def test_diff_view_detects_changed_added_removed_and_source_filter():
    d = diff_view(_ORIG, _CORR)
    changed = {c["name"] for c in d["changed_measures"]}
    assert changed == {"cost"}  # revenue identical, cost expr changed
    assert d["changed_measures"][0]["to_expr"] == "SUM(source.booked_cost)"
    assert [m["name"] for m in d["added_measures"]] == ["margin"]
    assert d["removed_measures"] == ["legacy_only"]
    assert d["source_from"] != d["source_to"]
    assert d["filter_to"] == "source.version = '0000'"


def test_whitespace_only_change_is_not_flagged():
    a = "measures:\n  - name: r\n    expr: SUM(source.a)\n"
    b = "measures:\n  - name: r\n    expr: SUM(source.a)\n"  # same
    assert diff_view(a, b)["changed_measures"] == []


def test_diff_all_drops_views_with_no_change():
    pairs = [
        {"view": "fact_sales", "original_yaml": _ORIG, "corrected_yaml": _CORR},
        {"view": "fact_noop", "original_yaml": _ORIG, "corrected_yaml": _ORIG},
    ]
    out = diff_all(pairs)
    assert set(out) == {"fact_sales"}


def test_malformed_yaml_is_safe():
    d = diff_view("::: not yaml :::", _CORR)
    # Original parsed empty → every corrected measure reads as "added", no crash.
    assert {m["name"] for m in d["added_measures"]} == {"revenue", "cost", "margin"}


def test_prompt_includes_the_concrete_corrections():
    diffs = diff_all(
        [{"view": "fact_sales", "original_yaml": _ORIG, "corrected_yaml": _CORR}]
    )
    prompt = build_distillation_prompt(diffs, model_hint="Total SC")
    assert "Total SC" in prompt
    assert "booked_cost" in prompt
    assert "fact_sales" in prompt


def test_distill_returns_none_when_nothing_changed():
    assert distill_corrections_to_readme({}, lambda s, u: "x") is None


def test_distill_invokes_llm_and_returns_readme():
    diffs = diff_all(
        [{"view": "fact_sales", "original_yaml": _ORIG, "corrected_yaml": _CORR}]
    )
    captured = {}

    def fake_llm(system, user):
        captured["system"] = system
        captured["user"] = user
        return "# Learned context\n- Prefer booked_cost."

    out = distill_corrections_to_readme(diffs, fake_llm, model_hint="Total SC")
    assert out and out.startswith("# Learned context")
    assert "booked_cost" in captured["user"]
    assert "GENERALISABLE" in captured["system"]
