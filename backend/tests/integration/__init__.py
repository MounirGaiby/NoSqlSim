"""
NoSqlSim Integration Tests

This test suite runs actual MongoDB containers to verify the full functionality
of the NoSqlSim platform. Tests are designed to run in sequence as they depend
on cluster state from previous tests.

Port Range: 27100-27110 (to avoid conflicts with local MongoDB)
"""
