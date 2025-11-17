"""YAML to SQL Converter Implementation"""

from typing import Any, Dict, List
from converters.base.base_converter import BaseConverter, ConversionFormat
from converters.formats.parsers.yaml_parser import YAMLKBIParser
from converters.formats.generators.sql_generator import SQLGenerator
from converters.processors.structure_processor import StructureProcessor
from converters.processors.sql_structure_processor import SQLStructureProcessor
from converters.models.kbi import KBIDefinition
from converters.models.sql_models import SQLDialect, SQLTranslationOptions, SQLTranslationResult


class YAMLToSQLConverter(BaseConverter):
    """
    Converts YAML measure definitions to SQL queries.

    This converter:
    1. Parses YAML input into KBI definitions
    2. Processes structures for time intelligence
    3. Generates SQL queries with proper aggregations and filters
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.yaml_parser = YAMLKBIParser()
        self.structure_processor = StructureProcessor()
        self.sql_structure_processor = SQLStructureProcessor()

        # Default SQL dialect
        self.dialect = SQLDialect(config.get('dialect', 'ANSI_SQL')) if config else SQLDialect.STANDARD

    @property
    def source_format(self) -> ConversionFormat:
        return ConversionFormat.YAML

    @property
    def target_format(self) -> ConversionFormat:
        return ConversionFormat.SQL

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
        Convert YAML to SQL queries.

        Args:
            input_data: Either:
                - Dict: YAML data as dictionary
                - String: Path to YAML file
            **kwargs: Additional options:
                - dialect: SQLDialect (default: STANDARD)
                - process_structures: bool (default True)
                - format_output: bool (default True)

        Returns:
            Dictionary with:
                - sql_result: SQLTranslationResult object
                - formatted_output: Formatted SQL string
        """
        dialect = SQLDialect(kwargs.get('dialect', self.dialect.value))
        process_structures = kwargs.get('process_structures', True)
        format_output = kwargs.get('format_output', True)

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

        # Create translation options
        translation_options = SQLTranslationOptions(
            target_dialect=dialect,
            format_output=format_output,
            include_comments=True,
        )

        # Generate SQL using SQLGenerator
        sql_generator = SQLGenerator(dialect=dialect.value)
        sql_result = sql_generator.generate_sql(definition, translation_options)

        # Return result
        return {
            "sql_result": sql_result,
            "formatted_output": sql_result.get_formatted_sql_output(),
            "query_count": len(sql_result.sql_queries),
            "measure_count": len(sql_result.sql_measures),
        }
