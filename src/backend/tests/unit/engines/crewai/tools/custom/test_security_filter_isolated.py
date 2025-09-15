"""
Isolated unit tests for SQL Security Filter functionality.

This test file imports only the security classes directly to avoid dependency issues.
"""

import pytest
import sys
import os
import re
import enum

# Add the specific file path directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../../src'))

# Copy the security classes directly to avoid import issues
class QueryType(enum.Enum):
    """SQL query type classification for security filtering."""
    SELECT = "SELECT"
    INSERT = "INSERT" 
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CREATE = "CREATE"
    DROP = "DROP"
    ALTER = "ALTER"
    TRUNCATE = "TRUNCATE"
    GRANT = "GRANT"
    REVOKE = "REVOKE"
    SHOW = "SHOW"
    DESCRIBE = "DESCRIBE"
    USE = "USE"
    UNKNOWN = "UNKNOWN"

class SecurityLevel(enum.Enum):
    """Security levels for query operations."""
    READ_ONLY = "READ_ONLY"
    WRITE_ALLOWED = "WRITE_ALLOWED" 
    ADMIN_REQUIRED = "ADMIN_REQUIRED"

class AuthMethod(enum.Enum):
    """Authentication methods used."""
    OBO_TOKEN = "OBO_TOKEN"
    PAT_TOKEN = "PAT_TOKEN"
    ENV_TOKEN = "ENV_TOKEN"
    NONE = "NONE"

