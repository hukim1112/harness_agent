"""
===============================================================================
[Harness Module 03-3] Claude Code Production-Grade 8 Essential Tool Category Engine
===============================================================================
"""

import os
import sys
import re
import glob
import json
import time
import subprocess
import urllib.request
import urllib.parse
from html.parser import HTMLParser
from typing import List, Dict, Any, Optional, Tuple
from langchain_core.tools import tool
from pydantic import BaseModel, Field

# =============================================================================
# Category 1: File Operations (FileRead, FileEdit, FileWriter, NotebookEdit)
# =============================================================================
@tool
def file_read(file_path: str, offset: int = 1, limit: int = 250, show_line_numbers: bool = True) -> str:
    """
    Reads lines from a file on the local filesystem with optional line numbers and pagination.
    Maps directly to Claude Code's FileReadTool.
    """
    abs_path = os.path.abspath(os.path.expanduser(file_path))
    if not os.path.exists(abs_path):
        return f"FileRead Error: File '{file_path}' (resolved to '{abs_path}') does not exist."
    if os.path.isdir(abs_path):
        return f"FileRead Error: Path '{file_path}' is a directory, not a file."

    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            
        total_lines = len(lines)
        start_idx = max(0, offset - 1)
        end_idx = min(total_lines, start_idx + limit)
        
        sliced_lines = lines[start_idx:end_idx]
        output_lines = []
        
        for idx, line in enumerate(sliced_lines, start=start_idx + 1):
            if show_line_numbers:
                output_lines.append(f"{idx:6d} | {line}")
            else:
                output_lines.append(line)
                
        content = "".join(output_lines)
        header = f"[File: {abs_path} (Lines {start_idx+1}-{end_idx} of {total_lines})]\n"
        return header + content
        
    except Exception as e:
        return f"FileRead Error: Failed to read file '{file_path}': {str(e)}"


@tool
def file_edit(file_path: str, target_content: str, replacement_content: str) -> str:
    """
    Replaces an exact matching block of text in a file with replacement_content.
    Maps directly to Claude Code's FileEditTool (exact string matching & atomic file write).
    """
    abs_path = os.path.abspath(os.path.expanduser(file_path))
    if not os.path.exists(abs_path):
        return f"FileEdit Error: Target file '{file_path}' does not exist."

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()

        if target_content not in content:
            preview = content[:200] + "..." if len(content) > 200 else content
            return (
                f"FileEdit Error: Exact target_content match not found in '{file_path}'.\n"
                f"File preview:\n{preview}"
            )

        match_count = content.count(target_content)
        if match_count > 1:
            return f"FileEdit Error: target_content matches {match_count} locations in '{file_path}'. Provide a unique block."

        new_content = content.replace(target_content, replacement_content, 1)

        # Atomic Write
        temp_path = abs_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        os.replace(temp_path, abs_path)

        return f"SUCCESS: File '{abs_path}' edited successfully (replaced {len(target_content)} bytes with {len(replacement_content)} bytes)."

    except Exception as e:
        return f"FileEdit Error: Failed to edit '{file_path}': {str(e)}"


@tool
def file_writer(file_path: str, content: str, overwrite: bool = True) -> str:
    """
    Creates a new file or overwrites an existing file with content.
    Maps directly to Claude Code's FileWriteTool.
    """
    abs_path = os.path.abspath(os.path.expanduser(file_path))
    if os.path.exists(abs_path) and not overwrite:
        return f"FileWrite Error: File '{file_path}' already exists and overwrite=False."

    try:
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"SUCCESS: Written {len(content)} characters to '{abs_path}'."
    except Exception as e:
        return f"FileWrite Error: Failed to write to '{file_path}': {str(e)}"


