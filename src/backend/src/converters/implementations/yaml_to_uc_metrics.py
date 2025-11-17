"""YAML to Unity Catalog Metrics Converter Implementation"""

from typing import Any, Dict, List
from converters.base.base_converter import BaseConverter, ConversionFormat
from converters.formats.parsers.yaml_parser import YAMLKBIParser
from converters.processors.structure_processor import StructureProcessor
from converters.processors.uc_metrics_processor import UCMetricsProcessor
from converters.models.kbi import KBIDefinition


class YAMLToUCMetricsConverter(BaseConverter):
    """
    Converts YAML measure definitions to Unity Catalog Metrics format.

    This converter:
    1. Parses YAML input into KBI definitions
    2. Processes structures for time intelligence
    3. Generates UC Metrics store definitions
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.yaml_parser = YAMLKBIParser()
        self.structure_processor = StructureProcessor()
        self.uc_processor = UCMetricsProcessor()

    @property
    def source_format(self) -> ConversionFormat:
        return ConversionFormat.YAML

    @property
    def target_format(self) -> ConversionFormat:
        return ConversionFormat.UC_METRICS

    def validate_input(self, input_data: Any) -> bool:
        """
        Validate YAML input data.

        Args:
            input_data: Either a dict or a file path string

        Returns:
            True if valid, raises ValueError if invalid
        """
        if isinstance(input_data, str):
            # File path - will be validated when parsed
            return True

        if not isinstance(input_data, dict):
            raise ValueError("Input must be a dictionary or file path string")

        # Check required fields
        if 'kbi' not in input_data and 'kbis' not in input_data:
            raise ValueError("Input must contain 'kbi' or 'kbis' field")

        return True

    def convert(self, input_data: Any, **kwargs) -> Dict[str, Any]:
        """
        Convert YAML to Unity Catalog Metrics format.

        Args:
            input_data: Either:
                - Dict: YAML data as dictionary
                - String: Path to YAML file
            **kwargs: Additional options:
                - process_structures: bool (default True)
                - catalog: str - UC catalog name
                - schema: str - UC schema name

        Returns:
            Dictionary with:
                - uc_metrics: List of UC metrics definitions
                - count: Number of metrics generated
        """
        process_structures = kwargs.get('process_structures', True)

        # Parse YAML input
        if isinstance(input_data, str):
            # File path
            definition = self.yaml_parser.parse_file(input_data)
        elif isinstance(input_data, dict):
            # Dictionary data
            definition = self.yaml_parser._parse_yaml_data(input_data)
        else:
            raise ValueError("Input must be a dictionary or file path")

        # Process structures if enabled
        if process_structures and definition.structures:
            definition = self.structure_processor.process_definition(definition)

        # Prepare metadata for UC processor
        yaml_metadata = {
            'description': definition.description,
            'technical_name': definition.technical_name,
            'default_variables': definition.default_variables,
            'filters': definition.filters or {},
        }

        # Generate UC Metrics definitions
        uc_metrics_list = []
        for kbi in definition.kbis:
            uc_metric = self.uc_processor.process_kbi_to_uc_metrics(kbi, yaml_metadata)
            uc_metrics_list.append(uc_metric)

        # Return result
        return {
            "uc_metrics": uc_metrics_list,
            "count": len(uc_metrics_list),
            "definition": definition,
        }
