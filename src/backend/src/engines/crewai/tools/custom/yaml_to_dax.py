"""YAML to DAX Converter Tool for CrewAI"""

import logging
from typing import TYPE_CHECKING, Any, Optional, Type
from pathlib import Path
import yaml
import tempfile

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

# Import converters
from converters.common.parsers.yaml import YAMLKPIParser
from converters.outbound.dax.generator import DAXGenerator
from converters.common.processors.structures import StructureExpander
from converters.base.models import DAXMeasure

logger = logging.getLogger(__name__)


class YAMLToDAXToolSchema(BaseModel):
    """Input schema for YAMLToDAXTool."""

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


class YAMLToDAXTool(BaseTool):
    """
    Convert YAML measure definitions to DAX formulas.

    This tool parses YAML-based KBI (Key Business Indicator) definitions
    and generates corresponding DAX measures suitable for Power BI.

    Features:
    - Parses YAML measure definitions
    - Generates DAX formulas with proper aggregations
    - Handles filters and time intelligence
    - Processes structures for advanced scenarios

    Example YAML input:
    ```yaml
    kbis:
      - name: "Total Sales"
        formula: "SUM(Sales[Amount])"
        source_table: "Sales"
        aggregation_type: "SUM"
    ```
    """

    name: str = "YAML to DAX Converter"
    description: str = (
        "Convert YAML measure definitions to DAX formulas for Power BI. "
        "Accepts either YAML content as string via 'yaml_content' parameter "
        "or a file path via 'file_path' parameter. "
        "Returns formatted DAX measures ready for Power BI."
    )
    args_schema: Type[BaseModel] = YAMLToDAXToolSchema

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the YAML to DAX converter tool."""
        super().__init__(**kwargs)
        self.yaml_parser = YAMLKPIParser()
        self.dax_generator = DAXGenerator()
        self.structure_processor = StructureExpander()

    def _run(self, **kwargs: Any) -> str:
        """
        Execute YAML to DAX conversion.

        Args:
            yaml_content (Optional[str]): YAML content as string
            file_path (Optional[str]): Path to YAML file
            process_structures (bool): Process time intelligence structures

        Returns:
            str: Formatted DAX measures
        """
        try:
            yaml_content = kwargs.get("yaml_content")
            file_path = kwargs.get("file_path")
            process_structures = kwargs.get("process_structures", True)

            # Validate input
            if not yaml_content and not file_path:
                return "Error: Must provide either 'yaml_content' or 'file_path'"

            if yaml_content and file_path:
                return "Error: Provide only one of 'yaml_content' or 'file_path', not both"

            logger.info(f"[yaml_to_dax] Starting conversion (process_structures={process_structures})")

            # Parse YAML
            if file_path:
                # File path provided
                logger.info(f"[yaml_to_dax] Parsing YAML file: {file_path}")
                definition = self.yaml_parser.parse_file(file_path)
            else:
                # YAML content provided - need to create temp file
                logger.info(f"[yaml_to_dax] Parsing YAML content ({len(yaml_content)} chars)")

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

            logger.info(f"[yaml_to_dax] Parsed {len(definition.kpis)} KBI(s)")

            # Process structures if enabled
            if process_structures and definition.structures:
                logger.info(f"[yaml_to_dax] Processing {len(definition.structures)} structure(s)")
                definition = self.structure_processor.process_definition(definition)

            # Generate DAX measures
            dax_measures = []
            for kpi in definition.kpis:
                dax_measure = self.dax_generator.generate_dax_measure(definition, kbi)
                dax_measures.append(dax_measure)

            logger.info(f"[yaml_to_dax] Generated {len(dax_measures)} DAX measure(s)")

            # Format output
            output = self._format_output(dax_measures)

            return output

        except FileNotFoundError as e:
            logger.error(f"[yaml_to_dax] File not found: {e}")
            return f"Error: File not found - {str(e)}"
        except ValueError as e:
            logger.error(f"[yaml_to_dax] Validation error: {e}")
            return f"Error: Invalid input - {str(e)}"
        except Exception as e:
            logger.error(f"[yaml_to_dax] Conversion failed: {e}", exc_info=True)
            return f"Error converting YAML to DAX: {str(e)}"

    def _format_output(self, measures: list[DAXMeasure]) -> str:
        """
        Format DAX measures for output.

        Args:
            measures: List of DAX measures

        Returns:
            Formatted string with DAX measures
        """
        if not measures:
            return "No DAX measures generated."

        output_lines = []
        output_lines.append(f"✅ Generated {len(measures)} DAX Measure(s)")
        output_lines.append("=" * 80)
        output_lines.append("")

        for i, measure in enumerate(measures, 1):
            output_lines.append(f"-- Measure {i}: {measure.name}")
            if measure.description:
                output_lines.append(f"-- {measure.description}")
            output_lines.append(f"{measure.name} = ")
            output_lines.append(f"    {measure.dax_formula}")
            output_lines.append("")  # Blank line between measures

        output_lines.append("=" * 80)
        output_lines.append(f"📋 Total: {len(measures)} measure(s) ready for Power BI")

        return "\n".join(output_lines)
