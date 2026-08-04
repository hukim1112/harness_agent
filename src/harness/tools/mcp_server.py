# -*- coding: utf-8 -*-
"""
===============================================================================
[Harness Module 03-MCP Server] Lightweight SQLite MCP Server
-------------------------------------------------------------------------------
Uses fastmcp package to define standard SQLite discovery & invocation tools.
Can be executed as a stdio server for client integrations.
===============================================================================
"""

import os
import sqlite3
from fastmcp import FastMCP

mcp = FastMCP("SQLite Local Server")
DB_PATH = "mcp_test.db"


def init_db():
    # Initialize a dummy table in the test database for demonstration
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE
        )
    """)
    # Insert mock data if empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
            INSERT INTO users (name, email) VALUES (?, ?)
        """, [
            ("Alice", "alice@example.com"),
            ("Bob", "bob@example.com"),
            ("Charlie", "charlie@example.com")
        ])
    conn.commit()
    conn.close()


@mcp.tool()
def sqlite_list_tables() -> str:
    """Lists all tables present in the local SQLite database for schema discovery."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return f"Tables in SQLite: {tables}"
    except Exception as e:
        return f"Error listing tables: {e}"


@mcp.tool()
def sqlite_query_db(sql_query: str) -> str:
    """Executes a readonly SQL SELECT query on the SQLite database and returns rows as text.
    
    Args:
        sql_query: A valid SQL SELECT query statement.
    """
    if not sql_query.strip().lower().startswith("select"):
        return "Error: Only readonly SELECT queries are permitted for safety."
        
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        colnames = [desc[0] for desc in cursor.description]
        conn.close()
        
        # Format table format
        result = [f"Columns: {colnames}"]
        for row in rows:
            result.append(str(row))
        return "\n".join(result)
    except Exception as e:
        return f"Error executing query: {e}"


if __name__ == "__main__":
    init_db()
    mcp.run()
