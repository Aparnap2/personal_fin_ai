"""
Load Tests for Personal Finance AI

Uses Locust to test:
- API endpoints under load
- Categorization throughput
- Database queries performance
- Frontend page load times

Run with: locust -f locustfile.py --host=http://localhost:8000
"""
import json
import logging
import random
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from locust import (
    HttpUser,
    TaskSet,
    task,
    events,
    between,
    sequential,
)
from locust.runners import MasterRunner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test data
TEST_USER_ID = str(uuid.uuid4())

# Sample transactions for load testing
SAMPLE_TRANSACTIONS = [
    {"description": "Swiggy order for dinner", "amount": 450.00, "category": "Dining"},
    {"description": "Uber trip to airport", "amount": 320.00, "category": "Transport"},
    {"description": "BigBasket groceries", "amount": 2100.00, "category": "Groceries"},
    {"description": "Netflix subscription", "amount": 499.00, "category": "Subscriptions"},
    {"description": "Electricity bill payment", "amount": 2500.00, "category": "Utilities"},
    {"description": "Amazon shopping", "amount": 3500.00, "category": "Shopping"},
    {"description": "Movie tickets", "amount": 600.00, "category": "Entertainment"},
    {"description": "Pharmacy medicines", "amount": 450.00, "category": "Health"},
    {"description": "Petrol refill", "amount": 1800.00, "category": "Transport"},
    {"description": "Salary deposit", "amount": 75000.00, "category": "Income"},
]


