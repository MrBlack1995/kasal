"""Tests for MQueryParser."""
import pytest
from src.engines.crewai.tools.custom.metric_view_utils.mquery_parser import MQueryParser


@pytest.fixture
def parser():
    return MQueryParser()


class TestParseJson:
    def test_basic_fact_table(self, parser):
        entries = [{
            'table_name': 'fact_sales',
            'transpiled_sql': 'SELECT region, SUM(amount) AS amount FROM catalog.schema.sales GROUP BY region',
            'validation_passed': 'Yes',
        }]
        tables = parser.parse_json(entries)
        assert 'fact_sales' in tables
        info = tables['fact_sales']
        assert info.is_fact is True
        assert info.source_table == 'catalog.schema.sales'
        assert len(info.aggregate_columns) == 1
        assert info.aggregate_columns[0]['name'] == 'amount'
        assert 'region' in info.group_by_columns

    def test_dim_table_no_aggregates(self, parser):
        entries = [{
            'table_name': 'dim_region',
            'transpiled_sql': 'SELECT code, name FROM catalog.schema.regions',
            'validation_passed': 'Yes',
        }]
        tables = parser.parse_json(entries)
        assert 'dim_region' in tables
        assert tables['dim_region'].is_fact is False

    def test_skips_failed_validation(self, parser):
        entries = [{
            'table_name': 'bad_table',
            'transpiled_sql': 'SELECT * FROM catalog.schema.x',
            'validation_passed': 'No',
        }]
        tables = parser.parse_json(entries)
        assert 'bad_table' not in tables

    def test_accepts_list_input(self, parser):
        entries = [{
            'table_name': 'test',
            'transpiled_sql': 'SELECT col, SUM(val) AS val FROM cat.sch.tbl GROUP BY col',
            'validation_passed': 'Yes',
        }]
        tables = parser.parse_json(entries)
        assert 'test' in tables

    def test_extracts_where_filters(self, parser):
        entries = [{
            'table_name': 'fact',
            'transpiled_sql': "SELECT col, SUM(val) AS val FROM cat.sch.tbl WHERE status = 'active' GROUP BY col",
            'validation_passed': 'Yes',
        }]
        tables = parser.parse_json(entries)
        assert len(tables['fact'].static_filters) >= 1

    def test_extracts_left_joins(self, parser):
        sql = (
            "SELECT t.col, SUM(t.val) AS val "
            "FROM cat.sch.fact t "
            "LEFT JOIN cat.sch.dim d ON t.key = d.key "
            "GROUP BY t.col"
        )
        entries = [{'table_name': 'fact', 'transpiled_sql': sql, 'validation_passed': 'Yes'}]
        tables = parser.parse_json(entries)
        assert 'd' in tables['fact'].dim_source_tables


class TestGroupByAll:
    def test_infer_group_by_all(self, parser):
        sql = "SELECT region, country, SUM(amount) AS amount FROM cat.sch.tbl GROUP BY ALL"
        entries = [{'table_name': 'test', 'transpiled_sql': sql, 'validation_passed': 'Yes'}]
        tables = parser.parse_json(entries)
        gb = tables['test'].group_by_columns
        assert 'region' in gb
        assert 'country' in gb


class TestMLanguageTokenNormalization:
    """M-language escape tokens (#(lf) etc.) must not leak into parsed SQL/columns."""

    def test_lf_token_stripped_from_source(self):
        from src.engines.crewai.tools.custom.metric_view_utils.mquery_parser import MQueryParser
        sql = ("SELECT a, b,#(lf) c AS flag#(lf) FROM cat.sch.t "
               "WHERE y = YEAR(CURRENT_DATE)")
        info = MQueryParser()._parse_sql('t', sql)
        assert info.source_table == 'cat.sch.t'
        assert '#(lf)' not in str(info.group_by_columns)
        assert '#(lf)' not in (info.full_sql or '')

    def test_doubled_quotes_collapsed(self):
        from src.engines.crewai.tools.custom.metric_view_utils.mquery_parser import MQueryParser
        sql = 'SELECT a, if(x=1,""yes"",""no"") AS f FROM cat.sch.t'
        info = MQueryParser()._parse_sql('t', sql)
        assert '""' not in (info.full_sql or '')


