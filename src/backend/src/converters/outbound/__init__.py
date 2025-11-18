"""
Outbound converters - Export FROM internal KBI model TO external formats.

This package contains converters that generate external format output
from the internal KBI (Key Business Indicator) representation.

Supported Output Formats:
- DAX (Power BI measures)
- SQL (Multiple dialects: Databricks, PostgreSQL, MySQL, SQL Server, Snowflake, BigQuery)
- Unity Catalog Metrics (Databricks UC Metrics Store)

Future Formats:
- Tableau
- Looker
- DBT
"""

# DAX exports
from converters.outbound.dax.generator import DAXGenerator

# SQL exports
from converters.outbound.sql.generator import SQLGenerator
from converters.outbound.sql.models import (
    SQLDialect,
    SQLAggregationType,
    SQLTranslationOptions,
    SQLTranslationResult,
)

# UC Metrics exports
from converters.outbound.uc_metrics.generator import UCMetricsGenerator

__all__ = [
    # DAX
    "DAXGenerator",
    # SQL
    "SQLGenerator",
    "SQLDialect",
    "SQLAggregationType",
    "SQLTranslationOptions",
    "SQLTranslationResult",
    # UC Metrics
    "UCMetricsGenerator",
]
