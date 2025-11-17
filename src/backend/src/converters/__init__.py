"""
Converters Package

This package contains all measure conversion logic including:
- YAML to DAX conversion
- YAML to SQL conversion
- YAML to UC Metrics conversion
- Power BI measure parsing and conversion

The package is organized into:
- base: Base classes and factory pattern
- measure: Core measure conversion logic
- formats: Input/output format handlers (YAML, DAX, SQL, UC Metrics, PBI)
- models: Data models for measures, KBIs, and conversions
- rules: Conversion rules and mappings between formats
- utils: Helper utilities for conversion operations
"""

from converters.base.base_converter import BaseConverter, ConversionFormat
from converters.base.converter_factory import ConverterFactory
from converters.implementations.yaml_to_dax import YAMLToDAXConverter
from converters.implementations.yaml_to_sql import YAMLToSQLConverter
from converters.implementations.yaml_to_uc_metrics import YAMLToUCMetricsConverter

# Import registry to auto-register all converters
import converters.registry  # noqa: F401

__all__ = [
    "BaseConverter",
    "ConversionFormat",
    "ConverterFactory",
    "YAMLToDAXConverter",
    "YAMLToSQLConverter",
    "YAMLToUCMetricsConverter",
]
