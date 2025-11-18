"""
Converters Package - Measure Conversion Library

This package provides conversion logic for business measures between formats.

## Data Flow

                    ┌─────────────┐
    INBOUND  ──────►│ KBI Model   │──────► OUTBOUND
                    │  (Internal) │
                    └─────────────┘

    FROM external       Unified           TO external
    formats            representation      formats

## Architecture

converters/
├── base/              # Framework + core models (BaseConverter, KBI, etc.)
├── common/            # Shared utilities (parsers, translators, processors)
├── models/            # Model aggregator (re-exports for convenience)
├── inbound/           # Input converters (FROM external → KBI)
│   └── pbi/          # Power BI → YAML/KBI
└── outbound/          # Output converters (FROM KBI → external)
    ├── dax/          # KBI → DAX (Power BI measures)
    ├── sql/          # KBI → SQL (multiple dialects)
    └── uc_metrics/   # KBI → Unity Catalog Metrics

## Supported Conversions

### Inbound (Import):
- Power BI (.pbix) → KBI (future)
- Tableau → KBI (future)
- Excel → KBI (future)

### Outbound (Export):
- KBI → DAX (Power BI)
- KBI → SQL (Databricks, PostgreSQL, MySQL, SQL Server, Snowflake, BigQuery)
- KBI → Unity Catalog Metrics (Databricks)

## Usage

### Direct Usage (API/Service layer):
```python
from converters.outbound.dax.generator import DAXGenerator
from converters.common.parsers.yaml import YAMLKPIParser

parser = YAMLKPIParser()
generator = DAXGenerator()

definition = parser.parse_file("measures.yaml")
measures = [generator.generate_dax_measure(definition, kbi) for kpi in definition.kpis]
```

### CrewAI Tools:
Use front-end facing tools in engines/crewai/tools/custom/:
- YAMLToDAXTool
- YAMLToSQLTool
- YAMLToUCMetricsTool
"""

# Base framework and core models
from converters.base import (
    BaseConverter,
    ConversionFormat,
    ConverterFactory,
    KBI,
    KPIDefinition,
    DAXMeasure,
    SQLMeasure,
    UCMetric,
)

__all__ = [
    # Framework
    "BaseConverter",
    "ConversionFormat",
    "ConverterFactory",
    # Models
    "KBI",
    "KPIDefinition",
    "DAXMeasure",
    "SQLMeasure",
    "UCMetric",
]