class TestClassifyMquerySource:
    """classify_mquery_source: route no-SQL M sources to a skip-with-reason
    category so the report can emit them as a note (mirrors untranslatable
    measures) instead of routing benign non-facts to broken SQL recovery."""

    def _C(self, m):
        from src.engines.crewai.tools.custom.metric_view_utils.mquery_parser import (
            classify_mquery_source)
        return classify_mquery_source(m)

    def test_inline_constant_table(self):
        m = ('let Source = Table.FromRows(Json.Document(Binary.Decompress('
             'Binary.FromText("i45W", BinaryEncoding.Base64), Compression.Deflate))) '
             'in Source')
        assert self._C(m)[0] == 'inline_const'

    def test_dax_calc_generateseries(self):
        assert self._C('GENERATESERIES(-5, 20, 5)')[0] == 'dax_calc'

    def test_dax_calc_summarizecolumns(self):
        assert self._C('SUMMARIZECOLUMNS(Dim_Date[YearMonth])')[0] == 'dax_calc'

    def test_dax_calc_parameter_query(self):
        assert self._C('"N" meta [IsParameterQuery=true, Type="Text"]')[0] == 'dax_calc'

    def test_external_access_database(self):
        m = 'let Source = Access.Database(File.Contents("x.accdb")) in Source'
        assert self._C(m)[0] == 'external'

    def test_extractable_native_query(self):
        m = 'let Source = Value.NativeQuery(db, "SELECT a FROM t") in Source'
        assert self._C(m)[0] == 'extractable'

    def test_extractable_databricks_connector(self):
        m = 'let Source = Databricks.Catalogs("h","p"){[Name="c"]}[Data] in Source'
        assert self._C(m)[0] == 'extractable'

    def test_unknown_shape(self):
        assert self._C('let Source = List.Numbers(1,10) in Source')[0] == 'unknown'

    def test_empty_input(self):
        assert self._C('')[0] == 'unknown'
        assert self._C(None)[0] == 'unknown'

    def test_reason_is_human_readable(self):
        cat, reason = self._C('GENERATESERIES(1,10)')
        assert isinstance(reason, str) and len(reason) > 10

    def test_inline_const_precedence_over_dax(self):
        # a base64 inline table that also mentions VALUES must classify as inline_const
        m = ('Table.FromRows(Json.Document(Binary.Decompress('
             'Binary.FromText("x", BinaryEncoding.Base64))))  // VALUES helper')
        assert self._C(m)[0] == 'inline_const'

    def test_inline_const_plain_literal_rows_no_base64(self):
        # Table.FromRows with hardcoded rows spelled out in plain M (no
        # base64/Binary.Decompress wrapper) is the same category — still an
        # inline constant table, no warehouse source.
        m = 'let Source = Table.FromRows({{"a", 1}, {"b", 2}}) in Source'
        assert self._C(m)[0] == 'inline_const'

    def test_dax_calc_summarize(self):
        # SUMMARIZE is a distinct DAX function from SUMMARIZECOLUMNS — both
        # must classify as dax_calc.
        assert self._C('SUMMARIZE(T, T[Col])')[0] == 'dax_calc'

    def test_dax_calc_calculatetable(self):
        assert self._C('CALCULATETABLE(SUMMARIZE(T, T[Col]), T[Flag]=1)')[0] == 'dax_calc'

    def test_dax_calc_tuple_literal_table(self):
        # DAX's bare table-constructor syntax: a brace-enclosed list of
        # parenthesized row tuples, e.g. { ("a", 1), ("b", 2) }.
        m = '{ ("Sub Domain", NAMEOF(T[Col]), 0, "Check Hierarchy", 0) }'
        assert self._C(m)[0] == 'dax_calc'


