"""YAML to SQL Converter Tool for CrewAI"""

import logging
from typing import TYPE_CHECKING, Any, Optional, Type
from pathlib import Path
import yaml
import tempfile

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

# Import converters
from converters.common.parsers.yaml import YAMLKPIParser
from converters.outbound.sql.generator import SQLGenerator
from converters.common.processors.structures import StructureExpander
from converters.outbound.sql.models import SQLDialect, SQLTranslationOptions

logger = logging.getLogger(__name__)


class YAMLToSQLToolSchema(BaseModel):
    """Input schema for YAMLToSQLTool."""

    yaml_content: Optional[str] = Field(
        None,
        description="YAML content as a string containing KPI measure definitions"
    )
    file_path: Optional[str] = Field(
        None,
        description="Path to YAML file containing KPI measure definitions"
    )
    dialect: str = Field(
        "databricks",
        description="SQL dialect for output: databricks, postgresql, mysql, sqlserver, snowflake, bigquery, or standard (default: databricks)"
    )
    process_structures: bool = Field(
        True,
        description="Whether to process time intelligence structures (default: True)"
    )
    include_comments: bool = Field(
        True,
        description="Include descriptive comments in SQL output (default: True)"
    )


class YAMLToSQLTool(BaseTool):
    """
    Convert YAML measure definitions to SQL queries.

    This tool parses YAML-based KBI (Key Business Indicator) definitions
    and generates corresponding SQL queries for various SQL dialects.

    Supported SQL Dialects:
    - databricks (default)
    - postgresql
    - mysql
    - sqlserver
    - snowflake
    - bigquery
    - standard (ANSI SQL)

    Features:
    - Parses YAML measure definitions
    - Generates SQL queries with proper aggregations
    - Handles filters and time intelligence
    - Supports multiple SQL dialects
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

    name: str = "YAML to SQL Converter"
    description: str = (
        "Convert YAML measure definitions to SQL queries for various database systems. "
        "Accepts either YAML content as string via 'yaml_content' parameter "
        "or a file path via 'file_path' parameter. "
        "Supports multiple SQL dialects: databricks, postgresql, mysql, sqlserver, snowflake, bigquery. "
        "Returns formatted SQL queries ready for execution."
    )
    args_schema: Type[BaseModel] = YAMLToSQLToolSchema

    # Dialect mapping
    DIALECT_MAP = {
        "databricks": SQLDialect.DATABRICKS,
        "postgresql": SQLDialect.POSTGRESQL,
        "mysql": SQLDialect.MYSQL,
        "sqlserver": SQLDialect.SQLSERVER,
        "snowflake": SQLDialect.SNOWFLAKE,
        "bigquery": SQLDialect.BIGQUERY,
        "standard": SQLDialect.STANDARD,
    }

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the YAML to SQL converter tool."""
        super().__init__(**kwargs)
        self.yaml_parser = YAMLKPIParser()
        self.structure_processor = StructureExpander()

    def _run(self, **kwargs: Any) -> str:
        """
        Execute YAML to SQL conversion.

        Args:
            yaml_content (Optional[str]): YAML content as string
            file_path (Optional[str]): Path to YAML file
            dialect (str): SQL dialect (databricks, postgresql, mysql, etc.)
            process_structures (bool): Process time intelligence structures
            include_comments (bool): Include comments in SQL output

        Returns:
            str: Formatted SQL queries
        """
        try:
            yaml_content = kwargs.get("yaml_content")
            file_path = kwargs.get("file_path")
            dialect_str = kwargs.get("dialect", "databricks").lower()
            process_structures = kwargs.get("process_structures", True)
            include_comments = kwargs.get("include_comments", True)

            # Validate input
            if not yaml_content and not file_path:
                return "Error: Must provide either 'yaml_content' or 'file_path'"

            if yaml_content and file_path:
                return "Error: Provide only one of 'yaml_content' or 'file_path', not both"

            # Validate and get SQL dialect
            if dialect_str not in self.DIALECT_MAP:
                available = ", ".join(self.DIALECT_MAP.keys())
                return f"Error: Unknown SQL dialect '{dialect_str}'. Available: {available}"

            dialect = self.DIALECT_MAP[dialect_str]

            logger.info(f"[yaml_to_sql] Starting conversion (dialect={dialect_str}, process_structures={process_structures})")

            # Parse YAML
            if file_path:
                # File path provided
                logger.info(f"[yaml_to_sql] Parsing YAML file: {file_path}")
                definition = self.yaml_parser.parse_file(file_path)
            else:
                # YAML content provided - need to create temp file
                logger.info(f"[yaml_to_sql] Parsing YAML content ({len(yaml_content)} chars)")

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

            logger.info(f"[yaml_to_sql] Parsed {len(definition.kpis)} KBI(s)")

            # Process structures if enabled
            if process_structures and definition.structures:
                logger.info(f"[yaml_to_sql] Processing {len(definition.structures)} structure(s)")
                definition = self.structure_processor.process_definition(definition)

            # Create translation options
            translation_options = SQLTranslationOptions(
                target_dialect=dialect,
                format_output=True,
                include_comments=include_comments,
            )

            # Generate SQL using SQLGenerator
            sql_generator = SQLGenerator(dialect=dialect)
            sql_result = sql_generator.generate_sql_from_kbi_definition(definition, translation_options)

            logger.info(f"[yaml_to_sql] Generated {len(sql_result.sql_queries)} SQL queries, {len(sql_result.sql_measures)} measures")

            # Format output
            output = self._format_output(sql_result, dialect_str)

            return output

        except FileNotFoundError as e:
            logger.error(f"[yaml_to_sql] File not found: {e}")
            return f"Error: File not found - {str(e)}"
        except ValueError as e:
            logger.error(f"[yaml_to_sql] Validation error: {e}")
            return f"Error: Invalid input - {str(e)}"
        except Exception as e:
            logger.error(f"[yaml_to_sql] Conversion failed: {e}", exc_info=True)
            return f"Error converting YAML to SQL: {str(e)}"

    def _format_output(self, sql_result, dialect: str) -> str:
        """
        Format SQL translation result for output.

        Args:
            sql_result: SQLTranslationResult object
            dialect: SQL dialect name

        Returns:
            Formatted string with SQL queries
        """
        output_lines = []
        output_lines.append(f"✅ Generated SQL for dialect: {dialect.upper()}")
        output_lines.append("=" * 80)
        output_lines.append("")

        # Get formatted SQL output
        formatted_sql = sql_result.get_formatted_sql_output()

        if formatted_sql:
            output_lines.append(formatted_sql)
        else:
            output_lines.append("No SQL generated.")

        output_lines.append("")
        output_lines.append("=" * 80)
        output_lines.append(f"📊 Summary:")
        output_lines.append(f"  - SQL Queries: {len(sql_result.sql_queries)}")
        output_lines.append(f"  - Measures: {len(sql_result.sql_measures)}")
        output_lines.append(f"  - Dialect: {dialect.upper()}")

        return "\n".join(output_lines)