@tool
def notebook_edit(notebook_path: str, cell_index: int, new_code: str) -> str:
    """
    Edits a specific cell inside a Jupyter Notebook (.ipynb).
    Maps to Claude Code's NotebookEditTool.
    """
    abs_path = os.path.abspath(os.path.expanduser(notebook_path))
    if not os.path.exists(abs_path):
        return f"NotebookEdit Error: Notebook '{notebook_path}' does not exist."

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            nb_data = json.load(f)

        cells = nb_data.get("cells", [])
        if cell_index < 0 or cell_index >= len(cells):
            return f"NotebookEdit Error: Cell index {cell_index} out of bounds (Notebook has {len(cells)} cells)."

        cells[cell_index]["source"] = new_code.splitlines(keepends=True)

        with open(abs_path, "w", encoding="utf-8") as f:
            json.dump(nb_data, f, indent=2, ensure_ascii=False)

        return f"SUCCESS: Cell #{cell_index} in notebook '{abs_path}' updated successfully."
    except Exception as e:
        return f"NotebookEdit Error: Failed to edit notebook '{notebook_path}': {str(e)}"


# =============================================================================
# Category 2: Shell (Bash)
# =============================================================================
@tool
def bash_command(command: str, timeout_seconds: int = 30, max_stdout_length: int = 4000) -> str:
    """
    Executes a real shell command on local system, capturing stdout, stderr, and exit code.
    Maps directly to Claude Code's BashTool.

    Args:
        command: The shell command to run.
        timeout_seconds: Subprocess execution timeout in seconds. Defaults to 30.
        max_stdout_length: Maximum stdout character length to return to prevent prompt bloat. Defaults to 4000. Can be set up to 50000 for large outputs.
    """
    stdout_limit = min(50000, max(100, max_stdout_length))
    
    try:
        start_time = time.time()
        process = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=os.getcwd()
        )
        duration = round(time.time() - start_time, 2)
        
        stdout_clean = process.stdout.strip()
        stderr_clean = process.stderr.strip()
        
        result_parts = [
            f"[Command: '{command}']",
            f"[Exit Code: {process.returncode} | Execution Time: {duration}s]"
        ]
        
        if stdout_clean:
            if len(stdout_clean) > stdout_limit:
                stdout_clean = stdout_clean[:stdout_limit] + f"\n... [STDOUT TRUNCATED {len(stdout_clean)-stdout_limit} bytes]"
            result_parts.append(f"--- STDOUT ---\n{stdout_clean}")
            
        if stderr_clean:
            if len(stderr_clean) > 2000:
                stderr_clean = stderr_clean[:2000] + f"\n... [STDERR TRUNCATED {len(stderr_clean)-2000} bytes]"
            result_parts.append(f"--- STDERR ---\n{stderr_clean}")
            
        if not stdout_clean and not stderr_clean:
            result_parts.append("(Command executed silently with no output)")

        return "\n".join(result_parts)

    except subprocess.TimeoutExpired:
        return f"Bash Error: Command '{command}' timed out after {timeout_seconds} seconds."
    except Exception as e:
        return f"Bash Error: Failed to execute command '{command}': {str(e)}"