class TestExtractSourceTable:
    """extract_source_table: parse catalog.schema.table from an *extractable* M
    source (Databricks connector nav / native query / Sql.Database). Returns None
    when it can't resolve confidently — never guesses (a wrong source_table would
    silently wire a bad join)."""

    def _E(self, m):
        from src.engines.crewai.tools.custom.metric_view_utils.mquery_parser import (
            extract_source_table)
        return extract_source_table(m)

    def test_databricks_catalogs_navigation_chain(self):
        m = ('let Source = Databricks.Catalogs("h.databricks.com","/sql/1.0/wh/abc")'
             '{[Name="dc_datalake_prod_001"]}[Data]{[Name="udm_example_md"]}[Data]'
             '{[Name="ca_dim_workcenter"]}[Data] in Source')
        assert self._E(m) == 'dc_datalake_prod_001.udm_example_md.ca_dim_workcenter'

    def test_databricks_keyed_navigation(self):
        m = ('Databricks.Catalogs(){[Catalog="c1"]}[Data]{[Schema="s1"]}[Data]'
             '{[Item="t1"]}[Data]')
        assert self._E(m) == 'c1.s1.t1'

    def test_native_query_from_clause(self):
        m = 'let Source = Value.NativeQuery(db, "SELECT a, b FROM cat_x.sch_y.tbl_z WHERE 1=1") in Source'
        assert self._E(m) == 'cat_x.sch_y.tbl_z'

    def test_sql_database_schema_item(self):
        m = 'let Source = Sql.Database("myserver","mydb"){[Schema="dbo",Item="Orders"]} in Source'
        assert self._E(m) == 'mydb.dbo.Orders'

    def test_inline_const_returns_none(self):
        m = ('let Source = Table.FromRows(Json.Document(Binary.Decompress('
             'Binary.FromText("i45W",BinaryEncoding.Base64)))) in Source')
        assert self._E(m) is None

    def test_dax_calc_returns_none(self):
        assert self._E('GENERATESERIES(-5,20,5)') is None

    def test_external_returns_none(self):
        assert self._E('let Source = Access.Database(File.Contents("x.accdb")) in Source') is None

    def test_incomplete_databricks_chain_returns_none(self):
        # only one [Name=…] segment — not enough to form a 3-level name
        m = 'let Source = Databricks.Catalogs("h","p"){[Name="onlycat"]}[Data] in Source'
        assert self._E(m) is None

    def test_none_and_empty_input(self):
        assert self._E(None) is None
        assert self._E('') is None

    def test_databricks_quoted_catalog_name(self):
        # M quotes an identifier as #"like this" whenever it isn't a valid bare
        # identifier (e.g. contains spaces) — the real shape the Databricks
        # connector emits for its top-level catalog step. The unquoted-only
        # regex silently dropped this match, leaving only 2/3 names and always
        # returning None even though the chain was fully resolvable.
        m = ('let Source = Databricks.Catalogs(DatabricksHost, DatabricksHTTPpath, '
             '[Catalog=null, Database=null]), '
             'metastore_Database = Source{[Name=#"Databricks Data Catalog",Kind="Database"]}[Data], '
             'curated_Schema = metastore_Database{[Name="curated_data_quality",Kind="Schema"]}[Data], '
             'dim_Table = curated_Schema{[Name="dim_rules_inventory_v7",Kind="Table"]}[Data] '
             'in dim_Table')
        assert self._E(m) == 'Databricks Data Catalog.curated_data_quality.dim_rules_inventory_v7'

    def test_snowflake_catalog_navigation_chain(self):
        # Non-Databricks catalog-browse connector sharing the same [Name=,Kind=]
        # navigation shape (a Power Query SDK convention, not Databricks-only).
        m = ('let Source = Snowflake.Databases("acct.snowflakecomputing.com","WH")'
             '{[Name="MY_DB"]}[Data]{[Name="PUBLIC"]}[Data]{[Name="ORDERS"]}[Data] in Source')
        assert self._E(m) == 'MY_DB.PUBLIC.ORDERS'


