"""Aggregation rules for DAX and SQL"""

from converters.rules.aggregations.dax_aggregations import detect_and_build_aggregation
from converters.rules.aggregations.sql_aggregations import SQLAggregationBuilder

__all__ = [
    "detect_and_build_aggregation",
    "SQLAggregationBuilder",
]
