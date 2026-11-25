#!/usr/bin/env python
from fastmcp import FastMCP

mcp = FastMCP("Data & Math Engine")


@mcp.tool()
def calculate_roi(revenue: float, cost: float) -> str:
    """Calculates Return on Investment (ROI) percentage given revenue and cost."""
    if cost == 0:
        return "Error: Cost cannot be zero."
    roi = ((revenue - cost) / cost) * 100.0
    return f"Calculated ROI: {roi:.2f}% (Revenue: ${revenue:,.2f}, Cost: ${cost:,.2f})"


@mcp.tool()
def query_database(table: str, limit: int = 5) -> str:
    """Queries records from a simulated corporate database table (users, sales, products)."""
    sample_data = {
        "sales": [
            {"quarter": "Q1", "revenue": 1200000, "target_met": True},
            {"quarter": "Q2", "revenue": 1450000, "target_met": True},
            {"quarter": "Q3", "revenue": 1100000, "target_met": False},
            {"quarter": "Q4", "revenue": 1800000, "target_met": True},
        ],
        "users": [
            {"id": 1, "name": "Cheolsu Kim", "role": "Lead Engineer"},
            {"id": 2, "name": "Younghee Lee", "role": "Data Scientist"},
        ],
    }
    records = sample_data.get(table.lower(), [{"info": f"Table '{table}' not found."}])
    return str(records[:limit])


if __name__ == "__main__":
    mcp.run(transport="stdio")