class TestResolveMqueryToSql:
    """resolve_mquery_to_sql: compile an extractable M source into compact SQL
    (SELECT ... FROM catalog.schema.table) the downstream SQL-only parser can
    read directly — the deterministic alternative to routing catalog-browse
    connector M (Databricks.Catalogs et al) through an LLM."""

    def _R(self, m):
        from src.engines.crewai.tools.custom.metric_view_utils.mquery_parser import (
            resolve_mquery_to_sql)
        return resolve_mquery_to_sql(m)

    def test_databricks_catalogs_with_select_and_rename(self):
        m = (
            'let\n'
            '    Source = Databricks.Catalogs(DatabricksHost, DatabricksHTTPpath, [Catalog=null]),\n'
            '    metastore_Database = Source{[Name=#"Databricks Data Catalog",Kind="Database"]}[Data],\n'
            '    curated_Schema = metastore_Database{[Name="curated_data_quality",Kind="Schema"]}[Data],\n'
            '    dim_Table = curated_Schema{[Name="dim_rules_inventory_v7",Kind="Table"]}[Data],\n'
            '    #"Removed Other Columns" = Table.SelectColumns(dim_Table,{"rule_code", "domain", "is_active"}),\n'
            '    #"Renamed Columns" = Table.RenameColumns(#"Removed Other Columns",'
            '{{"rule_code", "Rule Code"}, {"is_active", "Is Active"}})\n'
            'in\n'
            '    #"Renamed Columns"'
        )
        sql = self._R(m)
        assert sql == (
            'SELECT rule_code AS `Rule Code`, domain, is_active AS `Is Active` '
            'FROM `Databricks Data Catalog`.curated_data_quality.dim_rules_inventory_v7'
        )

    def test_quotes_identifiers_with_spaces(self):
        # Column/alias/catalog names containing spaces (routine in PBI M) must
        # come out backtick-quoted — unquoted, they're invalid SQL syntax.
        m = ('let Source = Databricks.Catalogs("h","p"){[Name="My Catalog"]}[Data]'
             '{[Name="sch"]}[Data]{[Name="tbl"]}[Data],\n'
             '    Sel = Table.SelectColumns(Source,{"Order Date","amount"})\n'
             'in Sel')
        assert self._R(m) == 'SELECT `Order Date`, amount FROM `My Catalog`.sch.tbl'

    def test_databricks_catalogs_no_select_columns_falls_back_to_star(self):
        m = ('let Source = Databricks.Catalogs("h","p"){[Name="cat"]}[Data]'
             '{[Name="sch"]}[Data]{[Name="tbl"]}[Data] in Source')
        assert self._R(m) == 'SELECT * FROM cat.sch.tbl'

    def test_unresolvable_source_returns_none(self):
        assert self._R('GENERATESERIES(-5, 20, 5)') is None
        assert self._R('let Source = Access.Database(File.Contents("x.accdb")) in Source') is None
        assert self._R(None) is None
        assert self._R('') is None


