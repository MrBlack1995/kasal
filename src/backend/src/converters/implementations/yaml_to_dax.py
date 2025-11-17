"""YAML to DAX Converter Implementation"""

from typing import Any, Dict, List
from converters.base.base_converter import BaseConverter, ConversionFormat
from converters.formats.parsers.yaml_parser import YAMLKBIParser
from converters.formats.generators.dax_generator import DAXGenerator
from converters.processors.structure_processor import StructureProcessor
from converters.models.kbi import KBIDefinition, DAXMeasure


class YAMLToDAXConverter(BaseConverter):
    """
    Converts YAML measure definitions to DAX formulas.

    This converter:
    1. Parses YAML input into KBI definitions
    2. Processes structures for time intelligence
    3. Generates DAX measures with proper filters and aggregations
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.yaml_parser = YAMLKBIParser()
        self.dax_generator = DAXGenerator()
        self.structure_processor = StructureProcessor()

    @property
    def source_format(self) -> ConversionFormat:
        return ConversionFormat.YAML

    @property
    def target_format(self) -> ConversionFormat:
        return ConversionFormat.DAX

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
        Convert YAML to DAX measures.

        Args:
            input_data: Either:
                - Dict: YAML data as dictionary
                - String: Path to YAML file
            **kwargs: Additional options:
                - process_structures: bool (default True) - Process time intelligence structures

        Returns:
            Dictionary with:
                - measures: List of DAXMeasure objects
                - definition: Original KBIDefinition
                - count: Number of measures generated
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

        # Generate DAX measures
        dax_measures: List[DAXMeasure] = []
        for kbi in definition.kbis:
            dax_measure = self.dax_generator.generate_dax_measure(definition, kbi)
            dax_measures.append(dax_measure)

        # Return result
        return {
            "measures": dax_measures,
            "definition": definition,
            "count": len(dax_measures),
            "formatted_output": self._format_dax_output(dax_measures)
        }

    def _format_dax_output(self, measures: List[DAXMeasure]) -> str:
        """
        Format DAX measures for copy-paste into Power BI.

        Args:
            measures: List of DAX measures

        Returns:
            Formatted DAX measures as string
        """
        output_lines = []

        for measure in measures:
            output_lines.append(f"-- {measure.description}")
            output_lines.append(f"{measure.name} = {measure.dax_formula}")
            output_lines.append("")  # Blank line between measures

        return "\n".join(output_lines)