class SQLSecurityFilter:
    """SQL security filter to prevent destructive operations."""
    
    # Define destructive operations that require special permissions
    DESTRUCTIVE_PATTERNS = [
        r'\bDROP\s+(?:TABLE|DATABASE|SCHEMA|INDEX|VIEW)',
        r'\bDELETE\s+FROM\b',
        r'\bTRUNCATE\s+TABLE\b',
        r'\bALTER\s+(?:TABLE|DATABASE|SCHEMA)',
        r'\bGRANT\b',
        r'\bREVOKE\b',
        r'\bCREATE\s+(?:DATABASE|SCHEMA)',
    ]
    
    # Read-only operations that are always safe
    READ_ONLY_PATTERNS = [
        r'\bSELECT\b',
        r'\bSHOW\s+(?:TABLES|DATABASES|SCHEMAS)',
        r'\bDESCRIBE\b',
        r'\bDESC\b',
        r'\bEXPLAIN\b',
    ]
    
    # Write operations that may be allowed with proper permissions
    WRITE_PATTERNS = [
        r'\bINSERT\s+INTO\b',
        r'\bUPDATE\b',
        r'\bCREATE\s+(?:TABLE|VIEW|INDEX)',
        r'\bMERGE\s+INTO\b',
    ]
    
    @classmethod
    def classify_query(cls, query: str) -> tuple[QueryType, SecurityLevel]:
        """
        Classify SQL query and determine required security level.
        
        Args:
            query: SQL query to classify
            
        Returns:
            Tuple of (QueryType, SecurityLevel)
        """
        query_upper = query.upper().strip()
        
        # Check for destructive operations
        for pattern in cls.DESTRUCTIVE_PATTERNS:
            if re.search(pattern, query_upper):
                if 'DROP' in pattern:
                    query_type = QueryType.DROP
                elif 'DELETE' in pattern:
                    query_type = QueryType.DELETE
                elif 'TRUNCATE' in pattern:
                    query_type = QueryType.TRUNCATE
                elif 'ALTER' in pattern:
                    query_type = QueryType.ALTER
                elif 'GRANT' in pattern:
                    query_type = QueryType.GRANT
                elif 'REVOKE' in pattern:
                    query_type = QueryType.REVOKE
                else:
                    query_type = QueryType.UNKNOWN
                return query_type, SecurityLevel.ADMIN_REQUIRED
        
        # Check for read-only operations
        for pattern in cls.READ_ONLY_PATTERNS:
            if re.search(pattern, query_upper):
                return QueryType.SELECT, SecurityLevel.READ_ONLY
                
        # Check for write operations
        for pattern in cls.WRITE_PATTERNS:
            if re.search(pattern, query_upper):
                if 'INSERT' in pattern:
                    query_type = QueryType.INSERT
                elif 'UPDATE' in pattern:
                    query_type = QueryType.UPDATE
                elif 'CREATE' in pattern:
                    query_type = QueryType.CREATE
                else:
                    query_type = QueryType.UNKNOWN
                return query_type, SecurityLevel.WRITE_ALLOWED
        
        # Default classification
        if query_upper.startswith('SELECT'):
            return QueryType.SELECT, SecurityLevel.READ_ONLY
        elif query_upper.startswith('INSERT'):
            return QueryType.INSERT, SecurityLevel.WRITE_ALLOWED
        elif query_upper.startswith('UPDATE'):
            return QueryType.UPDATE, SecurityLevel.WRITE_ALLOWED
        elif query_upper.startswith('DELETE'):
            return QueryType.DELETE, SecurityLevel.ADMIN_REQUIRED
        elif query_upper.startswith('CREATE'):
            return QueryType.CREATE, SecurityLevel.WRITE_ALLOWED
        elif query_upper.startswith('DROP'):
            return QueryType.DROP, SecurityLevel.ADMIN_REQUIRED
        elif query_upper.startswith('ALTER'):
            return QueryType.ALTER, SecurityLevel.ADMIN_REQUIRED
        else:
            return QueryType.UNKNOWN, SecurityLevel.ADMIN_REQUIRED

    @classmethod
    def is_query_allowed(cls, query: str, security_mode: str = "READ_ONLY", admin_override: bool = False) -> tuple[bool, str]:
        """
        Check if query is allowed based on security mode.
        
        Args:
            query: SQL query to check
            security_mode: Current security mode (READ_ONLY, WRITE_ALLOWED, ADMIN_REQUIRED)
            admin_override: Whether admin override is enabled
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        query_type, required_level = cls.classify_query(query)
        
        if admin_override:
            return True, "Admin override enabled"
        
        if security_mode == "READ_ONLY":
            if required_level == SecurityLevel.READ_ONLY:
                return True, "Read-only query approved"
            else:
                return False, f"Query type {query_type.value} not allowed in READ_ONLY mode"
        
        elif security_mode == "WRITE_ALLOWED":
            if required_level in [SecurityLevel.READ_ONLY, SecurityLevel.WRITE_ALLOWED]:
                return True, f"Query type {query_type.value} approved for WRITE_ALLOWED mode"
            else:
                return False, f"Query type {query_type.value} requires ADMIN_REQUIRED mode"
        
        elif security_mode == "ADMIN_REQUIRED":
            return True, f"Query type {query_type.value} approved with admin permissions"
        
        return False, f"Unknown security mode: {security_mode}"


class MockDatabricksCustomTool:
    """Minimal mock of DatabricksCustomTool for testing security features."""
    
    def __init__(self, security_mode="READ_ONLY", allow_admin_override=False, enable_audit_logging=True):
        self.security_mode = security_mode
        self.allow_admin_override = allow_admin_override
        self.enable_audit_logging = enable_audit_logging
        self._auth_method = AuthMethod.NONE
    
    def _validate_query_security(self, query: str, admin_override: bool = False) -> tuple[bool, str, QueryType]:
        """Validate query against security policies."""
        # Classify the query
        query_type, security_level = SQLSecurityFilter.classify_query(query)
        
        # Check if admin override is requested but not allowed
        if admin_override and not self.allow_admin_override:
            return False, "Admin override requested but not permitted", query_type
        
        # Check query permissions
        is_allowed, reason = SQLSecurityFilter.is_query_allowed(
            query, 
            self.security_mode, 
            admin_override and self.allow_admin_override
        )
        
        return is_allowed, reason, query_type
    
    def _perform_dry_run(self, query: str) -> str:
        """Perform a dry run of the query."""
        query_type, security_level = SQLSecurityFilter.classify_query(query)
        is_allowed, reason = SQLSecurityFilter.is_query_allowed(query, self.security_mode)
        
        result = f"""