class TestResolveMqueryWithContext:
    """resolve_mquery_with_context: the direct resolver extended with model-
    level context for a table's M that can't resolve on its own — a reference
    to a disabled staging query, or a parameter-driven source."""

    def _RC(self, m, expressions=None):
        from src.engines.crewai.tools.custom.metric_view_utils.mquery_parser import (
            resolve_mquery_with_context)
        return resolve_mquery_with_context(m, expressions)

    def test_falls_through_to_direct_resolver_when_no_context_needed(self):
        m = ('let Source = Databricks.Catalogs("h","p"){[Name="cat"]}[Data]'
             '{[Name="sch"]}[Data]{[Name="tbl"]}[Data] in Source')
        assert self._RC(m) == 'SELECT * FROM cat.sch.tbl'

    def test_follows_quoted_reference_to_shared_expression(self):
        m = 'let Source = #"f_vendor_universe - DataBricks SQL" in Source'
        expressions = {
            "f_vendor_universe - DataBricks SQL": (
                'let Source = Databricks.Catalogs("h","p"){[Name="cat"]}[Data]'
                '{[Name="sch"]}[Data]{[Name="tbl"]}[Data] in Source'
            ),
        }
        assert self._RC(m, expressions) == 'SELECT * FROM cat.sch.tbl'

    def test_follows_bare_unquoted_reference(self):
        m = 'let Source = SomeStagingQuery in Source'
        expressions = {
            "SomeStagingQuery": (
                'let Source = Databricks.Catalogs("h","p"){[Name="cat"]}[Data]'
                '{[Name="sch"]}[Data]{[Name="tbl"]}[Data] in Source'
            ),
        }
        assert self._RC(m, expressions) == 'SELECT * FROM cat.sch.tbl'

    def test_follows_bare_name_with_no_let_wrapper(self):
        # Some Admin-Scanner-reported tables carry just the referenced name,
        # not even a `let...in` wrapper.
        m = '"1_Report Measures"'
        expressions = {"1_Report Measures": 'let Source = Databricks.Catalogs("h","p")'
                        '{[Name="cat"]}[Data]{[Name="sch"]}[Data]{[Name="tbl"]}[Data] in Source'}
        assert self._RC(m, expressions) == 'SELECT * FROM cat.sch.tbl'

    def test_falls_back_to_parameter_evaluation(self):
        m = (
            'let\n'
            'FromClause = Catalog_Name & "." & Database & "." & "hub_product_v2",\n'
            'NativeQuery = Value.NativeQuery(Data_Mesh, "select * from " & FromClause, null, [EnableFolding=true])\n'
            'in NativeQuery'
        )
        expressions = {
            "Catalog_Name": '"dc_prod_001" meta [IsParameterQuery = true]',
            "Database": '"golden" meta [IsParameterQuery = true]',
        }
        assert self._RC(m, expressions) == 'select * from dc_prod_001.golden.hub_product_v2'

    def test_no_expressions_returns_none_for_unresolvable(self):
        m = 'let Source = #"Some Staging Query" in Source'
        assert self._RC(m, None) is None
        assert self._RC(m, {}) is None

    def test_reference_target_not_in_expressions_returns_none(self):
        m = 'let Source = #"Missing Query" in Source'
        assert self._RC(m, {"Other": "x"}) is None

    def test_follows_reference_with_trailing_column_cleanup(self):
        # A reference followed by a cosmetic step (TransformColumnTypes) —
        # not a pure passthrough, but still reads exactly one physical table.
        m = (
            'let\n'
            '    Source = #"Staging Vendor",\n'
            '    #"Changed Type" = Table.TransformColumnTypes(Source,'
            '{{"Check Status", Int64.Type}})\n'
            'in\n'
            '    #"Changed Type"'
        )
        expressions = {
            "Staging Vendor": ('let Source = Databricks.Catalogs("h","p"){[Name="cat"]}[Data]'
                                '{[Name="sch"]}[Data]{[Name="tbl"]}[Data] in Source'),
        }
        assert self._RC(m, expressions) == 'SELECT * FROM cat.sch.tbl'

    def test_does_not_guess_when_sources_are_combined(self):
        # First binding IS a reference, but the M also Table.Combines it with
        # a second source — trusting "the first binding" here would silently
        # drop the second source. Must return None, not guess.
        m = (
            'let\n'
            '    Source = #"Old Query",\n'
            '    #"Appended Query" = Table.Combine({Source, #"New Query"})\n'
            'in\n'
            '    #"Appended Query"'
        )
        expressions = {
            "Old Query": ('let Source = Databricks.Catalogs("h","p"){[Name="cat"]}[Data]'
                          '{[Name="sch"]}[Data]{[Name="tbl1"]}[Data] in Source'),
            "New Query": ('let Source = Databricks.Catalogs("h","p"){[Name="cat"]}[Data]'
                          '{[Name="sch"]}[Data]{[Name="tbl2"]}[Data] in Source'),
        }
        assert self._RC(m, expressions) is None