# =============================================================================
# Category 3: Search (Grep, Glob, ToolSearch)
# =============================================================================
VCS_EXCLUDE_DIRS = {".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "env_langchain_123"}

@tool
def grep_search(pattern: str, search_path: str = ".", output_mode: str = "files_with_matches", head_limit: int = 50) -> str:
    """
    Searches file contents using regex matching, ignoring VCS directories.
    Maps directly to Claude Code's GrepTool.
    """
    abs_root = os.path.abspath(os.path.expanduser(search_path))
    if not os.path.exists(abs_root):
        return f"Grep Error: Search path '{search_path}' does not exist."

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except Exception as err:
        return f"Grep Error: Invalid regex pattern '{pattern}': {err}"

    matching_files = []
    content_matches = []
    total_match_count = 0

    if os.path.isfile(abs_root):
        target_files = [abs_root]
    else:
        target_files = []
        for root, dirs, files in os.walk(abs_root):
            dirs[:] = [d for d in dirs if d not in VCS_EXCLUDE_DIRS]
            for f in files:
                target_files.append(os.path.join(root, f))

    for fpath in target_files:
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            rel_path = os.path.relpath(fpath, os.getcwd())
            file_had_match = False
            
            for line_no, line in enumerate(lines, start=1):
                if regex.search(line):
                    file_had_match = True
                    total_match_count += 1
                    if output_mode == "content" and len(content_matches) < head_limit:
                        content_matches.append(f"{rel_path}:{line_no}:{line.strip()}")

            if file_had_match:
                matching_files.append(rel_path)
                if output_mode == "files_with_matches" and len(matching_files) >= head_limit:
                    break
        except Exception:
            continue

    if output_mode == "content":
        if not content_matches:
            return f"No matches found for pattern '{pattern}'."
        return f"Found {total_match_count} matches for '{pattern}':\n" + "\n".join(content_matches)

    elif output_mode == "count":
        return f"Found {total_match_count} total occurrences across {len(matching_files)} files."

    else:
        if not matching_files:
            return f"No files matching pattern '{pattern}'."
        return f"Found {len(matching_files)} matching files:\n" + "\n".join(matching_files[:head_limit])


@tool
def glob_search(pattern: str, search_path: str = ".") -> str:
    """
    Finds files matching a glob wildcard pattern (e.g. '**/*.py').
    Maps to Claude Code's GlobTool.
    """
    abs_root = os.path.abspath(os.path.expanduser(search_path))
    full_pattern = os.path.join(abs_root, pattern)
    
    matches = glob.glob(full_pattern, recursive=True)
    clean_matches = [
        os.path.relpath(m, os.getcwd()) for m in matches 
        if not any(ex in m for ex in VCS_EXCLUDE_DIRS)
    ]
    
    if not clean_matches:
        return f"No files matched glob pattern '{pattern}' in '{search_path}'."
        
    return f"Found {len(clean_matches)} files matching '{pattern}':\n" + "\n".join(clean_matches[:100])


@tool
def tool_search(query: str) -> str:
    """
    Searches registered tools by keyword/capability.
    """
    tools_catalog = {
        "file_read": "Reads file contents with line offset and limit.",
        "file_edit": "Performs exact string matching replacement in local files.",
        "file_writer": "Creates or overwrites files on local disk.",
        "bash_command": "Executes shell commands with timeout and exit codes.",
        "grep_search": "Searches file contents using regex.",
        "glob_search": "Finds files matching glob patterns.",
        "web_fetch": "Fetches and parses text/markdown from web URLs.",
        "web_search": "Performs DuckDuckGo web queries for snippets.",
    }
    
    query_lower = query.lower()
    matched = [f"{tname}: {desc}" for tname, desc in tools_catalog.items() if query_lower in tname.lower() or query_lower in desc.lower()]
    
    if not matched:
        return f"No tools matching query '{query}'. Available tools: {list(tools_catalog.keys())}"
        
    return "Matched Tools:\n" + "\n".join(matched)


# =============================================================================
# Category 4: Web (WebFetch, WebSearch)
# =============================================================================
class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_chunks = []
    def handle_data(self, data):
        cleaned = data.strip()
        if cleaned:
            self.text_chunks.append(cleaned)
    def get_text(self):
        return " ".join(self.text_chunks)


@tool
def web_fetch(url: str) -> str:
    """
    Fetches raw content from an HTTP/HTTPS URL and extracts plain text.
    Maps directly to Claude Code's WebFetchTool.
    """
    try:
        req = urllib.request.Request(
            url, 
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html_bytes = response.read()
            html_text = html_bytes.decode("utf-8", errors="ignore")

        parser = HTMLTextExtractor()
        parser.feed(html_text)
        extracted = parser.get_text()

        if len(extracted) > 4000:
            extracted = extracted[:4000] + f"\n... [WEBFETCH TRUNCATED {len(extracted)-4000} bytes]"

        return f"[Fetched URL: {url}]\n" + extracted

    except Exception as e:
        return f"WebFetch Error: Failed to fetch '{url}': {str(e)}"


@tool
def web_search(query: str) -> str:
    """
    Performs web search to retrieve documentation links and text snippets.
    Uses duckduckgo_search library to bypass captcha verification and get live results.
    """
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            from duckduckgo_search import DDGS
        results = []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            with DDGS() as ddgs:
                search_results = list(ddgs.text(query, max_results=5))
            for idx, r in enumerate(search_results):
                clean_title = r.get("title", "Result").strip()
                clean_snippet = r.get("body", "").strip()
                results.append(f"{idx+1}. [{clean_title}]: {clean_snippet}")

        if not results:
            return f"WebSearch Result for '{query}': No snippets extracted."

        return f"[Web Search Results for '{query}']\n" + "\n".join(results)

    except Exception as e:
        return f"WebSearch Error: Search failed for query '{query}': {str(e)}"
