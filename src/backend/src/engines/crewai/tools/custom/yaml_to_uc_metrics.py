"""YAML to Unity Catalog Metrics Converter Tool for CrewAI"""

import logging
import json
from typing import TYPE_CHECKING, Any, Optional, Type
from pathlib import Path
import yaml
import tempfile

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

# Import converters
from converters.common.parsers.yaml import YAMLKPIParser
from converters.outbound.uc_metrics.generator import UCMetricsGenerator
from converters.common.processors.structures import StructureExpander

logger = logging.getLogger(__name__)


class YAMLToUCMetricsToolSchema(BaseModel):
    """Input schema for YAMLToUCMetricsTool."""

    yaml_content: Optional[str] = Field(
        None,
        description="YAML content as a string containing KPI measure definitions"
    )
    file_path: Optional[str] = Field(
        None,
        description="Path to YAML file containing KPI measure definitions"
    )
    process_structures: bool = Field(
        True,
        description="Whether to process time intelligence structures (default: True)"
    )
    catalog: Optional[str] = Field(
        None,
        description="Unity Catalog catalog name (optional)"
    )
    schema_name: Optional[str] = Field(
        None,
        description="Unity Catalog schema name (optional)"
    )


class YAMLToUCMetricsTool(BaseTool):
    """
    Convert YAML measure definitions to Unity Catalog Metrics Store format.

    This tool parses YAML-based KBI (Key Business Indicator) definitions
    and generates corresponding Unity Catalog metrics store definitions for Databricks.

    Features:
    - Parses YAML measure definitions
    - Generates UC metrics store JSON format
    - Handles filters and variable substitution
    - Processes structures for advanced scenarios
    - Supports Unity Catalog three-level namespace (catalog.schema.table)

    Unity Catalog Metrics Store Format:
    The tool generates JSON definitions that can be used with Databricks Unity Catalog
    Metrics Store API to create managed metrics.

    Example YAML input:
    ```yaml
    kbis:
      - name: "Total Sales"
        formula: "SUM(Sales[Amount])"
        source_table: "sales_table"
        aggregation_type: "SUM"
    ```

    Example UC Metrics output:
    ```json
    {
      "version": "0.1",
      "description": "UC metrics store definition",
      "source": "catalog.schema.sales_table",
      "measures": [
        {
          "name": "total_sales",
          "expr": "SUM(amount)"
        }
      ]
    }
    ```
    """

    name: str = "YAML to Unity Catalog Metrics Converter"
    description: str = (
        "Convert YAML measure definitions to Unity Catalog Metrics Store format. "
        "Accepts either YAML content as string via 'yaml_content' parameter "
        "or a file path via 'file_path' parameter. "
        "Optionally specify 'catalog' and 'schema_name' for Unity Catalog namespace. "
        "Returns JSON metrics store definitions ready for Databricks UC."
    )
    args_schema: Type[BaseModel] = YAMLToUCMetricsToolSchema

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the YAML to UC Metrics converter tool."""
        super().__init__(**kwargs)
        self.yaml_parser = YAMLKPIParser()
        self.structure_processor = StructureExpander()
        self.uc_processor = UCMetricsGenerator()

    def _run(self, **kwargs: Any) -> str:
        """
        Execute YAML to UC Metrics conversion.

        Args:
            yaml_content (Optional[str]): YAML content as string
            file_path (Optional[str]): Path to YAML file
            process_structures (bool): Process time intelligence structures
            catalog (Optional[str]): UC catalog name
            schema_name (Optional[str]): UC schema name

        Returns:
            str: Formatted UC Metrics JSON definitions
        """
        try:
            yaml_content = kwargs.get("yaml_content")
            file_path = kwargs.get("file_path")
            process_structures = kwargs.get("process_structures", True)
            catalog = kwargs.get("catalog")
            schema_name = kwargs.get("schema_name")

            # Validate input
            if not yaml_content and not file_path:
                return "Error: Must provide either 'yaml_content' or 'file_path'"

            if yaml_content and file_path:
                return "Error: Provide only one of 'yaml_content' or 'file_path', not both"

            logger.info(f"[yaml_to_uc_metrics] Starting conversion (process_structures={process_structures})")

            # Parse YAML
            if file_path:
                # File path provided
                logger.info(f"[yaml_to_uc_metrics] Parsing YAML file: {file_path}")
                definition = self.yaml_parser.parse_file(file_path)
            else:
                # YAML content provided - need to create temp file
                logger.info(f"[yaml_to_uc_metrics] Parsing YAML content ({len(yaml_content)} chars)")

                # Validate YAML syntax first
                try:
                    yaml_data = yaml.safe_load(yaml_content)
                except yaml.YAMLError as e:
                    return f"Error: Invalid YAML syntax - {str(e)}"

                # Create temp file for parsing
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
                    tmp.write(yaml_content)
                    tmp_path = tmp.name

                try:
                    definition = self.yaml_parser.parse_file(tmp_path)
                finally:
                    # Clean up temp file
                    Path(tmp_path).unlink(missing_ok=True)

            logger.info(f"[yaml_to_uc_metrics] Parsed {len(definition.kpis)} KBI(s)")

            # Process structures if enabled
            if process_structures and definition.structures:
                logger.info(f"[yaml_to_uc_metrics] Processing {len(definition.structures)} structure(s)")
                definition = self.structure_processor.process_definition(definition)

            # Prepare metadata for UC processor
            yaml_metadata = {
                'description': definition.description,
                'technical_name': definition.technical_name,
                'default_variables': definition.default_variables or {},
                'filters': definition.filters or {},
            }

            # Add catalog/schema if provided
            if catalog:
                yaml_metadata['catalog'] = catalog
            if schema_name:
                yaml_metadata['schema'] = schema_name

            # Generate UC Metrics definitions
            uc_metrics_list = []
            for kpi in definition.kpis:
                uc_metric = self.uc_processor.generate_uc_metrics(kbi, yaml_metadata)
                uc_metrics_list.append(uc_metric)

            logger.info(f"[yaml_to_uc_metrics] Generated {len(uc_metrics_list)} UC metrics definition(s)")

            # Format output
            output = self._format_output(uc_metrics_list, catalog, schema_name)

            return output

        except FileNotFoundError as e:
            logger.error(f"[yaml_to_uc_metrics] File not found: {e}")
            return f"Error: File not found - {str(e)}"
        except ValueError as e:
            logger.error(f"[yaml_to_uc_metrics] Validation error: {e}")
            return f"Error: Invalid input - {str(e)}"
        except Exception as e:
            logger.error(f"[yaml_to_uc_metrics] Conversion failed: {e}", exc_info=True)
            return f"Error converting YAML to UC Metrics: {str(e)}"

    def _format_output(self, uc_metrics_list: list, catalog: Optional[str], schema_name: Optional[str]) -> str:
        """
        Format UC Metrics definitions for output.

        Args:
            uc_metrics_list: List of UC metrics dictionaries
            catalog: UC catalog name (if provided)
            schema_name: UC schema name (if provided)

        Returns:
            Formatted string with UC Metrics JSON
        """
        if not uc_metrics_list:
            return "No UC Metrics generated."

        output_lines = []
        output_lines.append(f"✅ Generated {len(uc_metrics_list)} Unity Catalog Metrics Definition(s)")
        output_lines.append("=" * 80)
        output_lines.append("")

        if catalog or schema_name:
            output_lines.append("Unity Catalog Namespace:")
            if catalog:
                output_lines.append(f"  Catalog: {catalog}")
            if schema_name:
                output_lines.append(f"  Schema: {schema_name}")
            output_lines.append("")

        # Output each UC metrics definition as JSON
        for i, uc_metric in enumerate(uc_metrics_list, 1):
            output_lines.append(f"-- UC Metrics Definition {i}")
            output_lines.append(f"-- Description: {uc_metric.get('description', 'N/A')}")
            output_lines.append("")

            # Pretty-print JSON
            json_output = json.dumps(uc_metric, indent=2)
            output_lines.append(json_output)
            output_lines.append("")

        output_lines.append("=" * 80)
        output_lines.append(f"📊 Summary:")
        output_lines.append(f"  - UC Metrics Definitions: {len(uc_metrics_list)}")
        output_lines.append(f"  - Format: Unity Catalog Metrics Store JSON")
        output_lines.append(f"  - Ready for: Databricks UC Metrics Store API")

        return "\n".join(output_lines)