class TestExtractFirstBindingReference:
    """_extract_first_binding_reference: identify the physical source via a
    let block's FIRST binding, even when later bindings reshape columns —
    but never when the M combines multiple sources (that would silently pick
    only one side of a union)."""

    def _F(self, m):
        from src.engines.crewai.tools.custom.metric_view_utils.mquery_parser import (
            _extract_first_binding_reference)
        return _extract_first_binding_reference(m)

    def test_reference_plus_cleanup_step(self):
        m = (
            'let\n'
            '    Source = #"f_vendor_details_l3_uniqueness - DataBricks SQL",\n'
            '    #"Changed Type" = Table.TransformColumnTypes(Source,'
            '{{"Check Status", Int64.Type}})\n'
            'in\n'
            '    #"Changed Type"'
        )
        assert self._F(m) == 'f_vendor_details_l3_uniqueness - DataBricks SQL'

    def test_bare_unquoted_first_reference(self):
        m = 'let Source = SomeStagingQuery, X = Table.RenameColumns(Source, {}) in X'
        assert self._F(m) == 'SomeStagingQuery'

    def test_bails_on_table_combine(self):
        m = 'let Source = #"A", Y = Table.Combine({Source, #"B"}) in Y'
        assert self._F(m) is None

    def test_bails_on_table_append(self):
        m = 'let Source = #"A", Y = Table.Append({Source, #"B"}) in Y'
        assert self._F(m) is None

    def test_bails_on_table_join(self):
        m = 'let Source = #"A", Y = Table.Join(Source, "k", #"B", "k") in Y'
        assert self._F(m) is None

    def test_first_binding_not_a_reference_returns_none(self):
        m = 'let Source = Databricks.Catalogs() in Source'
        assert self._F(m) is None

    def test_no_let_block_returns_none(self):
        assert self._F('GENERATESERIES(1,10)') is None
        assert self._F(None) is None
        assert self._F('') is None


class TestExtractSourceTableWithContext:
    """extract_source_table_with_context: same context-aware resolution as
    resolve_mquery_with_context, but returns just the physical FQN — used for
    join_key_map[dim].source_table, a plain config value."""

    def _EC(self, m, expressions=None):
        from src.engines.crewai.tools.custom.metric_view_utils.mquery_parser import (
            extract_source_table_with_context)
        return extract_source_table_with_context(m, expressions)

    def test_direct_resolution_unchanged(self):
        m = ('let Source = Databricks.Catalogs("h","p"){[Name="cat"]}[Data]'
             '{[Name="sch"]}[Data]{[Name="tbl"]}[Data] in Source')
        assert self._EC(m) == 'cat.sch.tbl'

    def test_follows_reference_returns_fqn_not_full_sql(self):
        m = 'let Source = #"Staging" in Source'
        expressions = {
            "Staging": ('let Source = Databricks.Catalogs("h","p"){[Name="cat"]}[Data]'
                        '{[Name="sch"]}[Data]{[Name="tbl"]}[Data] in Source'),
        }
        assert self._EC(m, expressions) == 'cat.sch.tbl'

    def test_parameter_driven_extracts_fqn_from_resolved_sql(self):
        m = (
            'let\n'
            'FromClause = Catalog_Name & "." & Database & "." & "hub_product_v2",\n'
            'NativeQuery = Value.NativeQuery(Data_Mesh, "select * from " & FromClause, null, [EnableFolding=true])\n'
            'in NativeQuery'
        )
        expressions = {
            "Catalog_Name": '"dc_prod_001" meta [IsParameterQuery = true]',
            "Database": '"golden" meta [IsParameterQuery = true]',
        }
        assert self._EC(m, expressions) == 'dc_prod_001.golden.hub_product_v2'

    def test_unresolvable_returns_none(self):
        assert self._EC('GENERATESERIES(1,10)', {"X": "y"}) is None
        assert self._EC('let Source = #"Missing" in Source', {"Other": "x"}) is None
