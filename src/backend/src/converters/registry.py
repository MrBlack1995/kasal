"""
Converter Registry

Registers all available converters with the converter factory.
Import this module to ensure all converters are registered.
"""

from converters.base.converter_factory import ConverterFactory
from converters.base.base_converter import ConversionFormat
from converters.implementations.yaml_to_dax import YAMLToDAXConverter
from converters.implementations.yaml_to_sql import YAMLToSQLConverter
from converters.implementations.yaml_to_uc_metrics import YAMLToUCMetricsConverter


def register_all_converters():
    """Register all available converters with the factory"""

    # YAML to DAX
    ConverterFactory.register(
        source_format=ConversionFormat.YAML,
        target_format=ConversionFormat.DAX,
        converter_class=YAMLToDAXConverter
    )

    # YAML to SQL
    ConverterFactory.register(
        source_format=ConversionFormat.YAML,
        target_format=ConversionFormat.SQL,
        converter_class=YAMLToSQLConverter
    )

    # YAML to UC Metrics
    ConverterFactory.register(
        source_format=ConversionFormat.YAML,
        target_format=ConversionFormat.UC_METRICS,
        converter_class=YAMLToUCMetricsConverter
    )


# Auto-register on import
register_all_converters()
