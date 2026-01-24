"""
Integration tests for query execution.
These tests run after cluster tests (depend on existing cluster).

Test order:
1. test_01_insert_test_data - Insert sample data
2. test_02_find_query - Execute find queries
3. test_03_insert_document - Insert a single document
4. test_04_read_concerns - Test different read concerns
5. test_05_write_concerns - Test different write concerns
"""
import pytest
import httpx
import logging

from .conftest import TEST_REPLICA_SET, wait_for_condition

logger = logging.getLogger(__name__)


class TestQueryOperations:
    """Test query execution against the replica set."""
    
    @pytest.fixture(autouse=True)
    def setup(self, http_client):
        """Store HTTP client."""
        self.client = http_client
    
    def test_01_insert_test_data(self):
        """Test: Insert test data into the cluster."""
        logger.info("Inserting test data...")
        
        response = self.client.post(
            "/api/queries/test-data",
            params={"replica_set_name": TEST_REPLICA_SET}
        )
        
        assert response.status_code == 200, f"Insert test data failed: {response.text}"
        data = response.json()
        assert data.get("success") is True or "inserted" in str(data).lower()
        
        logger.info("Test data inserted successfully")
    
    def test_02_find_query(self):
        """Test: Execute a find query."""
        logger.info("Executing find query...")
        
        response = self.client.post("/api/queries/execute", json={
            "replica_set_name": TEST_REPLICA_SET,
            "database": "testdb",
            "collection": "testcol",
            "operation": "find",
            "filter": {},
            "limit": 10,
            "read_concern": "local",
            "read_preference": "primary"
        })
        
        assert response.status_code == 200, f"Find query failed: {response.text}"
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert len(data["data"]) > 0, "No documents found"
        
        logger.info(f"Find query returned {len(data['data'])} documents")
    
    def test_03_insert_document(self):
        """Test: Insert a single document."""
        logger.info("Inserting a single document...")
        
        response = self.client.post("/api/queries/execute", json={
            "replica_set_name": TEST_REPLICA_SET,
            "database": "testdb",
            "collection": "testcol",
            "operation": "insertOne",
            "document": {
                "name": "Integration Test",
                "value": 42,
                "test": True
            },
            "write_concern": "majority"
        })
        
        assert response.status_code == 200, f"Insert failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        
        logger.info("Document inserted with majority write concern")
    
    def test_04_find_inserted_document(self):
        """Test: Find the document we just inserted."""
        logger.info("Finding inserted document...")
        
        response = self.client.post("/api/queries/execute", json={
            "replica_set_name": TEST_REPLICA_SET,
            "database": "testdb",
            "collection": "testcol",
            "operation": "find",
            "filter": {"name": "Integration Test"},
            "read_concern": "majority"
        })
        
        assert response.status_code == 200, f"Find failed: {response.text}"
        data = response.json()
        
        assert data["success"] is True
        assert len(data["data"]) >= 1, "Inserted document not found"
        assert data["data"][0]["value"] == 42
        
        logger.info("Inserted document verified with majority read concern")
    
    def test_05_count_documents(self):
        """Test: Count documents in collection."""
        logger.info("Counting documents...")
        
        response = self.client.post("/api/queries/execute", json={
            "replica_set_name": TEST_REPLICA_SET,
            "database": "testdb",
            "collection": "testcol",
            "operation": "count",
            "filter": {}
        })
        
        assert response.status_code == 200, f"Count failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        
        logger.info(f"Collection has {data.get('data', 'N/A')} documents")
    
    def test_06_query_with_read_preference(self):
        """Test: Query with secondary read preference."""
        logger.info("Testing secondary read preference...")
        
        response = self.client.post("/api/queries/execute", json={
            "replica_set_name": TEST_REPLICA_SET,
            "database": "testdb",
            "collection": "testcol",
            "operation": "find",
            "filter": {},
            "limit": 5,
            "read_concern": "local",
            "read_preference": "secondary"
        })
        
        assert response.status_code == 200, f"Query failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        
        logger.info("Secondary read preference query succeeded")
    
    def test_07_query_history(self):
        """Test: Check query history."""
        logger.info("Checking query history...")
        
        response = self.client.get("/api/queries/history")
        
        assert response.status_code == 200, f"History failed: {response.text}"
        data = response.json()
        
        assert len(data) > 0, "Query history is empty"
        logger.info(f"Query history has {len(data)} entries")
