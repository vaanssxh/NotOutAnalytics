"""
Main Pipeline Script

Runs the complete data ingestion, cleaning, processing, and validation pipeline.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_loader import DataLoader
from src.data_cleaning import DataCleaner
from src.data_processor import DataProcessor, run_full_pipeline
from src.data_validation import DataValidator, run_validation_pipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run the complete pipeline."""
    zip_path = Path("C:/claudepro/Sports-Analytics/data/raw/ipl_csv2.zip")

    if not zip_path.exists():
        logger.error(f"Zip file not found: {zip_path}")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("STARTING IPL DATA PIPELINE")
    logger.info("=" * 60)

    # Run pipeline with validation
    logger.info("Running validation pipeline...")
    report = run_validation_pipeline(str(zip_path))

    # Print summary
    logger.info("=" * 60)
    logger.info("PIPELINE SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Raw deliveries: {report.total_raw_deliveries}")
    logger.info(f"Cleaned deliveries: {report.total_cleaned_deliveries}")
    logger.info(f"Batter innings: {report.total_batter_innings}")
    logger.info(f"Bowler innings: {report.total_bowler_innings}")
    logger.info(f"Batter seasons: {report.total_batter_seasons}")
    logger.info(f"Bowler seasons: {report.total_bowler_seasons}")
    logger.info(f"Batter careers: {report.total_batter_careers}")
    logger.info(f"Bowler careers: {report.total_bowler_careers}")

    logger.info("\nValidation Results:")
    for result in report.validation_results:
        status = "PASS" if result.passed else "FAIL"
        logger.info(f"  [{status}] {result.check_name}: {result.message}")

    # Errors and warnings
    errors = report.get_errors()
    warnings = report.get_warnings()

    if errors:
        logger.error(f"\n{len(errors)} ERROR(S) FOUND:")
        for e in errors:
            logger.error(f"  - {e.check_name}: {e.message}")

    if warnings:
        logger.warning(f"\n{len(warnings)} WARNING(S):")
        for w in warnings:
            logger.warning(f"  - {w.check_name}: {w.message}")

    # Quality issues
    if report.quality_issues:
        logger.warning(f"\nQuality issues found: {len(report.quality_issues)}")
        # Group by issue type
        from collections import Counter
        issue_types = Counter(issue['issue'] for issue in report.quality_issues)
        for issue_type, count in issue_types.most_common():
            logger.warning(f"  {issue_type}: {count}")

    # Duplicates
    if report.duplicate_records:
        logger.warning(f"\nDuplicate raw records: {len(report.duplicate_records)}")

    # Summary stats
    if report.summary_stats:
        logger.info("\nSummary Statistics:")
        for key, value in report.summary_stats.items():
            logger.info(f"  {key}: {value}")

    # Save report
    output_dir = Path("C:/claudepro/Sports-Analytics/logs")
    output_dir.mkdir(exist_ok=True)
    report_path = output_dir / "data_quality_report.json"
    report.save_json(str(report_path))
    logger.info(f"\nData quality report saved to: {report_path}")

    # Print top players for verification
    logger.info("\n" + "=" * 60)
    logger.info("TOP BATTERS (Career)")
    logger.info("=" * 60)

    # We need to re-run processor to get the data for printing
    processor = run_full_pipeline(str(zip_path))

    # Top 10 career run scorers (min 200 balls)
    batter_careers = processor.get_batter_careers()
    qualified = [(b, bc) for b, bc in batter_careers.items() if bc.balls_faced >= 200]
    qualified.sort(key=lambda x: x[1].runs, reverse=True)

    logger.info(f"{'Rank':>4} {'Batter':<25} {'Runs':>6} {'Balls':>6} {'Avg':>6} {'SR':>7} {'4s':>4} {'6s':>4} {'50s':>4} {'100s':>4}")
    for i, (batter, bc) in enumerate(qualified[:10], 1):
        logger.info(f"{i:>4} {batter:<25} {bc.runs:>6} {bc.balls_faced:>6} {bc.average:>6.2f} {bc.strike_rate:>7.2f} {bc.fours:>4} {bc.sixes:>4} {bc.fifties:>4} {bc.hundreds:>4}")

    # Top 10 career wicket takers (min 100 balls)
    bowler_careers = processor.get_bowler_careers()
    qualified_bowlers = [(b, bc) for b, bc in bowler_careers.items() if bc.balls_bowled >= 100]
    qualified_bowlers.sort(key=lambda x: x[1].wickets, reverse=True)

    logger.info("\n" + "=" * 60)
    logger.info("TOP BOWLERS (Career)")
    logger.info("=" * 60)
    logger.info(f"{'Rank':>4} {'Bowler':<25} {'Wkts':>5} {'Balls':>6} {'Runs':>6} {'Avg':>6} {'Econ':>6} {'SR':>6}")
    for i, (bowler, bc) in enumerate(qualified_bowlers[:10], 1):
        logger.info(f"{i:>4} {bowler:<25} {bc.wickets:>5} {bc.balls_bowled:>6} {bc.runs_conceded:>6} {bc.average:>6.2f} {bc.economy:>6.2f} {bc.strike_rate:>6.2f}")

    logger.info("\n" + "=" * 60)
    logger.info("PIPELINE COMPLETED SUCCESSFULLY")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()