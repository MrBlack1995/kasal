"""
Tree Parsing DAX Generator
Extends the standard DAX generator to handle nested measure dependencies
"""

from typing import List, Dict, Tuple
from converters.models.kbi import KBI, KBIDefinition, DAXMeasure
from converters.rules.translators.dependency_resolver import DependencyResolver
from .dax_generator import DAXGenerator


class TreeParsingDAXGenerator(DAXGenerator):
    """DAX Generator with tree parsing capabilities for nested measure dependencies"""
    
    def __init__(self):
        super().__init__()
        self.dependency_resolver = DependencyResolver()
    
    def generate_all_measures(self, definition: KBIDefinition) -> List[DAXMeasure]:
        """
        Generate DAX measures for all KBIs, resolving dependencies
        
        Returns measures in dependency order (dependencies first)
        """
        # Register all measures for dependency resolution
        self.dependency_resolver.register_measures(definition)
        
        # Check for circular dependencies
        cycles = self.dependency_resolver.detect_circular_dependencies()
        if cycles:
            cycle_descriptions = []
            for cycle in cycles:
                cycle_descriptions.append(' -> '.join(cycle))
            raise ValueError(f"Circular dependencies detected:\n" + '\n'.join(cycle_descriptions))
        
        # Get measures in dependency order
        ordered_measures = self.dependency_resolver.get_dependency_order()
        
        measures = []
        for measure_name in ordered_measures:
            kbi = self.dependency_resolver.measure_registry[measure_name]
            
            if kbi.aggregation_type == 'CALCULATED':
                # For calculated measures, resolve dependencies inline
                dax_measure = self._generate_calculated_measure(definition, kbi)
            else:
                # For leaf measures, use standard generation
                dax_measure = self.generate_dax_measure(definition, kbi)
            
            measures.append(dax_measure)
        
        return measures
    
    def _generate_calculated_measure(self, definition: KBIDefinition, kbi: KBI) -> DAXMeasure:
        """Generate DAX for a calculated measure with dependencies"""
        measure_name = self.formula_translator.create_measure_name(kbi, definition)
        
        # For regular calculated measures, resolve dependencies inline
        resolved_formula = self.dependency_resolver.resolve_formula_inline(kbi.technical_name)
        
        # Apply filters and constant selection if specified
        resolved_filters = self.filter_resolver.resolve_filters(definition, kbi)
        dax_formula = self._add_filters_to_dax(resolved_formula, resolved_filters, kbi.source_table or 'Table', kbi)
        
        # Apply display sign if needed (SAP BW visualization property)
        if hasattr(kbi, 'display_sign') and kbi.display_sign == -1:
            dax_formula = f"-1 * ({dax_formula})"
        elif hasattr(kbi, 'display_sign') and kbi.display_sign != 1:
            dax_formula = f"{kbi.display_sign} * ({dax_formula})"
        
        return DAXMeasure(
            name=measure_name,
            description=kbi.description or f"Calculated measure for {measure_name}",
            dax_formula=dax_formula,
            original_kbi=kbi
        )
    
    def get_dependency_analysis(self, definition: KBIDefinition) -> Dict:
        """Get comprehensive dependency analysis for all measures"""
        self.dependency_resolver.register_measures(definition)
        
        analysis = {
            "total_measures": len(definition.kbis),
            "dependency_graph": dict(self.dependency_resolver.dependency_graph),
            "dependency_order": self.dependency_resolver.get_dependency_order(),
            "circular_dependencies": self.dependency_resolver.detect_circular_dependencies(),
            "measure_trees": {}
        }
        
        # Generate dependency trees for all measures
        for kbi in definition.kbis:
            if kbi.technical_name:
                analysis["measure_trees"][kbi.technical_name] = self.dependency_resolver.get_dependency_tree(kbi.technical_name)
        
        return analysis
    
    def generate_measure_with_separate_dependencies(self, definition: KBIDefinition, target_measure_name: str) -> List[DAXMeasure]:
        """
        Generate a target measure along with all its dependencies as separate measures
        
        This creates individual DAX measures for each dependency rather than inlining everything
        """
        self.dependency_resolver.register_measures(definition)
        
        if target_measure_name not in self.dependency_resolver.measure_registry:
            raise ValueError(f"Measure '{target_measure_name}' not found")
        
        # Get all dependencies for the target measure
        all_dependencies = self.dependency_resolver.get_all_dependencies(target_measure_name)
        all_dependencies.add(target_measure_name)  # Include the target itself
        
        # Get them in dependency order
        ordered_measures = self.dependency_resolver.get_dependency_order()
        required_measures = [m for m in ordered_measures if m in all_dependencies]
        
        measures = []
        for measure_name in required_measures:
            kbi = self.dependency_resolver.measure_registry[measure_name]
            
            if kbi.aggregation_type == 'CALCULATED' and measure_name != target_measure_name:
                # For intermediate calculated measures, generate them as separate measures
                # but don't inline their dependencies - reference them by name
                dax_measure = self._generate_separate_calculated_measure(definition, kbi)
            else:
                # For leaf measures or the final target, use standard generation
                if kbi.aggregation_type == 'CALCULATED':
                    # Don't inline for the final measure either - reference separate measures
                    dax_measure = self._generate_separate_calculated_measure(definition, kbi)
                else:
                    dax_measure = self.generate_dax_measure(definition, kbi)
            
            measures.append(dax_measure)
        
        return measures
    
    def _generate_separate_calculated_measure(self, definition: KBIDefinition, kbi: KBI) -> DAXMeasure:
        """Generate DAX for a calculated measure that references other measures by name"""
        measure_name = self.formula_translator.create_measure_name(kbi, definition)
        
        # For regular calculated measures, we keep the original formula (with measure names)
        # but we need to wrap measure references in square brackets for DAX
        formula = kbi.formula
        dependencies = self.dependency_resolver.dependency_graph.get(kbi.technical_name, [])
        
        # Replace measure names with DAX measure references
        resolved_formula = formula
        for dep in dependencies:
            dep_kbi = self.dependency_resolver.measure_registry[dep]
            dep_measure_name = self.formula_translator.create_measure_name(dep_kbi, definition)
            # Replace with proper DAX measure reference
            import re
            resolved_formula = re.sub(r'\b' + re.escape(dep) + r'\b', f'[{dep_measure_name}]', resolved_formula)
        
        # Apply filters and constant selection if specified
        resolved_filters = self.filter_resolver.resolve_filters(definition, kbi)
        dax_formula = self._add_filters_to_dax(resolved_formula, resolved_filters, kbi.source_table or 'Table', kbi)
        
        # Apply display sign if needed (SAP BW visualization property)
        if hasattr(kbi, 'display_sign') and kbi.display_sign == -1:
            dax_formula = f"-1 * ({dax_formula})"
        elif hasattr(kbi, 'display_sign') and kbi.display_sign != 1:
            dax_formula = f"{kbi.display_sign} * ({dax_formula})"
        
        return DAXMeasure(
            name=measure_name,
            description=kbi.description or f"Calculated measure for {measure_name}",
            dax_formula=dax_formula,
            original_kbi=kbi
        )
    
    def get_measure_complexity_report(self, definition: KBIDefinition) -> Dict:
        """Generate a complexity report for all measures"""
        self.dependency_resolver.register_measures(definition)
        
        report = {
            "measures": {},
            "summary": {
                "leaf_measures": 0,
                "calculated_measures": 0,
                "max_dependency_depth": 0,
                "most_complex_measure": None
            }
        }
        
        for kbi in definition.kbis:
            if kbi.technical_name:
                dependencies = self.dependency_resolver.get_all_dependencies(kbi.technical_name)
                depth = self._calculate_dependency_depth(kbi.technical_name)
                
                measure_info = {
                    "name": kbi.technical_name,
                    "description": kbi.description,
                    "type": kbi.aggregation_type or "SUM",
                    "direct_dependencies": len(self.dependency_resolver.dependency_graph.get(kbi.technical_name, [])),
                    "total_dependencies": len(dependencies),
                    "dependency_depth": depth,
                    "is_leaf": len(dependencies) == 0
                }
                
                report["measures"][kbi.technical_name] = measure_info
                
                # Update summary
                if measure_info["is_leaf"]:
                    report["summary"]["leaf_measures"] += 1
                else:
                    report["summary"]["calculated_measures"] += 1
                
                if depth > report["summary"]["max_dependency_depth"]:
                    report["summary"]["max_dependency_depth"] = depth
                    report["summary"]["most_complex_measure"] = kbi.technical_name
        
        return report
    
    def _calculate_dependency_depth(self, measure_name: str, visited: set = None) -> int:
        """Calculate the maximum depth of dependencies for a measure"""
        if visited is None:
            visited = set()
        
        if measure_name in visited:
            return 0  # Circular dependency
        
        dependencies = self.dependency_resolver.dependency_graph.get(measure_name, [])
        if not dependencies:
            return 0  # Leaf measure
        
        visited.add(measure_name)
        max_depth = 0
        
        for dep in dependencies:
            depth = self._calculate_dependency_depth(dep, visited.copy())
            max_depth = max(max_depth, depth + 1)
        
        return max_depth