"""
SQL Structure Processor for YAML2DAX SQL Translation
Handles SQL equivalent of SAP BW structures and time intelligence in SQL
"""

from typing import List, Dict, Any, Optional, Tuple
import re
import logging
from converters.models.kbi import KBI, KBIDefinition, Structure
from converters.models.sql_models import (
    SQLDialect, SQLQuery, SQLMeasure, SQLDefinition, SQLStructure,
    SQLAggregationType, SQLTranslationOptions
)


class SQLStructureProcessor:
    """Processes SQL structures (equivalent to SAP BW structures) for time intelligence and reusable SQL logic"""
    
    def __init__(self, dialect: SQLDialect = SQLDialect.STANDARD):
        self.dialect = dialect
        self.logger = logging.getLogger(__name__)
        self.processed_definitions: List[SQLDefinition] = []
    
    def process_definition(self, definition: KBIDefinition, options: SQLTranslationOptions = None) -> SQLDefinition:
        with open('/tmp/sql_debug.log', 'a') as f:
            f.write("=== SQL STRUCTURE PROCESSOR CALLED ===\n")
            if definition.structures:
                f.write(f"Found {len(definition.structures)} structures\n")
                for name, struct in definition.structures.items():
                    f.write(f"Structure {name}: {len(struct.filters)} filters\n")
            if definition.kbis:
                f.write(f"Found {len(definition.kbis)} KBIs\n")
                for kbi in definition.kbis:
                    f.write(f"KBI {kbi.technical_name}: apply_structures={kbi.apply_structures}\n")
        """
        Process a KBI definition and expand KBIs with applied structures for SQL
        
        Args:
            definition: Original KBI definition with structures
            options: SQL translation options
            
        Returns:
            Expanded SQL definition with combined KBI+structure measures
        """
        if options is None:
            options = SQLTranslationOptions(target_dialect=self.dialect)
        
        # Create base SQL definition
        sql_definition = SQLDefinition(
            description=definition.description,
            technical_name=definition.technical_name,
            dialect=self.dialect,
            default_variables=definition.default_variables,
            original_kbis=definition.kbis,
        )
        
        # Add filters from definition for variable substitution
        if definition.filters:
            sql_definition.filters = definition.filters
        
        if not definition.structures:
            # No structures defined, process KBIs directly
            sql_definition.sql_measures = self._convert_kbis_to_sql_measures(definition.kbis, definition, options)
            return sql_definition
        
        # Convert SAP BW structures to SQL structures
        sql_structures = self._convert_structures_to_sql(definition.structures, definition)
        sql_definition.sql_structures = sql_structures
        
        # Process KBIs with structure expansion
        expanded_sql_measures = []
        
        for kbi in definition.kbis:
            if kbi.apply_structures:
                # Create combined SQL measures for each applied structure
                combined_measures = self._create_combined_sql_measures(
                    kbi, sql_structures, kbi.apply_structures, definition, options
                )
                expanded_sql_measures.extend(combined_measures)
            else:
                # No structures applied, convert KBI directly
                sql_measure = self._convert_kbi_to_sql_measure(kbi, definition, options)
                expanded_sql_measures.append(sql_measure)
        
        sql_definition.sql_measures = expanded_sql_measures
        return sql_definition
    
    def _convert_structures_to_sql(self, structures: Dict[str, Structure], definition: KBIDefinition) -> Dict[str, SQLStructure]:
        """Convert SAP BW structures to SQL structures"""
        sql_structures = {}
        
        for struct_name, structure in structures.items():
            # Add logging to a file to debug what's happening
            with open('/tmp/sql_debug.log', 'a') as f:
                f.write(f"Processing structure: {struct_name}\n")
                f.write(f"Structure filters: {structure.filters}\n")

            converted_filters = self._convert_filters_to_sql(structure.filters, definition)

            with open('/tmp/sql_debug.log', 'a') as f:
                f.write(f"Converted structure filters: {converted_filters}\n")

            sql_structure = SQLStructure(
                description=structure.description,
                filters=converted_filters,
                formula=structure.formula,
                display_sign=structure.display_sign
            )

            # Handle time intelligence specific logic
            if self._is_time_intelligence_structure(struct_name, structure):
                sql_structure = self._enhance_time_intelligence_sql_structure(sql_structure, struct_name, structure)

            sql_structures[struct_name] = sql_structure

            with open('/tmp/sql_debug.log', 'a') as f:
                f.write(f"Final SQL structure filters: {sql_structure.filters}\n")
        
        return sql_structures
    
    def _is_time_intelligence_structure(self, struct_name: str, structure: Structure) -> bool:
        """Check if structure is time intelligence related"""
        time_patterns = ['ytd', 'ytg', 'prior', 'year', 'period', 'quarter', 'month']
        struct_name_lower = struct_name.lower()
        
        return any(pattern in struct_name_lower for pattern in time_patterns)
    
    def _enhance_time_intelligence_sql_structure(self, sql_structure: SQLStructure, struct_name: str, structure: Structure) -> SQLStructure:
        """Enhance SQL structure with time intelligence specific SQL logic"""
        struct_name_lower = struct_name.lower()
        
        # Detect common date column patterns
        potential_date_columns = ['date', 'fiscal_date', 'period_date', 'transaction_date', 'created_date']
        
        # Try to find date column from filters
        date_column = None
        for filter_condition in structure.filters:
            for date_col in potential_date_columns:
                if date_col in filter_condition.lower():
                    date_column = date_col
                    break
            if date_column:
                break
        
        sql_structure.date_column = date_column
        
        # Add SQL-specific time intelligence logic
        if 'ytd' in struct_name_lower:
            sql_structure.sql_template = self._create_ytd_sql_template(date_column)
        elif 'ytg' in struct_name_lower:
            sql_structure.sql_template = self._create_ytg_sql_template(date_column)
        elif 'prior' in struct_name_lower:
            sql_structure.sql_template = self._create_prior_period_sql_template(date_column)
        
        return sql_structure
    
    def _create_ytd_sql_template(self, date_column: str = None) -> str:
        """Create SQL template for Year-to-Date calculations"""
        date_col = date_column or 'fiscal_date'
        
        if self.dialect == SQLDialect.DATABRICKS:
            return f"""
            {date_col} >= DATE_TRUNC('year', CURRENT_DATE())
            AND {date_col} <= CURRENT_DATE()
            """
        elif self.dialect == SQLDialect.POSTGRESQL:
            return f"""
            {date_col} >= DATE_TRUNC('year', CURRENT_DATE)
            AND {date_col} <= CURRENT_DATE
            """
        elif self.dialect == SQLDialect.SQLSERVER:
            return f"""
            {date_col} >= DATEFROMPARTS(YEAR(GETDATE()), 1, 1)
            AND {date_col} <= GETDATE()
            """
        else:
            return f"""
            {date_col} >= DATE(YEAR(CURRENT_DATE) || '-01-01')
            AND {date_col} <= CURRENT_DATE
            """
    
    def _create_ytg_sql_template(self, date_column: str = None) -> str:
        """Create SQL template for Year-to-Go calculations"""
        date_col = date_column or 'fiscal_date'
        
        if self.dialect == SQLDialect.DATABRICKS:
            return f"""
            {date_col} > CURRENT_DATE()
            AND {date_col} <= DATE_TRUNC('year', CURRENT_DATE()) + INTERVAL 1 YEAR - INTERVAL 1 DAY
            """
        elif self.dialect == SQLDialect.POSTGRESQL:
            return f"""
            {date_col} > CURRENT_DATE
            AND {date_col} <= DATE_TRUNC('year', CURRENT_DATE) + INTERVAL '1 year' - INTERVAL '1 day'
            """
        elif self.dialect == SQLDialect.SQLSERVER:
            return f"""
            {date_col} > GETDATE()
            AND {date_col} <= DATEFROMPARTS(YEAR(GETDATE()), 12, 31)
            """
        else:
            return f"""
            {date_col} > CURRENT_DATE
            AND {date_col} <= DATE(YEAR(CURRENT_DATE) || '-12-31')
            """
    
    def _create_prior_period_sql_template(self, date_column: str = None) -> str:
        """Create SQL template for Prior Period calculations"""
        date_col = date_column or 'fiscal_date'
        
        if self.dialect == SQLDialect.DATABRICKS:
            return f"""
            {date_col} >= DATE_TRUNC('year', CURRENT_DATE()) - INTERVAL 1 YEAR
            AND {date_col} <= DATE_TRUNC('year', CURRENT_DATE()) - INTERVAL 1 DAY
            """
        elif self.dialect == SQLDialect.POSTGRESQL:
            return f"""
            {date_col} >= DATE_TRUNC('year', CURRENT_DATE) - INTERVAL '1 year'
            AND {date_col} <= DATE_TRUNC('year', CURRENT_DATE) - INTERVAL '1 day'
            """
        elif self.dialect == SQLDialect.SQLSERVER:
            return f"""
            {date_col} >= DATEFROMPARTS(YEAR(GETDATE()) - 1, 1, 1)
            AND {date_col} <= DATEFROMPARTS(YEAR(GETDATE()) - 1, 12, 31)
            """
        else:
            return f"""
            {date_col} >= DATE((YEAR(CURRENT_DATE) - 1) || '-01-01')
            AND {date_col} <= DATE((YEAR(CURRENT_DATE) - 1) || '-12-31')
            """
    
    def _convert_filters_to_sql(self, filters: List[str], definition: KBIDefinition) -> List[str]:
        """Convert SAP BW style filters to SQL WHERE conditions"""
        from converters.rules.aggregations.sql_aggregations import SQLFilterProcessor

        with open('/tmp/sql_debug.log', 'a') as f:
            f.write(f"_convert_filters_to_sql: definition.filters = {definition.filters}\n")

        processor = SQLFilterProcessor(self.dialect)
        return processor.process_filters(filters, definition.default_variables, definition.filters)
    
    def _convert_kbis_to_sql_measures(self, kbis: List[KBI], definition: KBIDefinition, options: SQLTranslationOptions) -> List[SQLMeasure]:
        """Convert list of KBIs to SQL measures"""
        sql_measures = []
        
        for kbi in kbis:
            sql_measure = self._convert_kbi_to_sql_measure(kbi, definition, options)
            sql_measures.append(sql_measure)
        
        return sql_measures
    
    def _convert_kbi_to_sql_measure(self, kbi: KBI, definition: KBIDefinition, options: SQLTranslationOptions) -> SQLMeasure:
        """Convert a single KBI to SQL measure"""
        from converters.rules.aggregations.sql_aggregations import detect_and_build_sql_aggregation
        
        # Build KBI definition dict for aggregation system
        kbi_dict = {
            'formula': kbi.formula,
            'source_table': kbi.source_table,
            'aggregation_type': kbi.aggregation_type,
            'display_sign': kbi.display_sign,
            'exceptions': kbi.exceptions or [],
            'weight_column': kbi.weight_column,
            'percentile': kbi.percentile,
            'target_column': kbi.target_column,
            'exception_aggregation': kbi.exception_aggregation,
            'fields_for_exception_aggregation': kbi.fields_for_exception_aggregation,
        }
        
        # Generate SQL expression
        sql_expression = detect_and_build_sql_aggregation(kbi_dict, self.dialect)
        
        # Determine aggregation type
        agg_type = self._map_to_sql_aggregation_type(kbi.aggregation_type)
        
        # Process filters
        sql_filters = self._convert_filters_to_sql(kbi.filters, definition)

        # Handle constant selection - get group by columns
        group_by_columns = []
        if kbi.fields_for_constant_selection:
            group_by_columns = list(kbi.fields_for_constant_selection)

        # Create SQL measure
        sql_measure = SQLMeasure(
            name=kbi.description or kbi.technical_name or "Unnamed Measure",
            description=kbi.description or "",
            sql_expression=sql_expression,
            aggregation_type=agg_type,
            source_table=kbi.source_table or "fact_table",
            source_column=kbi.formula if self._is_simple_column_reference(kbi.formula) else None,
            filters=sql_filters,
            group_by_columns=group_by_columns,  # Add constant selection fields
            display_sign=kbi.display_sign,
            technical_name=kbi.technical_name or "",
            original_kbi=kbi,
            dialect=self.dialect
        )
        
        return sql_measure
    
    def _create_combined_sql_measures(self,
                                    base_kbi: KBI,
                                    sql_structures: Dict[str, SQLStructure],
                                    structure_names: List[str],
                                    definition: KBIDefinition,
                                    options: SQLTranslationOptions) -> List[SQLMeasure]:
        """Create combined KBI+structure SQL measures"""
        combined_measures = []
        
        for struct_name in structure_names:
            if struct_name not in sql_structures:
                self.logger.warning(f"SQL structure '{struct_name}' not found, skipping")
                continue
            
            sql_structure = sql_structures[struct_name]
            
            # Create combined measure name
            base_name = base_kbi.technical_name or self._generate_technical_name(base_kbi.description)
            combined_name = f"{base_name}_{struct_name}"
            
            # Create combined KBI for processing
            combined_kbi = self._create_combined_kbi(base_kbi, sql_structure, combined_name, definition)
            
            # Convert to SQL measure
            combined_sql_measure = self._convert_kbi_to_sql_measure(combined_kbi, definition, options)
            
            # Update description to reflect combination
            combined_sql_measure.name = f"{base_kbi.description} - {sql_structure.description}"
            combined_sql_measure.description = f"{base_kbi.description} - {sql_structure.description}"
            combined_sql_measure.technical_name = combined_name
            
            # Handle structure formulas that reference other structures
            if sql_structure.formula:
                combined_sql_measure = self._resolve_structure_formula_in_sql(
                    combined_sql_measure, sql_structure, sql_structures, base_kbi, definition
                )
            
            combined_measures.append(combined_sql_measure)
        
        return combined_measures
    
    def _create_combined_kbi(self, base_kbi: KBI, sql_structure: SQLStructure, combined_name: str, definition: KBIDefinition) -> KBI:
        """Create a combined KBI that incorporates the SQL structure"""

        # Debug logging
        with open('/tmp/sql_debug.log', 'a') as f:
            f.write(f"Creating combined KBI: {combined_name}\n")
            f.write(f"Base KBI filters: {base_kbi.filters}\n")
            f.write(f"SQL structure filters: {sql_structure.filters}\n")

        # Combine filters from base KBI and SQL structure
        combined_filters = list(base_kbi.filters) + list(sql_structure.filters)

        with open('/tmp/sql_debug.log', 'a') as f:
            f.write(f"Combined filters: {combined_filters}\n")
        
        # Determine aggregation type and formula
        if sql_structure.formula:
            # Structure has its own formula - this should be CALCULATED
            aggregation_type = "CALCULATED"
            formula = sql_structure.formula
            source_table = None
        else:
            # Structure without formula - use base KBI with combined filters
            aggregation_type = base_kbi.aggregation_type
            formula = base_kbi.formula
            source_table = base_kbi.source_table
        
        # Apply structure's display sign if specified
        display_sign = sql_structure.display_sign if sql_structure.display_sign != 1 else base_kbi.display_sign
        
        # Create combined KBI
        combined_kbi = KBI(
            description=f"{base_kbi.description} - {sql_structure.description}",
            formula=formula,
            filters=combined_filters,
            display_sign=display_sign,
            technical_name=combined_name,
            source_table=source_table,
            aggregation_type=aggregation_type,
            weight_column=base_kbi.weight_column,
            target_column=base_kbi.target_column,
            percentile=base_kbi.percentile,
            exceptions=base_kbi.exceptions,
            exception_aggregation=base_kbi.exception_aggregation,
            fields_for_exception_aggregation=base_kbi.fields_for_exception_aggregation,
            fields_for_constant_selection=base_kbi.fields_for_constant_selection
        )
        
        return combined_kbi
    
    def _resolve_structure_formula_in_sql(self,
                                        sql_measure: SQLMeasure,
                                        sql_structure: SQLStructure,
                                        all_sql_structures: Dict[str, SQLStructure],
                                        base_kbi: KBI,
                                        definition: KBIDefinition) -> SQLMeasure:
        """Resolve structure formula references in SQL context"""
        if not sql_structure.formula:
            return sql_measure
        
        base_name = base_kbi.technical_name or self._generate_technical_name(base_kbi.description)
        formula = sql_structure.formula
        
        # Find structure references in parentheses (same as DAX processor)
        pattern = r'\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)'
        
        def replace_reference(match):
            struct_ref = match.group(1).strip()
            if struct_ref in all_sql_structures:
                # In SQL context, we'll create subquery references or CTEs
                return f"({base_name}_{struct_ref})"
            else:
                return match.group(0)
        
        resolved_formula = re.sub(pattern, replace_reference, formula)
        
        # Update SQL expression to use resolved formula
        # This is a simplified approach - in practice, you'd want to build proper subqueries or CTEs
        sql_measure.sql_expression = resolved_formula
        
        # Mark as calculated expression
        sql_measure.aggregation_type = SQLAggregationType.SUM  # Will be wrapped in calculation logic
        
        return sql_measure
    
    def _map_to_sql_aggregation_type(self, dax_agg_type: str) -> SQLAggregationType:
        """Map DAX aggregation type to SQL aggregation type"""
        if not dax_agg_type:
            return SQLAggregationType.SUM
        
        mapping = {
            'SUM': SQLAggregationType.SUM,
            'COUNT': SQLAggregationType.COUNT,
            'COUNTROWS': SQLAggregationType.COUNT,
            'AVERAGE': SQLAggregationType.AVG,
            'MIN': SQLAggregationType.MIN,
            'MAX': SQLAggregationType.MAX,
            'DISTINCTCOUNT': SQLAggregationType.COUNT_DISTINCT,
            'CALCULATED': SQLAggregationType.SUM,  # Will be handled specially
        }
        
        return mapping.get(dax_agg_type.upper(), SQLAggregationType.SUM)
    
    def _is_simple_column_reference(self, formula: str) -> bool:
        """Check if formula is a simple column reference"""
        if not formula:
            return False
        
        pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*$'
        return bool(re.match(pattern, formula.strip()))
    
    def _generate_technical_name(self, description: str) -> str:
        """Generate technical name from description"""
        if not description:
            return "unnamed_measure"
        
        # Convert to lowercase, replace spaces with underscores, remove special chars
        name = re.sub(r'[^a-zA-Z0-9\s]', '', description.lower())
        name = re.sub(r'\s+', '_', name.strip())
        return name or "unnamed_measure"
    
    def generate_sql_queries_from_definition(self, sql_definition: SQLDefinition, options: SQLTranslationOptions = None) -> List[SQLQuery]:
        """Generate SQL queries from processed SQL definition"""
        if options is None:
            options = SQLTranslationOptions(target_dialect=self.dialect)
        
        queries = []
        
        if options.separate_measures:
            # Generate separate query for each measure
            for sql_measure in sql_definition.sql_measures:
                query = self._create_query_for_sql_measure(sql_measure, sql_definition, options)
                queries.append(query)
        else:
            # Generate combined query for all measures
            if sql_definition.sql_measures:
                combined_query = self._create_combined_sql_query(sql_definition.sql_measures, sql_definition, options)
                queries.append(combined_query)
        
        return queries
    
    def _create_query_for_sql_measure(self, sql_measure: SQLMeasure, sql_definition: SQLDefinition, options: SQLTranslationOptions) -> SQLQuery:
        """Create SQL query for a single measure"""

        # Check if this is an exception aggregation by looking at the original KBI
        if (hasattr(sql_measure, 'original_kbi') and
            sql_measure.original_kbi and
            sql_measure.original_kbi.aggregation_type == 'EXCEPTION_AGGREGATION'):
            # This is an exception aggregation - handle it specially
            return self._create_exception_aggregation_query(sql_measure, sql_definition, options)

        # Build SELECT clause
        select_clause = []

        # Add constant selection (grouping) columns FIRST for SAP BW constant selection behavior
        if sql_measure.group_by_columns:
            select_clause.extend([self._quote_identifier(col) for col in sql_measure.group_by_columns])

        # Add the measure expression
        measure_alias = sql_measure.technical_name or "measure_value"
        select_clause.append(f"{sql_measure.to_sql_expression()} AS {self._quote_identifier(measure_alias)}")

        # Build FROM clause
        from_clause = self._quote_identifier(sql_measure.source_table)
        if sql_definition.schema:
            from_clause = f"{self._quote_identifier(sql_definition.schema)}.{from_clause}"

        # Create query
        query = SQLQuery(
            dialect=self.dialect,
            select_clause=select_clause,
            from_clause=from_clause,
            where_clause=sql_measure.filters,
            group_by_clause=sql_measure.group_by_columns,
            description=f"SQL query for measure: {sql_measure.name}",
            original_kbi=sql_measure.original_kbi
        )
        
        return query

    def _create_exception_aggregation_query(self, sql_measure: SQLMeasure, sql_definition: SQLDefinition, options: SQLTranslationOptions) -> SQLQuery:
        """Create a special query for exception aggregation with subquery structure"""

        measure_alias = sql_measure.technical_name or "measure_value"

        # Build the complete custom SQL for exception aggregation
        subquery_where = ""
        if sql_measure.filters:
            subquery_where = f"\n        WHERE\n            " + "\n            AND ".join(sql_measure.filters)

        # Build the full query string manually for exception aggregation
        from_clause = self._quote_identifier(sql_measure.source_table)
        if sql_definition.schema:
            from_clause = f"{self._quote_identifier(sql_definition.schema)}.{from_clause}"

        # Create complete custom SQL for exception aggregation
        # Extract the subquery parts from the sql_expression
        sql_expr = sql_measure.sql_expression

        # Build complete custom SQL
        custom_sql = f"SELECT {sql_expr.replace('FROM `FactSales`', f'FROM {from_clause}{subquery_where}')} AS {self._quote_identifier(measure_alias)}"

        # Create query with custom SQL
        query = SQLQuery(
            dialect=self.dialect,
            select_clause=[],   # Not used with custom SQL
            from_clause="",     # Empty string for custom SQL
            where_clause=[],    # Not used with custom SQL
            group_by_clause=[], # Not used with custom SQL
            description=f"SQL query for measure: {sql_measure.name}",
            original_kbi=sql_measure.original_kbi
        )

        # Set the custom SQL directly
        query._custom_sql = custom_sql

        return query

    def _create_combined_sql_query(self, sql_measures: List[SQLMeasure], sql_definition: SQLDefinition, options: SQLTranslationOptions) -> SQLQuery:
        """Create combined SQL query for multiple measures with proper table handling"""
        
        # Group measures by source table
        table_measures = {}
        for sql_measure in sql_measures:
            table = sql_measure.source_table or "fact_table"
            if table not in table_measures:
                table_measures[table] = []
            table_measures[table].append(sql_measure)
        
        # If we have multiple tables, create a query with subqueries/joins
        if len(table_measures) > 1:
            return self._create_multi_table_sql_query(table_measures, sql_definition, options)
        else:
            # Single table - create simple query
            table_name = list(table_measures.keys())[0]
            measures = table_measures[table_name]
            return self._create_single_table_sql_query(measures, table_name, sql_definition, options)
    
    def _create_single_table_sql_query(self, sql_measures: List[SQLMeasure], table_name: str, sql_definition: SQLDefinition, options: SQLTranslationOptions) -> SQLQuery:
        """Create SQL query for measures from a single table"""
        select_expressions = []
        all_filters = []
        
        for sql_measure in sql_measures:
            alias = sql_measure.technical_name or f"measure_{len(select_expressions) + 1}"
            select_expressions.append(f"{sql_measure.to_sql_expression()} AS {self._quote_identifier(alias)}")
            all_filters.extend(sql_measure.filters)
        
        # Build FROM clause
        from_clause = self._quote_identifier(table_name)
        if sql_definition.schema:
            from_clause = f"{self._quote_identifier(sql_definition.schema)}.{from_clause}"
        
        # Process and deduplicate filters
        unique_filters = self._process_and_deduplicate_filters(all_filters, sql_definition)
        
        # Create query
        query = SQLQuery(
            dialect=self.dialect,
            select_clause=select_expressions,
            from_clause=from_clause,
            where_clause=unique_filters,
            description=f"SQL query for {len(sql_measures)} measures from {table_name}"
        )
        
        return query
    
    def _create_multi_table_sql_query(self, table_measures: Dict[str, List[SQLMeasure]], sql_definition: SQLDefinition, options: SQLTranslationOptions) -> SQLQuery:
        """Create SQL query for measures from multiple tables using UNION ALL"""
        union_parts = []
        
        for table_name, measures in table_measures.items():
            for measure in measures:
                # Create individual SELECT for each measure
                alias = measure.technical_name or "measure_value"
                
                # Build FROM clause
                from_clause = self._quote_identifier(table_name)
                if sql_definition.schema:
                    from_clause = f"{self._quote_identifier(sql_definition.schema)}.{from_clause}"
                
                # Process filters
                processed_filters = self._process_and_deduplicate_filters(measure.filters, sql_definition)
                
                # Build individual query
                select_part = f"SELECT '{alias}' AS measure_name, {measure.to_sql_expression()} AS measure_value"
                from_part = f"FROM {from_clause}"
                
                if processed_filters:
                    where_part = f"WHERE {' AND '.join(processed_filters)}"
                    query_part = f"{select_part} {from_part} {where_part}"
                else:
                    query_part = f"{select_part} {from_part}"
                
                union_parts.append(query_part)
        
        # Combine with UNION ALL
        combined_sql = "\nUNION ALL\n".join(union_parts)
        
        # Create a query object (note: this is a special case)
        query = SQLQuery(
            dialect=self.dialect,
            select_clause=[],  # Will be overridden
            from_clause="",    # Will be overridden
            description=f"Multi-table SQL query with {len(sum(table_measures.values(), []))} measures"
        )
        
        # Override the to_sql method result
        query._custom_sql = combined_sql
        
        return query
    
    def _process_and_deduplicate_filters(self, filters: List[str], sql_definition: SQLDefinition) -> List[str]:
        """Process filters with variable substitution and deduplication"""
        processed_filters = []
        variables = sql_definition.default_variables or {}
        
        # Get expanded filters from KBI definition (stored in sql_definition)
        expanded_filters = {}
        if hasattr(sql_definition, 'filters') and sql_definition.filters:
            for filter_group, filters in sql_definition.filters.items():
                if isinstance(filters, dict):
                    for filter_name, filter_value in filters.items():
                        expanded_filters[filter_name] = filter_value
                else:
                    expanded_filters[filter_group] = str(filters)
        
        for filter_condition in filters:
            if not filter_condition:
                continue
                
            # Handle special query_filter expansion
            if filter_condition == "$query_filter":
                # First try to expand from sql_definition filters
                if hasattr(sql_definition, 'filters') and sql_definition.filters:
                    query_filters = sql_definition.filters.get('query_filter', {})
                    for filter_name, filter_value in query_filters.items():
                        processed_filter = self._substitute_variables_in_filter(filter_value, variables, expanded_filters)
                        if processed_filter:
                            processed_filters.append(processed_filter)
                # Then try expanded_filters
                elif 'query_filter' in expanded_filters:
                    processed_filter = self._substitute_variables_in_filter(expanded_filters['query_filter'], variables, expanded_filters)
                    if processed_filter:
                        processed_filters.append(processed_filter)
                continue
            
            # Process regular filters with variable substitution
            processed_filter = self._substitute_variables_in_filter(filter_condition, variables, expanded_filters)
            if processed_filter:
                processed_filters.append(processed_filter)
        
        # Remove duplicates while preserving order
        unique_filters = []
        seen = set()
        for f in processed_filters:
            if f not in seen:
                unique_filters.append(f)
                seen.add(f)
        
        return unique_filters
    
    def _substitute_variables_in_filter(self, filter_condition: str, variables: Dict[str, Any], expanded_filters: Dict[str, str] = None) -> str:
        """Substitute variables in a filter condition"""
        result = filter_condition

        # Combine all available filters and variables
        all_substitutions = {}
        if variables:
            all_substitutions.update(variables)
        if expanded_filters:
            all_substitutions.update(expanded_filters)

        # Debug logging
        self.logger.debug(f"Substituting variables in filter: {filter_condition}")
        self.logger.debug(f"Available variables: {variables}")
        self.logger.debug(f"Available expanded filters: {expanded_filters}")

        for var_name, var_value in all_substitutions.items():
            # Handle different variable formats
            patterns = [f"\\$var_{var_name}", f"\\${var_name}"]

            for pattern in patterns:
                if isinstance(var_value, list):
                    # Handle list variables for IN clauses
                    quoted_values = [f"'{str(v)}'" for v in var_value]
                    replacement = f"({', '.join(quoted_values)})"
                    result = re.sub(pattern, replacement, result)
                    self.logger.debug(f"Replaced {pattern} with {replacement}")
                elif isinstance(var_value, (int, float)):
                    # Handle numeric variables (no quotes)
                    result = re.sub(pattern, str(var_value), result)
                    self.logger.debug(f"Replaced {pattern} with {str(var_value)}")
                else:
                    # Handle string variables
                    replacement = f"'{str(var_value)}'"
                    result = re.sub(pattern, replacement, result)
                    self.logger.debug(f"Replaced {pattern} with {replacement}")

        self.logger.debug(f"Final substituted filter: {result}")
        return result
    
    def _quote_identifier(self, identifier: str) -> str:
        """Quote identifier according to SQL dialect"""
        if self.dialect == SQLDialect.MYSQL or self.dialect == SQLDialect.DATABRICKS:
            return f"`{identifier}`"
        elif self.dialect == SQLDialect.SQLSERVER:
            return f"[{identifier}]"
        else:
            return f'"{identifier}"'


