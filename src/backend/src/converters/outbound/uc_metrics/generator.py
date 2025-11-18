"""
UC Metrics Store Generator
Converts KPI definitions to Unity Catalog metrics store format
"""

import logging
from typing import Dict, List, Any, Optional
from converters.base.models import KPI

logger = logging.getLogger(__name__)

class UCMetricsGenerator:
    """Generator for creating Unity Catalog metrics store definitions"""

    def __init__(self, dialect: str = "spark"):
        self.dialect = dialect

    def kpi: KPI, yaml_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Generate UC metrics definition from a single KBI"""

        # Extract basic information
        measure_name = kpi.technical_name or "unnamed_measure"
        description = kpi.description or f"UC metrics definition for {measure_name}"

        # Build source table reference
        source_table = self._build_source_reference(kpi.source_table, yaml_metadata)

        # Build filter conditions
        filter_conditions = self._build_filter_conditions(kbi, yaml_metadata)

        # Build measure expression
        measure_expr = self._build_measure_expression(kbi)

        # Construct UC metrics format
        uc_metrics = {
            "version": "0.1",
            "description": f"UC metrics store definition for \"{kbi.description}\" KBI",
            "source": source_table,
            "measures": [
                {
                    "name": measure_name,
                    "expr": measure_expr
                }
            ]
        }

        # Add filter if we have conditions
        if filter_conditions:
            uc_metrics["filter"] = filter_conditions

        return uc_metrics

    def _build_source_reference(self, source_table: str, yaml_metadata: Dict[str, Any]) -> str:
        """Build the source table reference in catalog.schema.table format"""

        # For now, use a simple format - this can be enhanced later
        # to extract catalog/schema information from metadata or configuration

        if '.' in source_table:
            # Already has schema/catalog info
            return source_table
        else:
            # Default format - can be made configurabl 
            return f"catalog.schema.{source_table}"

    def kpi: KPI, yaml_metadata: Dict[str, Any]) -> Optional[str]:
        """Build combined filter conditions from KBI filters and variable substitution"""

        if not kpi.filters:
            return None

        # Get variable definitions
        variables = yaml_metadata.get('default_variables', {})
        query_filters = yaml_metadata.get('filters', {}).get('query_filter', {})

        all_conditions = []

        for filter_condition in kpi.filters:
            processed_condition = self._process_filter_condition(
                filter_condition, variables, query_filters
            )
            if processed_condition:
                all_conditions.append(processed_condition)

        if all_conditions:
            return " AND ".join(all_conditions)

        return None

    def _process_filter_condition(self,
                                condition: str,
                                variables: Dict[str, Any],
                                query_filters: Dict[str, str]) -> Optional[str]:
        """Process a single filter condition with variable substitution"""

        if condition == "$query_filter":
            # Expand query filter
            expanded_conditions = []
            for filter_name, filter_expr in query_filters.items():
                expanded = self._substitute_variables(filter_expr, variables)
                if expanded:
                    expanded_conditions.append(expanded)
            return " AND ".join(expanded_conditions) if expanded_conditions else None
        else:
            # Direct condition - substitute variables
            return self._substitute_variables(condition, variables)

    def _substitute_variables(self, expression: str, variables: Dict[str, Any]) -> str:
        """Substitute $var_* variables in expressions"""

        result = expression

        for var_name, var_value in variables.items():
            var_placeholder = f"$var_{var_name}"

            if var_placeholder in result:
                if isinstance(var_value, list):
                    # Convert list to SQL IN format
                    quoted_values = [f"'{str(v)}'" for v in var_value]
                    replacement = f"({', '.join(quoted_values)})"
                else:
                    # Single value
                    replacement = f"'{str(var_value)}'"

                result = result.replace(var_placeholder, replacement)

        return result

    def kpi: KPI) -> str:
        """Build the measure expression based on aggregation type and formula"""

        aggregation_type = kpi.aggregation_type.upper() if kpi.aggregation_type else "SUM"
        formula = kpi.formula or "1"

        # Map aggregation types to UC metrics expressions
        if aggregation_type == "SUM":
            return f"SUM({formula})"
        elif aggregation_type == "COUNT":
            return f"COUNT({formula})"
        elif aggregation_type == "DISTINCTCOUNT":
            return f"COUNT(DISTINCT {formula})"
        elif aggregation_type == "AVERAGE":
            return f"AVG({formula})"
        elif aggregation_type == "MIN":
            return f"MIN({formula})"
        elif aggregation_type == "MAX":
            return f"MAX({formula})"
        else:
            # Default to SUM for unknown types
            logger.warning(f"Unknown aggregation type: {aggregation_type}, defaulting to SUM")
            return f"SUM({formula})"

    def kpi: KPI, specific_filters: Optional[str]) -> str:
        """Build the measure expression with FILTER clause for specific conditions"""

        aggregation_type = kpi.aggregation_type.upper() if kpi.aggregation_type else "SUM"
        formula = kpi.formula or "1"
        display_sign = getattr(kbi, 'display_sign', 1)  # Default to 1 if not specified

        # Note: EXCEPTION_AGGREGATION is handled separately in consolidated processing

        # Handle exceptions by transforming the formula
        exceptions = getattr(kbi, 'exceptions', None)
        if exceptions:
            formula = self._apply_exceptions_to_formula(formula, exceptions)

        # Build base aggregation
        if aggregation_type == "SUM":
            base_expr = f"SUM({formula})"
        elif aggregation_type == "COUNT":
            base_expr = f"COUNT({formula})"
        elif aggregation_type == "DISTINCTCOUNT":
            base_expr = f"COUNT(DISTINCT {formula})"
        elif aggregation_type == "AVERAGE":
            base_expr = f"AVG({formula})"
        elif aggregation_type == "MIN":
            base_expr = f"MIN({formula})"
        elif aggregation_type == "MAX":
            base_expr = f"MAX({formula})"
        else:
            # Default to SUM for unknown types
            logger.warning(f"Unknown aggregation type: {aggregation_type}, defaulting to SUM")
            base_expr = f"SUM({formula})"

        # Add FILTER clause if there are specific filters
        if specific_filters:
            filtered_expr = f"{base_expr} FILTER (WHERE {specific_filters})"
        else:
            filtered_expr = base_expr

        # Apply display_sign if it's -1 (multiply by -1 for negative values)
        if display_sign == -1:
            return f"(-1) * {filtered_expr}"
        else:
            return filtered_expr

    def _apply_exceptions_to_formula(self, formula: str, exceptions: List[Dict[str, Any]]) -> str:
        """Apply exception transformations to the formula"""
        transformed_formula = formula

        for exception in exceptions:
            exception_type = exception.get('type', '').lower()

            if exception_type == 'negative_to_zero':
                # Transform: field -> CASE WHEN field < 0 THEN 0 ELSE field END
                transformed_formula = f"CASE WHEN {transformed_formula} < 0 THEN 0 ELSE {transformed_formula} END"

            elif exception_type == 'null_to_zero':
                # Transform: field -> COALESCE(field, 0)
                transformed_formula = f"COALESCE({transformed_formula}, 0)"

            elif exception_type == 'division_by_zero':
                # For division operations, we need to handle division by zero
                # This assumes the formula contains a division operator
                if '/' in transformed_formula:
                    # Split on division and wrap denominator with NULL check
                    parts = transformed_formula.split('/')
                    if len(parts) == 2:
                        numerator = parts[0].strip()
                        denominator = parts[1].strip()
                        transformed_formula = f"CASE WHEN ({denominator}) = 0 THEN 0 ELSE ({numerator}) / ({denominator}) END"

        return transformed_formula

    def kpi: KPI, specific_filters: Optional[str]) -> tuple[str, dict]:
        """Build exception aggregation with window configuration"""

        formula = kpi.formula or "1"
        display_sign = getattr(kbi, 'display_sign', 1)
        exception_agg_type = getattr(kbi, 'exception_aggregation', 'sum').upper()
        exception_fields = getattr(kbi, 'fields_for_exception_aggregation', [])

        # Build the aggregation function for the main expression
        if exception_agg_type == "SUM":
            agg_func = "SUM"
        elif exception_agg_type == "COUNT":
            agg_func = "COUNT"
        elif exception_agg_type == "AVG":
            agg_func = "AVG"
        elif exception_agg_type == "MIN":
            agg_func = "MIN"
        elif exception_agg_type == "MAX":
            agg_func = "MAX"
        else:
            # Default to SUM
            agg_func = "SUM"

        # Format the formula with proper line breaks and indentation
        main_expr = f"""{agg_func}(
          {formula}
        )"""

        # Apply display_sign if it's -1
        if display_sign == -1:
            main_expr = f"(-1) * {main_expr}"

        # Build window configuration based on exception aggregation fields
        window_config = []
        if exception_fields:
            # Create window entries for all exception aggregation fields
            for field in exception_fields:
                window_entry = {
                    "order": field,
                    "range": "current",
                    "semiadditive": "last"
                }
                window_config.append(window_entry)

        return main_expr, window_config

    def generate_consolidated_uc_metrics(self, kbi_list: List[KPI], yaml_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Generate consolidated UC metrics definition from multiple KBIs"""

        # Separate KBIs by type
        constant_selection_kbis = [kbi for kpi in kbi_list if hasattr(kbi, 'fields_for_constant_selection') and kpi.fields_for_constant_selection]
        regular_kbis = [kbi for kpi in kbi_list if not (hasattr(kbi, 'fields_for_constant_selection') and kpi.fields_for_constant_selection)]

        # If ALL KBIs are constant selection, use constant selection format
        if constant_selection_kbis and len(regular_kbis) == 0:
            if len(constant_selection_kbis) == 1:
                return self._build_constant_selection_uc_metrics(constant_selection_kbis[0], yaml_metadata)
            else:
                return self._build_consolidated_constant_selection_uc_metrics(constant_selection_kbis, yaml_metadata)

        # If we have mixed types or only regular KBIs, use consolidated format
        # This will handle constant selection KBIs within the regular consolidated processing

        # Extract basic information
        description = yaml_metadata.get('description', 'UC metrics store definition')

        # Find common filters across KBIs
        common_filters = self._extract_common_filters(kbi_list, yaml_metadata)

        # Build consolidated measures
        measures = []
        for kpi in kbi_list:
            measure_name = kpi.technical_name or "unnamed_measure"

            # Get KBI-specific filters (beyond common ones)
            specific_filters = self._get_kbi_specific_filters(kbi, common_filters, yaml_metadata)

            # Check if this is an exception aggregation
            aggregation_type = kpi.aggregation_type.upper() if kpi.aggregation_type else "SUM"

            # Check for special KBI types
            has_constant_selection = hasattr(kbi, 'fields_for_constant_selection') and kpi.fields_for_constant_selection

            if aggregation_type == "EXCEPTION_AGGREGATION":
                # Build exception aggregation with window configuration
                measure_expr, window_config = self._build_exception_aggregation_with_window(kbi, specific_filters)
                measure = {
                    "name": measure_name,
                    "expr": measure_expr
                }
                # Add window configuration if it exists
                if window_config:
                    measure["window"] = window_config
            elif has_constant_selection:
                # Build constant selection measure (simplified for mixed mode)
                measure_expr = self._build_measure_expression_with_filter(kbi, specific_filters)

                # Build window configuration for constant selection fields
                window_config = []
                for field in kpi.fields_for_constant_selection:
                    window_entry = {
                        "order": field,
                        "semiadditive": "last",
                        "range": "current"
                    }
                    window_config.append(window_entry)

                measure = {
                    "name": measure_name,
                    "expr": measure_expr
                }
                # Add window configuration for constant selection
                if window_config:
                    measure["window"] = window_config
            else:
                # Build regular measure expression with FILTER clause if there are specific filters
                measure_expr = self._build_measure_expression_with_filter(kbi, specific_filters)
                measure = {
                    "name": measure_name,
                    "expr": measure_expr
                }

            measures.append(measure)

        # Construct consolidated UC metrics format
        uc_metrics = {
            "version": "0.1",
            "description": f"UC metrics store definition for \"{description}\"",
            "measures": measures
        }

        # Add common filter if we have any
        if common_filters:
            uc_metrics["filter"] = common_filters

        return uc_metrics

    def _extract_common_filters(self, kbi_list: List[KPI], yaml_metadata: Dict[str, Any]) -> Optional[str]:
        """Extract filters that are common across all KBIs"""

        # Get variable definitions
        variables = yaml_metadata.get('default_variables', {})
        query_filters = yaml_metadata.get('filters', {}).get('query_filter', {})

        # Always include query filters as common filters if they exist in the YAML
        common_filters = []

        if query_filters:
            for filter_expr in query_filters.values():
                expanded = self._substitute_variables(filter_expr, variables)
                if expanded:
                    common_filters.append(expanded)

        # Find other filters that appear in ALL KBIs (excluding query filters)
        all_filters = []

        for kpi in kbi_list:
            if not kpi.filters:
                continue

            kbi_specific_filters = []
            for filter_condition in kpi.filters:
                # Skip literal $query_filter references
                if filter_condition == "$query_filter":
                    continue

                # Skip filters that match expanded query filters
                is_query_filter = False
                for qf_expr in query_filters.values():
                    expanded_qf = self._substitute_variables(qf_expr, variables)
                    if expanded_qf == filter_condition:
                        is_query_filter = True
                        break

                if not is_query_filter:
                    kbi_specific_filters.append(filter_condition)

            if kbi_specific_filters:
                all_filters.append(set(kbi_specific_filters))

        # Get intersection of all filter sets (common non-query filters)
        if all_filters:
            common_non_query_filters = set.intersection(*all_filters)
            for filter_expr in sorted(common_non_query_filters):
                common_filters.append(filter_expr)

        if common_filters:
            return " AND ".join(common_filters)

        return None

    def kpi: KPI, common_filters: Optional[str], yaml_metadata: Dict[str, Any]) -> Optional[str]:
        """Get filters specific to this KBI (not in common filters)"""

        if not kpi.filters:
            return None

        # Get variable definitions
        variables = yaml_metadata.get('default_variables', {})
        query_filters = yaml_metadata.get('filters', {}).get('query_filter', {})

        # Parse common filters into a set
        common_filter_set = set()
        if common_filters:
            common_filter_set = set(f.strip() for f in common_filters.split(' AND '))

        # Get all KBI filters
        kbi_specific = []
        for filter_condition in kpi.filters:
            if filter_condition == "$query_filter":
                # Skip query filters as they're likely common
                continue
            else:
                # Direct condition
                expanded = self._substitute_variables(filter_condition, variables)
                if expanded and expanded not in common_filter_set:
                    kbi_specific.append(expanded)

        if kbi_specific:
            return " AND ".join(kbi_specific)

        return None

    def format_consolidated_uc_metrics_yaml(self, uc_metrics: Dict[str, Any]) -> str:
        """Format consolidated UC metrics as YAML string with comments for specific filters"""

        lines = []

        # Version and description
        lines.append(f"version: {uc_metrics['version']}")
        lines.append("")
        lines.append(f"# --- {uc_metrics['description']} ---")
        lines.append("")

        # Source (for constant selection format)
        if 'source' in uc_metrics:
            lines.append(f"source: {uc_metrics['source']}")
            lines.append("")

        # Common filter (if present)
        if 'filter' in uc_metrics:
            lines.append(f"filter: {uc_metrics['filter']}")
            lines.append("")

        # Dimensions (for constant selection format)
        if 'dimensions' in uc_metrics:
            lines.append("dimensions:")
            for dimension in uc_metrics['dimensions']:
                lines.append(f"  - name: {dimension['name']}")
                lines.append(f"    expr: {dimension['expr']}")
            lines.append("")

        # Measures
        lines.append("measures:")
        for measure in uc_metrics['measures']:
            lines.append(f"  - name: {measure['name']}")
            lines.append(f"    expr: {measure['expr']}")

            # Add window configuration if present (for exception aggregations)
            if 'window' in measure:
                lines.append(f"    window:")
                for window_entry in measure['window']:
                    lines.append(f"      - order: {window_entry['order']}")
                    lines.append(f"        range: {window_entry['range']}")
                    lines.append(f"        semiadditive: {window_entry['semiadditive']}")

            # Add subquery if present (for exception aggregations)
            if 'subquery' in measure:
                lines.append(f"    subquery: |")
                # Indent each line of the subquery
                subquery_lines = measure['subquery'].split('\n')
                for subquery_line in subquery_lines:
                    lines.append(f"      {subquery_line}")

            lines.append("")  # Empty line between measures

        return "\n".join(lines)

    def format_uc_metrics_yaml(self, uc_metrics: Dict[str, Any]) -> str:
        """Format UC metrics as YAML string (single measure format)"""

        lines = []

        # Version and description
        lines.append(f"version: {uc_metrics['version']}")
        lines.append("")
        lines.append(f"# --- {uc_metrics['description']} ---")
        lines.append("")

        # Source
        if 'source' in uc_metrics:
            lines.append(f"source: {uc_metrics['source']}")
            lines.append("")

        # Filter (if present)
        if 'filter' in uc_metrics:
            lines.append(f"filter: {uc_metrics['filter']}")
            lines.append("")

        # Measures
        lines.append("measures:")
        for measure in uc_metrics['measures']:
            lines.append(f"  - name: {measure['name']}")
            lines.append(f"    expr: {measure['expr']}")

        return "\n".join(lines)

    def kpi: KPI, yaml_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Build UC metrics for constant selection KBIs with dimensions and window configuration"""

        # Extract basic information
        measure_name = kpi.technical_name or "unnamed_measure"
        description = kpi.description or f"UC metrics definition for {measure_name}"

        # Build source table reference
        source_table = self._build_source_reference(kpi.source_table, yaml_metadata)

        # Get variable definitions
        variables = yaml_metadata.get('default_variables', {})
        query_filters = yaml_metadata.get('filters', {}).get('query_filter', {})

        # Build common filter conditions (query filters only for global filter)
        global_filters = []
        if query_filters:
            for filter_expr in query_filters.values():
                expanded = self._substitute_variables(filter_expr, variables)
                if expanded:
                    global_filters.append(expanded)

        # Build KBI-specific filters for FILTER clause
        kbi_specific_filters = []
        for filter_condition in kpi.filters:
            if filter_condition == "$query_filter":
                continue  # Skip query filters as they go in global filter
            else:
                expanded = self._substitute_variables(filter_condition, variables)
                if expanded:
                    kbi_specific_filters.append(expanded)

        # Build dimensions from constant selection fields and filter fields
        dimensions = []

        # Add constant selection fields as dimensions
        for field in kpi.fields_for_constant_selection:
            dimensions.append({
                "name": field,
                "expr": field
            })

        # Extract additional dimension fields from filters (fields that appear in equality conditions)
        dimension_fields = self._extract_dimension_fields_from_filters(kbi_specific_filters)
        for field in dimension_fields:
            if field not in [d["name"] for d in dimensions]:  # Avoid duplicates
                dimensions.append({
                    "name": field,
                    "expr": field
                })

        # Build measure expression with FILTER clause for KBI-specific conditions
        aggregation_type = kpi.aggregation_type.upper() if kpi.aggregation_type else "SUM"
        formula = kpi.formula or "1"
        display_sign = getattr(kbi, 'display_sign', 1)

        # Build base aggregation
        if aggregation_type == "SUM":
            base_expr = f"SUM({formula})"
        elif aggregation_type == "COUNT":
            base_expr = f"COUNT({formula})"
        elif aggregation_type == "AVERAGE":
            base_expr = f"AVG({formula})"
        elif aggregation_type == "MIN":
            base_expr = f"MIN({formula})"
        elif aggregation_type == "MAX":
            base_expr = f"MAX({formula})"
        else:
            base_expr = f"SUM({formula})"

        # Add FILTER clause if there are KBI-specific filters
        if kbi_specific_filters:
            filter_conditions = " AND ".join(kbi_specific_filters)
            measure_expr = f"{base_expr} FILTER (\n            WHERE {filter_conditions}\n          )"
        else:
            measure_expr = base_expr

        # Apply display_sign if it's -1
        if display_sign == -1:
            measure_expr = f"(-1) * {measure_expr}"

        # Build window configuration for constant selection fields
        window_config = []
        for field in kpi.fields_for_constant_selection:
            window_entry = {
                "order": field,
                "semiadditive": "last",
                "range": "current"
            }
            window_config.append(window_entry)

        # Build the measure object
        measure = {
            "name": measure_name,
            "expr": measure_expr
        }

        # Add window configuration if we have constant selection fields
        if window_config:
            measure["window"] = window_config

        # Construct constant selection UC metrics format
        uc_metrics = {
            "version": "1.0",
            "source": source_table,
            "description": f"UC metrics store definition for \"{description}\"",
            "dimensions": dimensions,
            "measures": [measure]
        }

        # Add global filter if we have common filters
        if global_filters:
            uc_metrics["filter"] = " AND ".join(global_filters)

        return uc_metrics

    def _extract_dimension_fields_from_filters(self, filters: List[str]) -> List[str]:
        """Extract field names from filter conditions that can be used as dimensions"""
        import re

        dimension_fields = []

        for filter_condition in filters:
            # Look for patterns like "field = 'value'" or "field IN (...)"
            # Match field names before = or IN operators
            patterns = [
                r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=',  # field = value
                r'([a-zA-Z_][a-zA-Z0-9_]*)\s+IN',  # field IN (...)
            ]

            for pattern in patterns:
                matches = re.findall(pattern, filter_condition, re.IGNORECASE)
                for match in matches:
                    if match not in dimension_fields:
                        dimension_fields.append(match)

        return dimension_fields

    def _build_consolidated_constant_selection_uc_metrics(self, constant_selection_kbis: List[KPI], yaml_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Build consolidated UC metrics for multiple constant selection KBIs"""

        # Extract basic information
        description = yaml_metadata.get('description', 'UC metrics store definition')

        # Get variable definitions
        variables = yaml_metadata.get('default_variables', {})
        query_filters = yaml_metadata.get('filters', {}).get('query_filter', {})

        # Build common filter conditions (query filters only for global filter)
        global_filters = []
        if query_filters:
            for filter_expr in query_filters.values():
                expanded = self._substitute_variables(filter_expr, variables)
                if expanded:
                    global_filters.append(expanded)

        # Collect all dimensions and measures
        all_dimensions = []
        all_measures = []
        dimension_names_seen = set()

        # Use the first KBI's source table (or find most common one)
        source_tables = [kbi.source_table for kpi in constant_selection_kbis if kpi.source_table]
        most_common_source = source_tables[0] if source_tables else "FactTable"
        source_table = self._build_source_reference(most_common_source, yaml_metadata)

        for kpi in constant_selection_kbis:
            # Build KBI-specific filters for FILTER clause
            kbi_specific_filters = []
            for filter_condition in kpi.filters:
                if filter_condition == "$query_filter":
                    continue  # Skip query filters as they go in global filter
                else:
                    expanded = self._substitute_variables(filter_condition, variables)
                    if expanded:
                        kbi_specific_filters.append(expanded)

            # Add constant selection fields as dimensions
            for field in kpi.fields_for_constant_selection:
                if field not in dimension_names_seen:
                    all_dimensions.append({
                        "name": field,
                        "expr": field
                    })
                    dimension_names_seen.add(field)

            # Extract additional dimension fields from filters
            dimension_fields = self._extract_dimension_fields_from_filters(kbi_specific_filters)
            for field in dimension_fields:
                if field not in dimension_names_seen:
                    all_dimensions.append({
                        "name": field,
                        "expr": field
                    })
                    dimension_names_seen.add(field)

            # Build measure expression
            measure_name = kpi.technical_name or "unnamed_measure"
            aggregation_type = kpi.aggregation_type.upper() if kpi.aggregation_type else "SUM"
            formula = kpi.formula or "1"
            display_sign = getattr(kbi, 'display_sign', 1)

            # Build base aggregation
            if aggregation_type == "SUM":
                base_expr = f"SUM({formula})"
            elif aggregation_type == "COUNT":
                base_expr = f"COUNT({formula})"
            elif aggregation_type == "AVERAGE":
                base_expr = f"AVG({formula})"
            elif aggregation_type == "MIN":
                base_expr = f"MIN({formula})"
            elif aggregation_type == "MAX":
                base_expr = f"MAX({formula})"
            else:
                base_expr = f"SUM({formula})"

            # Add FILTER clause if there are KBI-specific filters
            if kbi_specific_filters:
                filter_conditions = " AND ".join(kbi_specific_filters)
                measure_expr = f"{base_expr} FILTER (\n            WHERE {filter_conditions}\n          )"
            else:
                measure_expr = base_expr

            # Apply display_sign if it's -1
            if display_sign == -1:
                measure_expr = f"(-1) * {measure_expr}"

            # Build window configuration for constant selection fields
            window_config = []
            for field in kpi.fields_for_constant_selection:
                window_entry = {
                    "order": field,
                    "semiadditive": "last",
                    "range": "current"
                }
                window_config.append(window_entry)

            # Build the measure object
            measure = {
                "name": measure_name,
                "expr": measure_expr
            }

            # Add window configuration if we have constant selection fields
            if window_config:
                measure["window"] = window_config

            all_measures.append(measure)

        # Construct consolidated constant selection UC metrics format
        uc_metrics = {
            "version": "1.0",
            "source": source_table,
            "description": f"UC metrics store definition for \"{description}\"",
            "dimensions": all_dimensions,
            "measures": all_measures
        }

        # Add global filter if we have common filters
        if global_filters:
            uc_metrics["filter"] = " AND ".join(global_filters)

        return uc_metrics