class LoadTestMetrics:
    """Track load test metrics."""

    def __init__(self):
        self.total_requests = 0
        self.total_failures = 0
        self.total_successes = 0
        self.response_times = []
        self.throughput = []

    def record(self, response_time: float, success: bool):
        self.total_requests += 1
        if success:
            self.total_successes += 1
        else:
            self.total_failures += 1
        self.response_times.append(response_time)

    def get_stats(self) -> dict:
        if not self.response_times:
            return {}

        sorted_times = sorted(self.response_times)
        p50 = sorted_times[len(sorted_times) // 2]
        p95 = sorted_times[int(len(sorted_times) * 0.95)]
        p99 = sorted_times[int(len(sorted_times) * 0.99)]

        return {
            "total_requests": self.total_requests,
            "successes": self.total_successes,
            "failures": self.total_failures,
            "success_rate": self.total_successes / self.total_requests if self.total_requests > 0 else 0,
            "p50_latency_ms": p50,
            "p95_latency_ms": p95,
            "p99_latency_ms": p99,
            "avg_latency_ms": sum(self.response_times) / len(self.response_times),
        }


# Global metrics instance
metrics = LoadTestMetrics()


@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Initialize metrics on Locust start."""
    logger.info("Load test initialized")
    if isinstance(environment.runner, MasterRunner):
        logger.info("Running in distributed mode")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Log final metrics on test stop."""
    logger.info("Load test completed")
    stats = metrics.get_stats()
    logger.info(f"Final metrics: {json.dumps(stats, indent=2)}")

    # Save metrics to file
    with open("/tmp/load_test_results.json", "w") as f:
        json.dump(stats, f, indent=2)
    logger.info("Metrics saved to /tmp/load_test_results.json")


class APITaskSet(TaskSet):
    """API load testing tasks."""

    def on_start(self):
        """Set up test user."""
        self.user_id = str(uuid.uuid4())
        logger.info(f"Starting test for user: {self.user_id}")

    @task(10)
    def health_check(self):
        """Test health check endpoint (high frequency)."""
        with self.client.get(
            "/health",
            name="health_check",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                metrics.record(response.elapsed.total_seconds() * 1000, True)
            else:
                response.failure(f"Status: {response.status_code}")
                metrics.record(response.elapsed.total_seconds() * 1000, False)

    @task(5)
    def get_transactions(self):
        """Test get transactions endpoint."""
        with self.client.get(
            "/api/transactions",
            headers={"X-User-ID": self.user_id},
            name="get_transactions",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                metrics.record(response.elapsed.total_seconds() * 1000, True)
            else:
                response.failure(f"Status: {response.status_code}")
                metrics.record(response.elapsed.total_seconds() * 1000, False)

    @task(3)
    def get_dashboard(self):
        """Test dashboard endpoint."""
        with self.client.get(
            "/api/dashboard",
            headers={"X-User-ID": self.user_id},
            name="get_dashboard",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                metrics.record(response.elapsed.total_seconds() * 1000, True)
            else:
                response.failure(f"Status: {response.status_code}")
                metrics.record(response.elapsed.total_seconds() * 1000, False)

    @task(2)
    def get_budgets(self):
        """Test get budgets endpoint."""
        with self.client.get(
            "/api/budgets",
            headers={"X-User-ID": self.user_id},
            name="get_budgets",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                metrics.record(response.elapsed.total_seconds() * 1000, True)
            else:
                response.failure(f"Status: {response.status_code}")
                metrics.record(response.elapsed.total_seconds() * 1000, False)

    @task(2)
    def create_budget(self):
        """Test create budget endpoint."""
        budget = {
            "user_id": self.user_id,
            "category": random.choice(["Groceries", "Dining", "Transport"]),
            "monthly_limit": random.randint(1000, 10000),
            "month": datetime.now().strftime("%Y-%m-01"),
        }

        with self.client.post(
            "/api/budgets",
            json=budget,
            headers={"X-User-ID": self.user_id},
            name="create_budget",
            catch_response=True,
        ) as response:
            if response.status_code in [200, 201]:
                response.success()
                metrics.record(response.elapsed.total_seconds() * 1000, True)
            else:
                response.failure(f"Status: {response.status_code}")
                metrics.record(response.elapsed.total_seconds() * 1000, False)

    @task(1)
    def upload_csv(self):
        """Test CSV upload endpoint (lower frequency due to size)."""
        csv_content = "date,description,amount\n"
        for i in range(10):
            tx = random.choice(SAMPLE_TRANSACTIONS)
            csv_content += f"2024-01-{15+i:02d},{tx['description']},{tx['amount']}\n"

        with self.client.post(
            "/api/upload/csv",
            files={"file": ("test.csv", csv_content, "text/csv")},
            headers={"X-User-ID": self.user_id},
            name="upload_csv",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                metrics.record(response.elapsed.total_seconds() * 1000, True)
            else:
                response.failure(f"Status: {response.status_code}")
                metrics.record(response.elapsed.total_seconds() * 1000, False)

    @task(1)
    def categorize_transactions(self):
        """Test categorization endpoint (lower frequency due to LLM latency)."""
        transactions = [
            {
                "date": datetime.now().isoformat(),
                "description": tx["description"],
                "amount": str(tx["amount"]),
            }
            for tx in random.sample(SAMPLE_TRANSACTIONS, 5)
        ]

        with self.client.post(
            "/api/categorize",
            json={
                "transactions": transactions,
                "user_id": self.user_id,
            },
            headers={"X-User-ID": self.user_id},
            name="categorize",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                metrics.record(response.elapsed.total_seconds() * 1000, True)
            else:
                response.failure(f"Status: {response.status_code}")
                metrics.record(response.elapsed.total_seconds() * 1000, False)


class CategorizationLoadTest(HttpUser):
    """Focused load test for categorization endpoint."""

    tasks = [APITaskSet]
    wait_time = between(1, 5)

    # Higher weight = more users running this
    weight = 3


class DashboardLoadTest(HttpUser):
    """Focused load test for dashboard endpoints."""

    tasks = {
        "health_check": 10,
        "get_transactions": 5,
        "get_dashboard": 5,
        "get_budgets": 3,
    }
    wait_time = between(0.5, 2)

    weight = 2


class BurstLoadTest(HttpUser):
    """Burst load test - simulates sudden spike in traffic."""

    tasks = [APITaskSet]
    wait_time = between(0.1, 0.5)  # Faster requests

    weight = 1


# Custom statistics reporting
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Track individual request metrics."""
    pass  # Metrics are tracked in the task methods for more control


class LoadTestConfig:
    """Load test configuration."""

    # Spawn rates
    HATCH_RATE = 1  # Users per second
    MAX_USERS = 50  # Maximum concurrent users

    # Test durations (in seconds)
    WARMUP_TIME = 10
    RUN_TIME = 60
    COOLDOWN_TIME = 10

    # Thresholds for failure
    P95_LATENCY_THRESHOLD_MS = 2000  # 2 seconds
    ERROR_RATE_THRESHOLD = 0.05  # 5%


def run_load_test():
    """Run load test and print results."""
    import subprocess
    import sys

    cmd = [
        sys.executable, "-m", "locust",
        "-f", __file__,
        "--host", "http://localhost:8000",
        "--hatch-rate", str(LoadTestConfig.HATCH_RATE),
        "--users", str(LoadTestConfig.MAX_USERS),
        "--runtime", str(LoadTestConfig.RUN_TIME),
        "--csv", "/tmp/locust_results",
        "--html", "/tmp/locust_report.html",
        "-t", f"{LoadTestConfig.WARMUP_TIME + LoadTestConfig.RUN_TIME + LoadTestConfig.COOLDOWN_TIME}s",
    ]

    logger.info(f"Running load test: {' '.join(cmd)}")
    subprocess.run(cmd)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--run":
        run_load_test()
    else:
        print("Usage: locust -f locustfile.py --host=http://localhost:8000")
        print("Or: python locustfile.py --run")
