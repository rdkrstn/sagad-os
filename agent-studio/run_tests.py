import os
import sys
import time
import pytest
import dotenv

# Ensure we unset database and secret keys to prevent connection timeouts/401 auth failures in TestClient
os.environ["DATABASE_URL"] = ""
os.environ["AGENT_STUDIO_INTERNAL_SECRET"] = ""
os.environ["CHATWOOT_WEBHOOK_TOKEN"] = ""
os.environ["SAGAD_REALTIME_SECRET"] = ""
os.environ["CHATWOOT_BASE_URL"] = ""
os.environ["CHATWOOT_ACCOUNT_ID"] = ""
os.environ["CHATWOOT_API_ACCESS_TOKEN"] = ""

class ConsolidatedReporter:
    def __init__(self):
        self.stats = {}
        self.failures = []
        self.start_time = None
        self.end_time = None

    def pytest_sessionstart(self, session):
        self.start_time = time.time()

    def pytest_sessionfinish(self, session, exitstatus):
        self.end_time = time.time()

    def pytest_runtest_logreport(self, report):
        # We only count test results from call stage, or setup/teardown if they fail
        nodeid = report.nodeid
        file_path = nodeid.split("::")[0]
        
        if file_path not in self.stats:
            self.stats[file_path] = {"passed": 0, "failed": 0, "skipped": 0, "errored": 0}

        if report.when == "setup" and report.failed:
            self.stats[file_path]["errored"] += 1
            self.failures.append((nodeid, "setup", report.longreprtext))
        elif report.when == "teardown" and report.failed:
            self.stats[file_path]["errored"] += 1
            self.failures.append((nodeid, "teardown", report.longreprtext))
        elif report.when == "call":
            if report.failed:
                self.stats[file_path]["failed"] += 1
                self.failures.append((nodeid, "call", report.longreprtext))
            elif report.skipped:
                self.stats[file_path]["skipped"] += 1
            else:
                self.stats[file_path]["passed"] += 1

def run_consolidated_tests():
    reporter = ConsolidatedReporter()
    
    print("=" * 70)
    print(" SAGAD OS AGENT STUDIO - CONSOLIDATED TEST RUNNER")
    print("=" * 70)
    print("Unsetting DATABASE_URL for in-memory testing...")
    print("Running pytest on tests/ directory...\n")
    
    # Run pytest with our custom reporter plugin
    # -q: quiet, -p no:warnings: hide default warnings spam
    exit_code = pytest.main(
        ["tests/", "-q", "-p", "no:warnings"],
        plugins=[reporter]
    )
    
    duration = reporter.end_time - reporter.start_time if reporter.start_time and reporter.end_time else 0.0
    
    print("\n" + "=" * 70)
    print(" CONSOLIDATED TEST SUMMARY")
    print("=" * 70)
    
    total_passed = 0
    total_failed = 0
    total_skipped = 0
    total_errored = 0
    
    # Sort files by name for consistency
    for file_path in sorted(reporter.stats.keys()):
        counts = reporter.stats[file_path]
        passed = counts["passed"]
        failed = counts["failed"]
        skipped = counts["skipped"]
        errored = counts["errored"]
        
        total_passed += passed
        total_failed += failed
        total_skipped += skipped
        total_errored += errored
        
        file_total = passed + failed + skipped + errored
        
        status_str = "SUCCESS"
        if failed > 0 or errored > 0:
            status_str = "FAILURE"
            
        print(f"[File] {file_path:<35} | Total: {file_total:>3} | "
              f"Passed: {passed:>3} | Failed: {failed:>3} | "
              f"Errored: {errored:>3} | Status: {status_str}")
        
    print("-" * 70)
    total_all = total_passed + total_failed + total_skipped + total_errored
    print(f"[Summary] OVERALL RESULTS: Passed {total_passed}/{total_all} tests | "
          f"Failed: {total_failed} | Errored: {total_errored} | "
          f"Duration: {duration:.2f}s")
    
    if reporter.failures:
        print("\n" + "=" * 70)
        print(" DETAILED FAILURE LOG")
        print("=" * 70)
        for nodeid, stage, longrepr in reporter.failures:
            print(f"\n[Failed] FAILURE in {nodeid} ({stage} stage):")
            print("-" * 70)
            print(longrepr)
            print("-" * 70)
            
    print("=" * 70)
    if exit_code == 0:
        print(" SUCCESS: All tests completed and passed successfully!")
        print("=" * 70)
        sys.exit(0)
    else:
        print(" FAILURE: Some tests did not pass. Check details above.")
        print("=" * 70)
        sys.exit(1)

if __name__ == "__main__":
    run_consolidated_tests()
