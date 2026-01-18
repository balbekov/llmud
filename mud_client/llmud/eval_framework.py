"""
Evaluation Framework for Agentic MUD AI

This module provides tools for testing AI agent goals against a live MUD.
It tracks success rates, timing, and generates reports.
"""

import asyncio
import logging
import json
from typing import Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .agentic_session import AgenticSession, AgenticSessionConfig

logger = logging.getLogger(__name__)


@dataclass
class EvalResult:
    """Result of a single evaluation run."""
    goal: str
    success: bool
    summary: str
    duration_seconds: float
    commands_sent: int
    tokens_used: int
    rooms_visited: int
    errors: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "success": self.success,
            "summary": self.summary,
            "duration_seconds": self.duration_seconds,
            "commands_sent": self.commands_sent,
            "tokens_used": self.tokens_used,
            "rooms_visited": self.rooms_visited,
            "errors": self.errors,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class EvalSuite:
    """A suite of evaluation tests."""
    name: str
    goals: list[str]
    host: str = "dunemud.net"
    port: int = 6789
    username: str = ""
    password: str = ""
    timeout_per_goal: float = 120.0
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "goals": self.goals,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "timeout_per_goal": self.timeout_per_goal,
        }


@dataclass
class EvalReport:
    """Full evaluation report."""
    suite_name: str
    results: list[EvalResult] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.success) / len(self.results)
    
    @property
    def total_duration(self) -> float:
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return sum(r.duration_seconds for r in self.results)
    
    @property
    def total_tokens(self) -> int:
        return sum(r.tokens_used for r in self.results)
    
    def to_dict(self) -> dict:
        return {
            "suite_name": self.suite_name,
            "success_rate": self.success_rate,
            "total_duration": self.total_duration,
            "total_tokens": self.total_tokens,
            "num_tests": len(self.results),
            "successful_tests": sum(1 for r in self.results if r.success),
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "results": [r.to_dict() for r in self.results],
        }
    
    def save(self, path: str) -> None:
        """Save report to JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def print_summary(self) -> None:
        """Print a summary of the report."""
        print(f"\n{'='*60}")
        print(f"Evaluation Report: {self.suite_name}")
        print(f"{'='*60}")
        print(f"Tests Run: {len(self.results)}")
        print(f"Success Rate: {self.success_rate*100:.1f}%")
        print(f"Total Duration: {self.total_duration:.1f}s")
        print(f"Total Tokens: {self.total_tokens:,}")
        print(f"\nResults:")
        print(f"{'-'*60}")
        
        for i, result in enumerate(self.results, 1):
            status = "✓ PASS" if result.success else "✗ FAIL"
            print(f"{i}. {status} - {result.goal[:50]}...")
            print(f"   Duration: {result.duration_seconds:.1f}s, "
                  f"Commands: {result.commands_sent}, "
                  f"Tokens: {result.tokens_used}")
            if result.errors:
                print(f"   Errors: {result.errors}")
        
        print(f"{'='*60}\n")


class EvalRunner:
    """
    Runs evaluation tests against a live MUD.
    
    Usage:
        runner = EvalRunner(openai_api_key="...")
        report = await runner.run_suite(suite)
        report.print_summary()
    """
    
    def __init__(
        self,
        openai_api_key: str,
        model: str = "gpt-4o",
        verbose: bool = True,
    ):
        self.openai_api_key = openai_api_key
        self.model = model
        self.verbose = verbose
        
        # Setup logging
        if verbose:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
    
    async def run_single_goal(
        self,
        goal: str,
        host: str = "dunemud.net",
        port: int = 6789,
        username: str = "",
        password: str = "",
        timeout: float = 120.0,
    ) -> EvalResult:
        """
        Run a single goal evaluation.
        
        Args:
            goal: The goal to achieve
            host: MUD host
            port: MUD port
            username: Character name
            password: Character password
            timeout: Maximum time in seconds
            
        Returns:
            EvalResult with test outcome
        """
        if self.verbose:
            print(f"\n{'='*40}")
            print(f"Goal: {goal}")
            print(f"{'='*40}")
        
        start_time = datetime.now()
        errors = []
        commands_sent = 0
        tokens_used = 0
        rooms_visited = 0
        
        config = AgenticSessionConfig(
            host=host,
            port=port,
            username=username,
            password=password,
            openai_api_key=self.openai_api_key,
            model=self.model,
            map_enabled=True,
            auto_play=False,
        )
        
        session = AgenticSession(config)
        
        # Event handler for verbose output
        def on_event(event):
            if self.verbose and event.type == "text":
                text = event.data.get("text", "")[:100]
                if text.strip():
                    print(f"MUD: {text}")
            elif self.verbose and event.type == "ai_action":
                print(f"AI: {event.data.get('message', '')}")
        
        session.on_event(on_event)
        
        try:
            # Connect
            if not await session.connect():
                return EvalResult(
                    goal=goal,
                    success=False,
                    summary="Failed to connect to MUD",
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                    commands_sent=0,
                    tokens_used=0,
                    rooms_visited=0,
                    errors=["Connection failed"],
                )
            
            # Login if credentials provided
            if username and password:
                await session.login()
                await asyncio.sleep(3)  # Wait for login
            
            # Start session loop in background
            loop_task = asyncio.create_task(session.run())
            
            # Run the goal
            try:
                result = await asyncio.wait_for(
                    session.run_goal(goal, timeout=timeout),
                    timeout=timeout + 10
                )
            except asyncio.TimeoutError:
                result = {"success": False, "summary": "Timeout"}
                errors.append("Timeout exceeded")
            
            # Gather stats
            if session.agent:
                agent_state = session.agent.get_state_summary()
                commands_sent = agent_state.get("total_commands_sent", 0)
                tokens_used = agent_state.get("total_tokens_used", 0)
            
            if session.map_agent:
                map_stats = session.map_agent.get_map_stats()
                rooms_visited = map_stats.get("total_rooms", 0)
            
            # Cleanup
            session._running = False
            await asyncio.sleep(0.5)
            loop_task.cancel()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return EvalResult(
                goal=goal,
                success=result.get("success", False),
                summary=result.get("summary", "Unknown"),
                duration_seconds=duration,
                commands_sent=commands_sent,
                tokens_used=tokens_used,
                rooms_visited=rooms_visited,
                errors=errors,
            )
        
        except Exception as e:
            logger.error(f"Evaluation error: {e}")
            errors.append(str(e))
            
            return EvalResult(
                goal=goal,
                success=False,
                summary=f"Error: {e}",
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                commands_sent=commands_sent,
                tokens_used=tokens_used,
                rooms_visited=rooms_visited,
                errors=errors,
            )
        
        finally:
            await session.disconnect()
    
    async def run_suite(
        self,
        suite: EvalSuite,
        delay_between_tests: float = 5.0,
    ) -> EvalReport:
        """
        Run a full evaluation suite.
        
        Args:
            suite: The evaluation suite to run
            delay_between_tests: Seconds to wait between tests
            
        Returns:
            EvalReport with all results
        """
        report = EvalReport(suite_name=suite.name)
        
        if self.verbose:
            print(f"\n{'#'*60}")
            print(f"Running Evaluation Suite: {suite.name}")
            print(f"Goals: {len(suite.goals)}")
            print(f"{'#'*60}")
        
        for i, goal in enumerate(suite.goals, 1):
            if self.verbose:
                print(f"\n[{i}/{len(suite.goals)}] Testing goal...")
            
            result = await self.run_single_goal(
                goal=goal,
                host=suite.host,
                port=suite.port,
                username=suite.username,
                password=suite.password,
                timeout=suite.timeout_per_goal,
            )
            
            report.results.append(result)
            
            if self.verbose:
                status = "✓ PASS" if result.success else "✗ FAIL"
                print(f"Result: {status}")
            
            # Delay between tests
            if i < len(suite.goals):
                await asyncio.sleep(delay_between_tests)
        
        report.finished_at = datetime.now()
        return report


# ==================== Pre-defined Test Suites ====================

def create_astroport_navigation_suite(
    username: str = "",
    password: str = "",
) -> EvalSuite:
    """Create a test suite for Astroport navigation."""
    return EvalSuite(
        name="Astroport Navigation",
        goals=[
            "Explore the current room and report what you see.",
            "Move in a complete loop, returning to your starting position.",
            "Find and move to any exit, then return to the starting room.",
            "Explore at least 5 different rooms and report their names.",
        ],
        username=username,
        password=password,
        timeout_per_goal=60.0,
    )


def create_basic_commands_suite(
    username: str = "",
    password: str = "",
) -> EvalSuite:
    """Create a test suite for basic MUD commands."""
    return EvalSuite(
        name="Basic Commands",
        goals=[
            "Look at your current room and report the exits available.",
            "Check your score and report your HP percentage.",
            "Check your inventory and report what items you have.",
            "Look at yourself and describe your character.",
        ],
        username=username,
        password=password,
        timeout_per_goal=30.0,
    )


def create_exploration_suite(
    username: str = "",
    password: str = "",
) -> EvalSuite:
    """Create a test suite for exploration."""
    return EvalSuite(
        name="Exploration",
        goals=[
            "Explore the area until you find a room with 'shop' or 'store' in the name.",
            "Explore and create a mental map, then navigate to a room you've visited before.",
            "Find any NPC and report their name.",
            "Explore until you find a room with at least 4 exits.",
        ],
        username=username,
        password=password,
        timeout_per_goal=120.0,
    )


# ==================== Command-line Interface ====================

async def main():
    """Command-line interface for running evaluations."""
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description="Run MUD AI evaluations")
    parser.add_argument("--api-key", help="OpenAI API key", default=os.getenv("OPENAI_API_KEY"))
    parser.add_argument("--model", help="Model to use", default="gpt-4o")
    parser.add_argument("--host", help="MUD host", default="dunemud.net")
    parser.add_argument("--port", help="MUD port", type=int, default=6789)
    parser.add_argument("--username", help="Character name", default="")
    parser.add_argument("--password", help="Character password", default="")
    parser.add_argument("--suite", help="Suite to run", 
                       choices=["astroport", "basic", "exploration", "custom"])
    parser.add_argument("--goal", help="Single goal to test")
    parser.add_argument("--timeout", help="Timeout per goal", type=float, default=120.0)
    parser.add_argument("--output", help="Output file for report")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if not args.api_key:
        print("Error: OpenAI API key required (--api-key or OPENAI_API_KEY env var)")
        return
    
    runner = EvalRunner(
        openai_api_key=args.api_key,
        model=args.model,
        verbose=args.verbose,
    )
    
    if args.goal:
        # Single goal test
        result = await runner.run_single_goal(
            goal=args.goal,
            host=args.host,
            port=args.port,
            username=args.username,
            password=args.password,
            timeout=args.timeout,
        )
        print(f"\nResult: {'PASS' if result.success else 'FAIL'}")
        print(f"Summary: {result.summary}")
        print(f"Duration: {result.duration_seconds:.1f}s")
        print(f"Commands: {result.commands_sent}")
        print(f"Tokens: {result.tokens_used}")
    
    elif args.suite:
        # Run a suite
        if args.suite == "astroport":
            suite = create_astroport_navigation_suite(args.username, args.password)
        elif args.suite == "basic":
            suite = create_basic_commands_suite(args.username, args.password)
        elif args.suite == "exploration":
            suite = create_exploration_suite(args.username, args.password)
        else:
            print("Custom suite not implemented - use --goal for single tests")
            return
        
        suite.host = args.host
        suite.port = args.port
        suite.timeout_per_goal = args.timeout
        
        report = await runner.run_suite(suite)
        report.print_summary()
        
        if args.output:
            report.save(args.output)
            print(f"Report saved to {args.output}")
    
    else:
        print("Please specify --goal or --suite")


if __name__ == "__main__":
    asyncio.run(main())
