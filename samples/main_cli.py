"""
===============================================================================
[CLI Application] Main CLI Terminal Agent Runner
-------------------------------------------------------------------------------
Reference Sources & Grounding Traceability:
- Claude Code Source: c:/Users/hyoun/Desktop/github/Agent_reference/superview.sh-claude-code/src/cli.ts
- Hermes Agent Source: c:/Users/hyoun/Desktop/github/Agent_reference/hermes-agent/cli.py & run_agent.py
- Architecture Notes: h:/내 드라이브/work_memory/contexts/강의/handson/10_하네스_프로덕션_에이전트/references/ref_01_reasoning/architecture_notes.md
===============================================================================
"""

import sys
import os
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from harness.reasoning.naive_agent import build_naive_agent

console = Console()

def main():
    console.print(Panel.fit(
        "[bold green]🛡️ Production Agent Harness Lab - CLI Interactive Runner[/bold green]\n"
        "[dim]Harness Engineering 01-03 Activated (LangChain & LangGraph)[/dim]",
        border_style="cyan"
    ))

    agent = build_naive_agent()
    chat_history = []

    while True:
        try:
            user_input = Prompt.ask("\n[bold yellow]User[/bold yellow]")
            if user_input.lower() in ["exit", "quit", "q"]:
                console.print("[bold red]Exiting Agent Harness CLI. Goodbye![/bold red]")
                break
                
            with console.status("[bold cyan]Agent Thinking & Executing Harness...[/bold cyan]"):
                res = agent.invoke({"input": user_input, "chat_history": chat_history})
                output = res.get("output", "")
                
            console.print(Panel(output, title="[bold green]Agent Response[/bold green]", border_style="green"))
            chat_history.append({"role": "user", "content": user_input})
            chat_history.append({"role": "assistant", "content": output})
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[bold red]Error caught in Harness CLI: {e}[/bold red]")

if __name__ == "__main__":
    main()