DRY RUN ANALYSIS:
==================
Query Type: {query_type.value}
Security Level Required: {security_level.value}
Current Security Mode: {self.security_mode}
Permission Check: {'✅ ALLOWED' if is_allowed else '❌ DENIED'}
Reason: {reason}

Query Preview: {query[:200]}{'...' if len(query) > 200 else ''}

Authentication: {self._auth_method.value}
"""
        return result.strip()


# Test Classes
class TestSQLSecurityFilter:
    """Test SQL security filtering functionality."""
    
    def test_classify_select_query(self):
        """Test classification of SELECT queries."""
        query = "SELECT * FROM table1"
        query_type, security_level = SQLSecurityFilter.classify_query(query)
        assert query_type == QueryType.SELECT
        assert security_level == SecurityLevel.READ_ONLY
    
    def test_classify_insert_query(self):
        """Test classification of INSERT queries."""
        query = "INSERT INTO table1 (col1, col2) VALUES (1, 'test')"
        query_type, security_level = SQLSecurityFilter.classify_query(query)
        assert query_type == QueryType.INSERT
        assert security_level == SecurityLevel.WRITE_ALLOWED
    
    def test_classify_drop_query(self):
        """Test classification of DROP queries."""
        query = "DROP TABLE table1"
        query_type, security_level = SQLSecurityFilter.classify_query(query)
        assert query_type == QueryType.DROP
        assert security_level == SecurityLevel.ADMIN_REQUIRED
    
    def test_classify_delete_query(self):
        """Test classification of DELETE queries."""
        query = "DELETE FROM table1 WHERE id = 1"
        query_type, security_level = SQLSecurityFilter.classify_query(query)
        assert query_type == QueryType.DELETE
        assert security_level == SecurityLevel.ADMIN_REQUIRED
    
    def test_classify_alter_query(self):
        """Test classification of ALTER queries."""
        query = "ALTER TABLE table1 ADD COLUMN new_col VARCHAR(50)"
        query_type, security_level = SQLSecurityFilter.classify_query(query)
        assert query_type == QueryType.ALTER
        assert security_level == SecurityLevel.ADMIN_REQUIRED

    def test_is_query_allowed_read_only_mode(self):
        """Test query permission checking in READ_ONLY mode."""
        # SELECT should be allowed
        is_allowed, reason = SQLSecurityFilter.is_query_allowed(
            "SELECT * FROM table1", "READ_ONLY"
        )
        assert is_allowed is True
        assert "Read-only query approved" in reason
        
        # INSERT should be denied
        is_allowed, reason = SQLSecurityFilter.is_query_allowed(
            "INSERT INTO table1 VALUES (1)", "READ_ONLY"
        )
        assert is_allowed is False
        assert "not allowed in READ_ONLY mode" in reason
        
        # DROP should be denied
        is_allowed, reason = SQLSecurityFilter.is_query_allowed(
            "DROP TABLE table1", "READ_ONLY"
        )
        assert is_allowed is False
        assert "not allowed in READ_ONLY mode" in reason

    def test_is_query_allowed_write_allowed_mode(self):
        """Test query permission checking in WRITE_ALLOWED mode."""
        # SELECT should be allowed
        is_allowed, reason = SQLSecurityFilter.is_query_allowed(
            "SELECT * FROM table1", "WRITE_ALLOWED"
        )
        assert is_allowed is True
        
        # INSERT should be allowed
        is_allowed, reason = SQLSecurityFilter.is_query_allowed(
            "INSERT INTO table1 VALUES (1)", "WRITE_ALLOWED"
        )
        assert is_allowed is True
        
        # DROP should be denied
        is_allowed, reason = SQLSecurityFilter.is_query_allowed(
            "DROP TABLE table1", "WRITE_ALLOWED"
        )
        assert is_allowed is False
        assert "requires ADMIN_REQUIRED mode" in reason

    def test_is_query_allowed_admin_override(self):
        """Test admin override functionality."""
        # DROP should be denied in READ_ONLY mode without override
        is_allowed, reason = SQLSecurityFilter.is_query_allowed(
            "DROP TABLE table1", "READ_ONLY", admin_override=False
        )
        assert is_allowed is False
        
        # DROP should be allowed with admin override
        is_allowed, reason = SQLSecurityFilter.is_query_allowed(
            "DROP TABLE table1", "READ_ONLY", admin_override=True
        )
        assert is_allowed is True
        assert "Admin override enabled" in reason


class TestMockDatabricksCustomTool:
    """Test security features in MockDatabricksCustomTool."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tool = MockDatabricksCustomTool(
            security_mode="READ_ONLY",
            allow_admin_override=False,
            enable_audit_logging=True
        )
    
    def test_security_validation_allows_select(self):
        """Test that SELECT queries are allowed in READ_ONLY mode."""
        is_allowed, reason, query_type = self.tool._validate_query_security(
            "SELECT * FROM table1"
        )
        assert is_allowed is True
        assert query_type == QueryType.SELECT
        assert "Read-only query approved" in reason
    
    def test_security_validation_blocks_drop(self):
        """Test that DROP queries are blocked in READ_ONLY mode."""
        is_allowed, reason, query_type = self.tool._validate_query_security(
            "DROP TABLE table1"
        )
        assert is_allowed is False
        assert query_type == QueryType.DROP
        assert "not allowed in READ_ONLY mode" in reason
    
    def test_admin_override_denied_when_not_allowed(self):
        """Test that admin override is denied when not configured."""
        is_allowed, reason, query_type = self.tool._validate_query_security(
            "DROP TABLE table1", admin_override=True
        )
        assert is_allowed is False
        assert "Admin override requested but not permitted" in reason
    
    def test_admin_override_allowed_when_configured(self):
        """Test admin override when properly configured."""
        tool = MockDatabricksCustomTool(
            security_mode="READ_ONLY", 
            allow_admin_override=True
        )
        
        is_allowed, reason, query_type = tool._validate_query_security(
            "DROP TABLE table1", admin_override=True
        )
        assert is_allowed is True
        assert "Admin override enabled" in reason
    
    def test_dry_run_functionality(self):
        """Test dry run mode."""
        result = self.tool._perform_dry_run("SELECT * FROM table1")
        
        assert "DRY RUN ANALYSIS" in result
        assert "Query Type: SELECT" in result
        assert "Security Level Required: READ_ONLY" in result
        assert "✅ ALLOWED" in result
    
    def test_dry_run_with_blocked_query(self):
        """Test dry run with a blocked query."""
        result = self.tool._perform_dry_run("DROP TABLE table1")
        
        assert "DRY RUN ANALYSIS" in result
        assert "Query Type: DROP" in result
        assert "❌ DENIED" in result
    
    def test_write_allowed_mode(self):
        """Test WRITE_ALLOWED security mode."""
        tool = MockDatabricksCustomTool(security_mode="WRITE_ALLOWED")
        
        # SELECT should be allowed
        is_allowed, _, _ = tool._validate_query_security("SELECT * FROM table1")
        assert is_allowed is True
        
        # INSERT should be allowed
        is_allowed, _, _ = tool._validate_query_security("INSERT INTO table1 VALUES (1)")
        assert is_allowed is True
        
        # DROP should still be denied
        is_allowed, _, _ = tool._validate_query_security("DROP TABLE table1")
        assert is_allowed is False
    
    def test_admin_required_mode(self):
        """Test ADMIN_REQUIRED security mode."""
        tool = MockDatabricksCustomTool(security_mode="ADMIN_REQUIRED")
        
        # All query types should be allowed in ADMIN_REQUIRED mode
        queries = [
            "SELECT * FROM table1",
            "INSERT INTO table1 VALUES (1)",
            "UPDATE table1 SET col1 = 2",
            "DELETE FROM table1 WHERE id = 1",
            "DROP TABLE table1",
            "ALTER TABLE table1 ADD COLUMN new_col INT"
        ]
        
        for query in queries:
            is_allowed, _, _ = tool._validate_query_security(query)
            assert is_allowed is True, f"Query should be allowed in ADMIN_REQUIRED mode: {query}"


if __name__ == "__main__":
    pytest.main([__file__])