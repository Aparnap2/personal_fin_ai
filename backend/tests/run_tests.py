"""
Test Runner for Personal Finance AI

Runs all tests:
1. Unit tests (parser, categorizer, forecaster, alerter)
2. Integration tests (with Ollama)
3. E2E tests (API + Frontend)
4. Load tests (optional)

Usage:
    python tests/run_tests.py --unit          # Unit tests only
    python tests/run_tests.py --integration   # Integration with Ollama
    python tests/run_tests.py --e2e           # End-to-end tests
    python tests/run_tests.py --load          # Load tests
    python tests/run_tests.py --all           # All tests
    python tests/run_tests.py --report        # Generate HTML report
"""
import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
REPORTS_DIR = PROJECT_ROOT / "test_reports"

# Test results
TEST_RESULTS = {}


class TestRunner:
    """Test runner with reporting."""

    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "tests": {},
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "duration_seconds": 0,
            },
        }

    def log_section(self, title: str):
        """Log a section header."""
        separator = "=" * 60
        logger.info(f"\n{separator}")
        logger.info(f"  {title}")
        logger.info(f"{separator}\n")

    def run_command(
        self,
        cmd: list[str],
        cwd: Path,
        description: str,
        timeout: int = 300,
    ) -> tuple[int, str, str]:
        """Run a command and return exit code, stdout, stderr."""
        logger.info(f"Running: {description}")
        logger.info(f"Command: {' '.join(cmd)}")

        start = time.time()
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.time() - start

        logger.info(f"Completed in {elapsed:.2f}s with exit code {result.returncode}")

        if result.stdout:
            for line in result.stdout.strip().split('\n')[-20:]:  # Last 20 lines
                logger.info(f"  {line}")

        return result.returncode, result.stdout, result.stderr

    def run_unit_tests(self, integration: bool = False) -> dict:
        """Run unit tests."""
        self.log_section("UNIT TESTS")

        results = {"passed": 0, "failed": 0, "skipped": 0, "tests": []}

        # Install test dependencies
        cmd = [
            sys.executable, "-m", "pip", "install",
            "pytest", "pytest-asyncio", "pytest-cov",
            "httpx", "prophet", "litellm",
        ]
        self.run_command(cmd, BACKEND_DIR, "Installing test dependencies")

        # Run pytest
        pytest_args = [
            "-m", "not ollama" if not integration else "",
            "-v", "--tb=short",
            "--junitxml", str(REPORTS_DIR / "unit_tests.xml"),
            "--cov", str(BACKEND_DIR / "app"),
            "--cov-report", "term-missing",
            "--cov-report", "json:" + str(REPORTS_DIR / "coverage.json"),
        ]

        # Remove empty strings from args
        pytest_args = [a for a in pytest_args if a]

        cmd = [sys.executable, "-m", "pytest", str(BACKEND_DIR / "tests" / "unit")] + pytest_args
        exit_code, stdout, stderr = self.run_command(
            cmd, BACKEND_DIR, "Running unit tests"
        )

        # Parse results
        results["exit_code"] = exit_code
        results["duration"] = time.time() - self.start_time

        # Count results
        if "passed" in stdout:
            for line in stdout.split('\n'):
                if "passed" in line or "failed" in line or "error" in line:
                    logger.info(f"  {line}")

        self.results["tests"]["unit"] = results
        return results

    def run_integration_tests(self) -> dict:
        """Run integration tests with Ollama."""
        self.log_section("INTEGRATION TESTS (OLLAMA)")

        results = {"passed": 0, "failed": 0, "skipped": 0, "tests": []}

        # Check Ollama availability
        cmd = ["curl", "-s", "http://localhost:11434/api/tags"]
        exit_code, stdout, stderr = self.run_command(
            cmd, PROJECT_ROOT, "Checking Ollama availability"
        )

        if exit_code != 0:
            logger.warning("Ollama not available, skipping integration tests")
            results["skipped"] = 5
            self.results["tests"]["integration"] = results
            return results

        # Run Ollama tests
        pytest_args = [
            "-m", "ollama",
            "-v", "--tb=short",
            "--junitxml", str(REPORTS_DIR / "integration_tests.xml"),
        ]

        cmd = [
            sys.executable, "-m", "pytest",
            str(BACKEND_DIR / "tests" / "unit" / "test_categorizer.py"),
        ] + pytest_args

        exit_code, stdout, stderr = self.run_command(
            cmd, BACKEND_DIR, "Running integration tests"
        )

        results["exit_code"] = exit_code
        self.results["tests"]["integration"] = results
        return results

    def run_e2e_tests(self) -> dict:
        """Run E2E tests."""
        self.log_section("E2E TESTS")

        results = {"passed": 0, "failed": 0, "skipped": 0, "tests": []}

        # Install Playwright
        cmd = [
            sys.executable, "-m", "pip", "install",
            "playwright", "pytest-playwright",
        ]
        self.run_command(cmd, BACKEND_DIR, "Installing Playwright")

        # Install browser
        cmd = ["python", "-m", "playwright", "install", "chromium"]
        self.run_command(cmd, BACKEND_DIR, "Installing Chromium")

        # Run E2E tests
        pytest_args = [
            "-v", "--tb=short",
            "--junitxml", str(REPORTS_DIR / "e2e_tests.xml"),
        ]

        cmd = [
            sys.executable, "-m", "pytest",
            str(BACKEND_DIR / "tests" / "e2e"),
        ] + pytest_args

        exit_code, stdout, stderr = self.run_command(
            cmd, BACKEND_DIR, "Running E2E tests", timeout=600
        )

        results["exit_code"] = exit_code
        self.results["tests"]["e2e"] = results
        return results

    def run_load_tests(self) -> dict:
        """Run load tests."""
        self.log_section("LOAD TESTS")

        results = {"passed": 0, "failed": 0, "skipped": 0, "tests": []}

        # Install locust
        cmd = [sys.executable, "-m", "pip", "install", "locust"]
        self.run_command(cmd, BACKEND_DIR, "Installing Locust")

        # Run quick load test (30 seconds, 5 users)
        cmd = [
            sys.executable, "-m", "locust",
            "-f", str(BACKEND_DIR / "tests" / "load" / "locustfile.py"),
            "--host", "http://localhost:8000",
            "--users", "5",
            "--hatch-rate", "1",
            "--runtime", "30",
            "--csv", str(REPORTS_DIR / "load_test"),
            "--html", str(REPORTS_DIR / "load_test_report.html"),
            "-t", "30s",
        ]

        # Run in background to avoid blocking
        exit_code, stdout, stderr = self.run_command(
            cmd, BACKEND_DIR, "Running load tests", timeout=120
        )

        results["exit_code"] = exit_code
        self.results["tests"]["load"] = results
        return results

    def generate_report(self) -> str:
        """Generate HTML test report."""
        self.log_section("GENERATING REPORT")

        report = f"""<!DOCTYPE html>
<html>
<head>
    <title>Personal Finance AI - Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
        .stat {{ background: #007bff; color: white; padding: 15px 25px; border-radius: 5px; text-align: center; }}
        .stat.fail {{ background: #dc3545; }}
        .stat.skip {{ background: #6c757d; }}
        .stat h3 {{ margin: 0; font-size: 24px; }}
        .stat p {{ margin: 5px 0 0 0; font-size: 12px; text-transform: uppercase; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f8f9fa; }}
        .pass {{ color: #28a745; }}
        .fail {{ color: #dc3545; }}
        .skip {{ color: #6c757d; }}
        .timestamp {{ color: #6c757d; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Personal Finance AI - Test Report</h1>
        <p class="timestamp">Generated: {self.results['timestamp']}</p>

        <div class="summary">
            <div class="stat">
                <h3>{self.results['summary']['total']}</h3>
                <p>Total Tests</p>
            </div>
            <div class="stat">
                <h3>{self.results['summary']['passed']}</h3>
                <p>Passed</p>
            </div>
            <div class="stat fail">
                <h3>{self.results['summary']['failed']}</h3>
                <p>Failed</p>
            </div>
            <div class="stat skip">
                <h3>{self.results['summary']['skipped']}</h3>
                <p>Skipped</p>
            </div>
        </div>

        <h2>Test Results by Suite</h2>
        <table>
            <tr>
                <th>Suite</th>
                <th>Status</th>
                <th>Details</th>
            </tr>
"""

        for suite, data in self.results["tests"].items():
            status = "pass" if data.get("exit_code", 0) == 0 else "fail"
            status_text = "PASS" if status == "pass" else "FAIL"
            details = f"Duration: {data.get('duration', 'N/A')}s" if "duration" in data else ""

            report += f"""
            <tr>
                <td>{suite.upper()}</td>
                <td class="{status}">{status_text}</td>
                <td>{details}</td>
            </tr>
"""

        report += """
        </table>

        <h2>Configuration</h2>
        <ul>
            <li>LLM Provider: Ollama (qwen2.5-coder:3b, granite3.1-moe:3b)</li>
            <li>Embeddings: nomic-embed-text:v1.5</li>
            <li>Database: PostgreSQL (localhost)</li>
            <li>Cache: Redis (localhost)</li>
        </ul>

        <h2>Notes</h2>
        <ul>
            <li>Integration tests require Ollama to be running on localhost:11434</li>
            <li>E2E tests require the backend to be running on localhost:8000</li>
            <li>Load tests use Locust for performance testing</li>
        </ul>
    </div>
</body>
</html>
"""

        report_path = REPORTS_DIR / "test_report.html"
        report_path.write_text(report)
        logger.info(f"Report saved to: {report_path}")

        return report_path

    def run(self, test_type: str = "all"):
        """Run tests based on type."""
        self.start_time = time.time()

        # Create reports directory
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

        logger.info(f"Starting test run: {test_type}")
        logger.info(f"Reports will be saved to: {REPORTS_DIR}")

        if test_type in ["unit", "all"]:
            self.run_unit_tests(integration=(test_type == "all"))

        if test_type in ["integration", "all"]:
            self.run_integration_tests()

        if test_type in ["e2e", "all"]:
            self.run_e2e_tests()

        if test_type == "load":
            self.run_load_tests()

        self.end_time = time.time()
        self.results["summary"]["duration_seconds"] = self.end_time - self.start_time

        # Generate report
        if test_type == "all":
            self.generate_report()

        # Print summary
        self.log_section("TEST SUMMARY")
        logger.info(f"Total duration: {self.results['summary']['duration_seconds']:.2f}s")

        return self.results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test runner for Personal Finance AI")
    parser.add_argument(
        "--type",
        choices=["unit", "integration", "e2e", "load", "all", "report"],
        default="all",
        help="Type of tests to run",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(REPORTS_DIR),
        help="Output directory for reports",
    )

    args = parser.parse_args()

    runner = TestRunner()
    results = runner.run(args.type)

    # Exit with appropriate code
    if args.type == "all":
        has_failures = any(
            r.get("exit_code", 0) != 0
            for r in results["tests"].values()
            if r.get("exit_code") is not None
        )
        sys.exit(1 if has_failures else 0)


if __name__ == "__main__":
    main()
