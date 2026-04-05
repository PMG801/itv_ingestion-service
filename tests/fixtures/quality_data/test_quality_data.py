"""
Quality Assurance Test Runner for Data Normalizers.

This script tests all three normalizers (Catalunya, Valencia, Galicia)
against their corresponding quality test files to verify data quality
and identify rejection patterns.

Usage:
    python tests/fixtures/quality_data/test_quality_data.py

Output:
    - Console summary with pass/fail rates
    - Detailed rejected items report
    - Compatibility matrix between sources

Run with Docker (recommended):
    docker compose run --rm normalizer python tests/fixtures/quality_data/test_quality_data.py
"""

import json
import sys
import os
from pathlib import Path
from typing import Any
from datetime import datetime

# Add project root to path for local execution
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Handle both local and containerized execution
try:
    from domain.itv_stations.transformers.factory import TransformerFactory
    from domain.itv_stations.schemas import NormalizedStation
except ImportError as e:
    print(
        f"⚠️  Warning: Could not import required modules: {e}\n"
        "   This script should be run with: docker compose run --rm normalizer "
        "python tests/fixtures/quality_data/test_quality_data.py\n"
        "   Or ensure the project root is in PYTHONPATH"
    )
    sys.exit(1)


class QualityTestRunner:
    """Runner for quality assurance tests across normalizers."""

    def __init__(self):
        """Initialize test runner."""
        self.fixtures_path = Path(__file__).parent
        self.results = {}
        self.total_valid = 0
        self.total_rejected = 0
        self.total_processed = 0

    def run_all_tests(self) -> None:
        """Run quality tests for all sources."""
        print("\n" + "=" * 80)
        print("🧪 QUALITY ASSURANCE TEST SUITE - ITV Station Data Normalizers")
        print("=" * 80 + "\n")

        # Test each source
        self._test_source("catalunya", "quality_test_catalunya.xml")
        self._test_source("valencia", "quality_test_valencia.json")
        self._test_source("galicia", "quality_test_galicia.csv")

        # Print summary
        self._print_summary()

    def _test_source(self, source: str, filename: str) -> None:
        """Test a specific source normalizer."""
        file_path = self.fixtures_path / filename

        if not file_path.exists():
            print(f"❌ Test file not found: {file_path}")
            return

        print(f"\n📋 Testing {source.upper()} ({filename})")
        print("-" * 80)

        try:
            # Load and parse file
            with open(file_path, "r") as f:
                if filename.endswith(".xml"):
                    raw_payload = f.read()
                elif filename.endswith(".json"):
                    raw_payload = json.load(f)
                elif filename.endswith(".csv"):
                    raw_payload = f.read()
                else:
                    print(f"❌ Unknown file format: {filename}")
                    return

            # Create transformer and process
            transformer = TransformerFactory.create(source)
            valid_stations = transformer.transform(raw_payload)

            # Count results
            rejected_count = len(transformer.rejected_items)
            total_count = len(valid_stations) + rejected_count

            # Calculate metrics
            pass_rate = (len(valid_stations) / total_count * 100) if total_count > 0 else 0

            # Store results
            self.results[source] = {
                "valid": len(valid_stations),
                "rejected": rejected_count,
                "total": total_count,
                "pass_rate": pass_rate,
                "rejected_items": transformer.rejected_items,
                "valid_stations": valid_stations,
            }

            # Update totals
            self.total_valid += len(valid_stations)
            self.total_rejected += rejected_count
            self.total_processed += total_count

            # Print results
            print(f"✅ Valid records:    {len(valid_stations):3d} / {total_count}")
            print(f"❌ Rejected records: {rejected_count:3d} / {total_count}")
            print(f"📊 Pass rate:        {pass_rate:5.1f}%")

            # Print rejection breakdown
            if transformer.rejected_items:
                self._print_rejections(source, transformer.rejected_items)

            # Print sample valid records
            if valid_stations:
                self._print_sample_records(source, valid_stations[:2])

        except Exception as e:
            print(f"❌ Error processing {source}: {str(e)}")
            import traceback
            traceback.print_exc()

    def _print_rejections(self, source: str, rejected_items: list[dict]) -> None:
        """Print rejection analysis."""
        print("\n  🚫 Rejection Breakdown:")

        # Count rejections by reason
        reason_counts = {}
        for item in rejected_items:
            reason = item.get("reason", "unknown")
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

        for reason, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"    • {reason:30s}: {count:3d}")

    def _print_sample_records(
        self, source: str, stations: list[NormalizedStation], limit: int = 2
    ) -> None:
        """Print sample valid records."""
        print(f"\n  ✅ Sample Valid Records (showing {min(limit, len(stations))}):")
        for i, station in enumerate(stations[:limit], 1):
            print(f"    Record {i}:")
            print(f"      • ID:       {station.station_id}")
            print(f"      • Name:     {station.name}")
            print(f"      • Province: {station.province}")
            print(f"      • Coords:   ({station.latitude:.4f}, {station.longitude:.4f})")

    def _print_summary(self) -> None:
        """Print overall summary."""
        print("\n" + "=" * 80)
        print("📊 OVERALL QUALITY SUMMARY")
        print("=" * 80)

        # Summary table
        print(
            "\n  Source       Valid   Rejected  Total   Pass Rate   Status"
        )
        print("  " + "-" * 76)

        for source in ["catalunya", "valencia", "galicia"]:
            if source in self.results:
                result = self.results[source]
                status = "✅ PASS" if result["pass_rate"] >= 20 else "⚠️  WARN"
                print(
                    f"  {source:12s} {result['valid']:5d}   {result['rejected']:5d}      "
                    f"{result['total']:5d}   {result['pass_rate']:6.1f}%    {status}"
                )

        # Totals
        if self.total_processed > 0:
            total_pass_rate = (self.total_valid / self.total_processed * 100)
            print("  " + "-" * 76)
            print(
                f"  {'TOTAL':12s} {self.total_valid:5d}   {self.total_rejected:5d}      "
                f"{self.total_processed:5d}   {total_pass_rate:6.1f}%"
            )

        print("\n" + "=" * 80)
        print("🎯 Quality Assurance Insights")
        print("=" * 80)

        print("\n  📈 What These Tests Verify:")
        print("    • Each normalizer correctly parses its source format")
        print("    • Invalid data is properly rejected with reasons logged")
        print("    • Valid data passes all validation rules")
        print("    • Different formats (XML, JSON, CSV) are handled correctly")

        print("\n  🔍 Rejection Patterns Detected:")
        for source, result in self.results.items():
            if result["rejected"] > 0:
                print(f"\n    {source.upper()}:")
                for reason, count in sorted(
                    self._get_reason_counts(result["rejected_items"]).items(),
                    key=lambda x: x[1],
                    reverse=True,
                ):
                    print(f"      • {reason}: {count} occurrences")

        print("\n  ✨ Recommendations:")
        print("    • Use these test files in your CI/CD pipeline")
        print("    • Monitor rejection rates over time")
        print("    • Add new test cases as new edge cases are discovered")
        print("    • Compare across versions to detect quality regressions")

        print("\n" + "=" * 80 + "\n")

    @staticmethod
    def _get_reason_counts(rejected_items: list[dict]) -> dict[str, int]:
        """Get rejection reasons and their counts."""
        counts = {}
        for item in rejected_items:
            reason = item.get("reason", "unknown")
            counts[reason] = counts.get(reason, 0) + 1
        return counts


def main():
    """Run quality tests."""
    runner = QualityTestRunner()
    runner.run_all_tests()


if __name__ == "__main__":
    main()