class SQLTimeIntelligenceHelper:
    """Helper class for common SQL time intelligence patterns"""
    
    def __init__(self, dialect: SQLDialect = SQLDialect.STANDARD):
        self.dialect = dialect
    
    def create_ytd_sql_structure(self, date_column: str = 'fiscal_date') -> SQLStructure:
        """Create Year-to-Date SQL structure"""
        processor = SQLStructureProcessor(self.dialect)
        sql_template = processor._create_ytd_sql_template(date_column)
        
        return SQLStructure(
            description="Year to Date",
            sql_template=sql_template,
            date_column=date_column,
            filters=[sql_template.strip()],
            display_sign=1
        )
    
    def create_ytg_sql_structure(self, date_column: str = 'fiscal_date') -> SQLStructure:
        """Create Year-to-Go SQL structure"""
        processor = SQLStructureProcessor(self.dialect)
        sql_template = processor._create_ytg_sql_template(date_column)
        
        return SQLStructure(
            description="Year to Go",
            sql_template=sql_template,
            date_column=date_column,
            filters=[sql_template.strip()],
            display_sign=1
        )
    
    def create_prior_year_sql_structure(self, date_column: str = 'fiscal_date') -> SQLStructure:
        """Create Prior Year SQL structure"""
        processor = SQLStructureProcessor(self.dialect)
        sql_template = processor._create_prior_period_sql_template(date_column)
        
        return SQLStructure(
            description="Prior Year",
            sql_template=sql_template,
            date_column=date_column,
            filters=[sql_template.strip()],
            display_sign=1
        )
    
    def create_variance_sql_structure(self, base_measures: List[str]) -> SQLStructure:
        """Create variance calculation SQL structure"""
        if len(base_measures) >= 2:
            formula = f"({base_measures[0]}) - ({base_measures[1]})"
        else:
            formula = f"({base_measures[0] if base_measures else 'current'}) - (prior)"
        
        return SQLStructure(
            description="Variance Analysis",
            formula=formula,
            display_sign=1
        )