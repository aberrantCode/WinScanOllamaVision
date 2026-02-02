"""
Master Test Runner
Executes all comprehensive tests for Phases 1-3
"""

import os
import sys
import time

# Fix encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import test modules
import test_phase1_database
import test_phase2_providers
import test_phase3_services


def print_header():
    """Print test suite header"""
    print("\n" + "="*70)
    print("=" + " "*68 + "=")
    print("=" + "  WINSCAN OLLAMA VISION - COMPREHENSIVE TEST SUITE  ".center(68) + "=")
    print("=" + "  Phases 1-3: Foundation, Providers, and Services  ".center(68) + "=")
    print("=" + " "*68 + "=")
    print("="*70)


def print_separator():
    """Print section separator"""
    print("\n" + "-"*70 + "\n")


def run_test_phase(phase_name, test_function):
    """
    Run a test phase and track results.

    Args:
        phase_name: Name of the phase being tested
        test_function: Test function to execute

    Returns:
        Tuple of (passed: bool, duration_seconds: float)
    """
    print_separator()
    print(f">>> Starting {phase_name}...")
    print_separator()

    start_time = time.time()

    try:
        result = test_function()
        duration = time.time() - start_time

        if result == 0:
            print(f"\n[PASS] {phase_name} PASSED in {duration:.2f}s")
            return True, duration
        else:
            print(f"\n[FAIL] {phase_name} FAILED")
            return False, duration

    except Exception as e:
        duration = time.time() - start_time
        print(f"\n[FAIL] {phase_name} FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        return False, duration


def print_summary(results):
    """
    Print test summary.

    Args:
        results: List of (phase_name, passed, duration) tuples
    """
    print_separator()
    print("\n" + "="*70)
    print("=" + " "*68 + "=")
    print("=" + "  TEST SUMMARY  ".center(68) + "=")
    print("=" + " "*68 + "=")
    print("="*70 + "\n")

    total_duration = 0
    passed_count = 0
    failed_phases = []

    for phase_name, passed, duration in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status}  {phase_name:<40} {duration:>8.2f}s")
        total_duration += duration
        if passed:
            passed_count += 1
        else:
            failed_phases.append(phase_name)

    print("\n" + "-"*70)
    print(f"\n  Total: {passed_count}/{len(results)} phases passed")
    print(f"  Total duration: {total_duration:.2f}s")

    if failed_phases:
        print(f"\n  [X] Failed phases: {', '.join(failed_phases)}")
    else:
        print("\n  [SUCCESS] ALL TESTS PASSED!")

    print("\n" + "="*70 + "\n")

    return len(failed_phases) == 0


def main():
    """Run all test phases"""
    print_header()

    results = []

    # Phase 1: Database Foundation
    passed, duration = run_test_phase(
        "Phase 1: Database Foundation",
        test_phase1_database.main
    )
    results.append(("Phase 1: Database Foundation", passed, duration))

    # Phase 2: LLM Provider Abstraction
    passed, duration = run_test_phase(
        "Phase 2: LLM Provider Abstraction",
        test_phase2_providers.main
    )
    results.append(("Phase 2: LLM Provider Abstraction", passed, duration))

    # Phase 3: Analysis & Bundling Services
    passed, duration = run_test_phase(
        "Phase 3: Analysis & Bundling Services",
        test_phase3_services.main
    )
    results.append(("Phase 3: Analysis & Bundling Services", passed, duration))

    # Print summary
    all_passed = print_summary(results)

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
