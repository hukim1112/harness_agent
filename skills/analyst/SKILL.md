---
name: analyst
description: Comprehensive data analysis, statistical profiling, charting, professional Excel generation, and interactive HTML reporting skill for AI agents.
license: Apache-2.0
---

# Analyst Agent Skill Hub

This skill provides domain-specific guidelines, code templates, and best practices for data analysis, transformation, visualization, and reporting tasks.

## Skill Structure & Progressive Disclosure

When executing specific analyst subtasks, read the relevant guide on-demand using `file_read`:

| Subtask | Guide File | Key Topics |
|---|---|---|
| **Data Profiling & Pandas Querying** | `skills/analyst/data_analysis.md` | Schema detection, statistical profiling, safe query patterns, aggregations |
| **Data Visualization & Charts** | `skills/analyst/chart_patterns.md` | Chart selection, publication-grade styling, Korean font setup, Plotly/Matplotlib templates |
| **Professional Excel Reports** | `skills/analyst/xlsx_guide.md` | `openpyxl` rules, formula safety, financial modeling color conventions |
| **Interactive HTML Dashboards** | `skills/analyst/design_tokens.md` | Responsive dashboard templates, Chart.js + Mermaid integration, CSS tokens |

## Core Principles

1. **Progressive Disclosure**: Load only the specific guideline needed for the current task.
2. **Formula Over Hardcoding**: In spreadsheets, always emit dynamic formulas (`=SUM()`, `=AVERAGE()`) rather than static Python evaluation values.
3. **Publication Quality**: All visual charts and HTML reports must have curated color palettes, clear labels, and responsive layout.
4. **Resilient Data Ingestion**: Automatically handle diverse formats (JSON, CSV, TSV, Parquet, Excel) with graceful fallback.
