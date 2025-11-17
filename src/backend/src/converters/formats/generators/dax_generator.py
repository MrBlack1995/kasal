from typing import List
import re
from converters.models.kbi import KBI, KBIDefinition, DAXMeasure
from converters.rules.translators.filter_resolver import FilterResolver
from converters.rules.translators.formula_translator import FormulaTranslator
from converters.rules.aggregations.dax_aggregations import detect_and_build_aggregation
from converters.formats.parsers.formula_parser import FormulaParser


class DAXGenerator:
    def __init__(self):
        self.filter_resolver = FilterResolver()
        self.formula_translator = FormulaTranslator()
        self.formula_parser = FormulaParser()
    
    def generate_dax_measure(self, definition: KBIDefinition, kbi: KBI) -> DAXMeasure:
        """Generate a complete DAX measure from a KBI definition using enhanced aggregations."""
        # Get the measure name
        measure_name = self.formula_translator.create_measure_name(kbi, definition)
        
        # Parse formula to handle CASE WHEN and other complex expressions
        parsed_formula = self.formula_parser.parse_formula(kbi.formula, kbi.source_table or 'Table')
        
        # Create KBI definition dict for enhanced aggregation system
        kbi_dict = {
            'formula': parsed_formula,
            'source_table': kbi.source_table,
            'aggregation_type': kbi.aggregation_type,
            'weight_column': kbi.weight_column,
            'target_column': kbi.target_column,
            'percentile': kbi.percentile,
            'exceptions': kbi.exceptions or [],
            'display_sign': kbi.display_sign,
            'exception_aggregation': kbi.exception_aggregation,
            'fields_for_exception_aggregation': kbi.fields_for_exception_aggregation or [],
            'fields_for_constant_selection': kbi.fields_for_constant_selection or []
        }
        
        # Use enhanced aggregation system to build base formula
        base_dax_formula = detect_and_build_aggregation(kbi_dict)
        
        # Resolve filters
        resolved_filters = self.filter_resolver.resolve_filters(definition, kbi)
        
        # Add filters and constant selection to the formula
        dax_formula = self._add_filters_to_dax(base_dax_formula, resolved_filters, kbi.source_table or 'Table', kbi)
        
        return DAXMeasure(
            name=measure_name,
            description=kbi.description or f"Measure for {measure_name}",
            dax_formula=dax_formula,
            original_kbi=kbi
        )
    
    def convert_filter_to_dax(self, filter_condition: str, table_name: str) -> str:
        """
        Convert SQL-style filter syntax to proper DAX FILTER function
        
        Examples:
        - 'column NOT IN (val1, val2)' -> 'NOT Table[column] IN {"val1", "val2"}'
        - 'column BETWEEN val1 AND val2' -> '(Table[column] >= "val1" && Table[column] <= "val2")'
        """
        if not filter_condition:
            return filter_condition
        
        result = filter_condition.strip()
        
        # Step 1: Fix NOT IN patterns
        not_in_pattern = r"(\w+)\s+NOT\s+IN\s*\(([^)]+)\)"
        def fix_not_in(match):
            column = match.group(1)
            values = match.group(2).replace("'", '"')
            return f"NOT {table_name}[{column}] IN {{{values}}}"
        result = re.sub(not_in_pattern, fix_not_in, result)
        
        # Step 2: Fix regular IN patterns  
        in_pattern = r"(\w+)\s+IN\s*\(([^)]+)\)"
        def fix_in(match):
            column = match.group(1)
            values = match.group(2).replace("'", '"')
            return f"{table_name}[{column}] IN {{{values}}}"
        result = re.sub(in_pattern, fix_in, result)
        
        # Step 3: Fix BETWEEN patterns
        between_pattern = r"(\w+)\s+BETWEEN\s+'?([^'\s]+)'?\s+AND\s+'?([^'\s]+)'?"
        def fix_between(match):
            column = match.group(1)
            val1 = match.group(2)
            val2 = match.group(3)
            return f"({table_name}[{column}] >= \"{val1}\" && {table_name}[{column}] <= \"{val2}\")"
        result = re.sub(between_pattern, fix_between, result)
        
        # Step 4: Fix simple equality patterns
        equality_pattern = r"(\w+)\s*=\s*'([^']+)'"
        def fix_equality(match):
            column = match.group(1)
            value = match.group(2)
            return f"{table_name}[{column}] = \"{value}\""
        result = re.sub(equality_pattern, fix_equality, result)
        
        # Step 5: Fix simple equality patterns with double quotes
        equality_pattern_double = r"(\w+)\s*=\s*\"([^\"]+)\""
        def fix_equality_double(match):
            column = match.group(1)
            value = match.group(2)
            return f"{table_name}[{column}] = \"{value}\""
        result = re.sub(equality_pattern_double, fix_equality_double, result)
        
        # Step 6: Fix simple equality patterns without quotes (numbers)
        equality_pattern_number = r"(\w+)\s*=\s*([0-9]+(?:\.[0-9]+)?)"
        def fix_equality_number(match):
            column = match.group(1)
            value = match.group(2)
            return f"{table_name}[{column}] = {value}"
        result = re.sub(equality_pattern_number, fix_equality_number, result)
        
        # Step 7: Convert SQL operators to DAX operators
        result = result.replace(' AND ', ' && ')
        result = result.replace(' OR ', ' || ')
        
        # Step 8: Convert NULL to BLANK() for DAX compatibility
        # Handle various NULL comparison patterns
        result = re.sub(r'\bNULL\b', 'BLANK()', result)
        
        return result

    def _add_filters_to_dax(self, base_dax_formula: str, filters: List[str], table_name: str, kbi = None) -> str:
        """Add filters and constant selection to a DAX formula using CALCULATE and FILTER functions."""
        filter_functions = []
        
        # Add regular filters
        if filters:
            for filter_condition in filters:
                # Convert each filter to proper DAX with table references
                dax_condition = self.convert_filter_to_dax(filter_condition, table_name)
                
                # Wrap each condition in a FILTER function
                filter_function = f"FILTER(\n        {table_name},\n        {dax_condition}\n    )"
                filter_functions.append(filter_function)
        
        # Add constant selection REMOVEFILTERS
        if kbi and kbi.fields_for_constant_selection:
            for field in kbi.fields_for_constant_selection:
                removefilter_function = f"REMOVEFILTERS({table_name}[{field}])"
                filter_functions.append(removefilter_function)
        
        # If no filters or constant selection, return base formula
        if not filter_functions:
            return base_dax_formula
        
        # Build CALCULATE with separate filter arguments
        filters_formatted = ",\n\n    ".join(filter_functions)
        
        return f"CALCULATE(\n    {base_dax_formula},\n\n    {filters_formatted}\n)"

    def _build_dax_formula(self, formula_info: dict, filters: List[str], kbi: KBI) -> str:
        """Build the complete DAX formula with proper FILTER functions."""
        aggregation = formula_info['aggregation']
        table_name = formula_info['table_name']
        column_name = formula_info['column_name']
        
        # Base aggregation
        base_formula = f"{aggregation}({table_name}[{column_name}])"
        
        # Add filters if they exist
        if filters:
            filter_functions = []
            
            for filter_condition in filters:
                # Convert each filter to proper DAX with table references
                dax_condition = self.convert_filter_to_dax(filter_condition, table_name)
                
                # Wrap each condition in a FILTER function
                filter_function = f"FILTER(\n        {table_name},\n        {dax_condition}\n    )"
                filter_functions.append(filter_function)
            
            # Build CALCULATE with separate filter arguments
            filters_formatted = ",\n\n    ".join(filter_functions)
            
            dax_formula = f"CALCULATE(\n    {base_formula},\n\n    {filters_formatted}\n)"
        else:
            dax_formula = base_formula
        
        # Apply display sign if needed
        if hasattr(kbi, 'display_sign') and kbi.display_sign == -1:
            dax_formula = f"-1 * ({dax_formula})"
        
        return dax_formula
    
    def generate_measure_comment(self, definition: KBIDefinition, kbi: KBI) -> str:
        """Generate a descriptive comment for the DAX measure."""
        comments = []
        
        # Add source information
        comments.append(f"-- Source: {definition.technical_name}")
        comments.append(f"-- Original Formula: {kbi.formula}")
        
        # Add filter information
        if kbi.filters:
            comments.append("-- Original Filters:")
            for i, filter_item in enumerate(kbi.filters, 1):
                comments.append(f"--   {i}. {filter_item}")
        
        # Add variable information
        if definition.default_variables:
            comments.append("-- Variables used:")
            for var_name, var_value in definition.default_variables.items():
                comments.append(f"--   ${var_name} = {var_value}")
        
        return "\n".join(comments)
    
    def generate_full_measure_definition(self, definition: KBIDefinition, kbi: KBI) -> str:
        """Generate the complete measure definition with comments and DAX formula."""
        dax_measure = self.generate_dax_measure(definition, kbi)
        comments = self.generate_measure_comment(definition, kbi)
        
        full_definition = f"{comments}\n\n{dax_measure.name} = \n{dax_measure.dax_formula}"
        
        return full_definition
    
    def validate_dax_syntax(self, dax_formula: str) -> tuple[bool, str]:
        """Enhanced DAX syntax validation."""
        issues = []
        
        # Check for balanced parentheses
        open_parens = dax_formula.count('(')
        close_parens = dax_formula.count(')')
        if open_parens != close_parens:
            issues.append(f"Unbalanced parentheses: {open_parens} open, {close_parens} close")
        
        # Check for invalid NOT IN syntax
        if "NOT IN" in dax_formula:
            issues.append("Contains invalid 'NOT IN' syntax - should use 'NOT(column IN {})'")
        
        # Check for raw AND operations outside FILTER functions
        if " AND " in dax_formula and "FILTER(" not in dax_formula:
            issues.append("Contains raw AND operations outside FILTER functions")
        
        # Check for basic DAX function syntax
        dax_functions = ['CALCULATE', 'SUM', 'COUNT', 'AVERAGE', 'MAX', 'MIN', 'FILTER']
        has_dax_function = any(func in dax_formula.upper() for func in dax_functions)
        if not has_dax_function:
            issues.append("No recognized DAX functions found")
        
        # Check for table references
        if '[' in dax_formula and ']' in dax_formula:
            # Good - has column references
            pass
        else:
            issues.append("No column references found (missing [column] syntax)")
        
        # Positive validation for proper FILTER usage
        if "CALCULATE(" in dax_formula and "FILTER(" in dax_formula:
            if not issues:
                return True, "Valid DAX with proper FILTER functions"
        
        is_valid = len(issues) == 0
        message = "DAX formula appears valid" if is_valid else "; ".join(issues)
        
        return is_valid, message