"""
Data Validation Module

Validates data quality, checks cricket scoring rules, detects duplicates,
and generates data quality reports.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple, Any
from collections import defaultdict
import logging
import json
from datetime import datetime

from src.data_loader import RawDelivery, DataLoader
from src.data_cleaning import CleanedDelivery, DataCleaner
from src.data_processor import (
    DataProcessor, BatterInnings, BowlerInnings,
    BatterSeason, BowlerSeason, BatterCareer, BowlerCareer
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""
    check_name: str
    passed: bool
    message: str
    details: Dict = field(default_factory=dict)
    severity: str = 'info'  # 'info', 'warning', 'error'


@dataclass
class DataQualityReport:
    """Comprehensive data quality report."""
    timestamp: str
    total_raw_deliveries: int
    total_cleaned_deliveries: int
    total_batter_innings: int
    total_bowler_innings: int
    total_batter_seasons: int
    total_bowler_seasons: int
    total_batter_careers: int
    total_bowler_careers: int

    validation_results: List[ValidationResult] = field(default_factory=list)
    quality_issues: List[Dict] = field(default_factory=list)
    duplicate_records: List[Dict] = field(default_factory=list)
    suspicious_records: List[Dict] = field(default_factory=list)
    summary_stats: Dict = field(default_factory=dict)

    def add_result(self, result: ValidationResult) -> None:
        self.validation_results.append(result)

    def get_errors(self) -> List[ValidationResult]:
        return [r for r in self.validation_results if r.severity == 'error' and not r.passed]

    def get_warnings(self) -> List[ValidationResult]:
        return [r for r in self.validation_results if r.severity == 'warning' and not r.passed]

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp,
            'counts': {
                'raw_deliveries': self.total_raw_deliveries,
                'cleaned_deliveries': self.total_cleaned_deliveries,
                'batter_innings': self.total_batter_innings,
                'bowler_innings': self.total_bowler_innings,
                'batter_seasons': self.total_batter_seasons,
                'bowler_seasons': self.total_bowler_seasons,
                'batter_careers': self.total_batter_careers,
                'bowler_careers': self.total_bowler_careers,
            },
            'validation_results': [
                {
                    'check': r.check_name,
                    'passed': r.passed,
                    'message': r.message,
                    'severity': r.severity,
                    'details': r.details,
                }
                for r in self.validation_results
            ],
            'quality_issues_count': len(self.quality_issues),
            'duplicate_records_count': len(self.duplicate_records),
            'suspicious_records_count': len(self.suspicious_records),
            'summary_stats': self.summary_stats,
        }

    def save_json(self, path: str) -> None:
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


class DataValidator:
    """Validates data at all levels of the pipeline."""

    def __init__(self):
        self.report = DataQualityReport(
            timestamp=datetime.now().isoformat(),
            total_raw_deliveries=0,
            total_cleaned_deliveries=0,
            total_batter_innings=0,
            total_bowler_innings=0,
            total_batter_seasons=0,
            total_bowler_seasons=0,
            total_batter_careers=0,
            total_bowler_careers=0,
        )

    def validate_raw_deliveries(self, raw_deliveries: List[RawDelivery]) -> None:
        """Validate raw delivery records."""
        self.report.total_raw_deliveries = len(raw_deliveries)

        # Check for duplicates (match_id, innings, ball)
        seen = set()
        duplicates = []
        for d in raw_deliveries:
            key = (d.match_id, d.innings, d.ball, d.striker, d.bowler)
            if key in seen:
                duplicates.append({
                    'match_id': d.match_id,
                    'innings': d.innings,
                    'ball': d.ball,
                    'striker': d.striker,
                    'bowler': d.bowler,
                })
            seen.add(key)

        self.report.duplicate_records = duplicates
        self.report.add_result(ValidationResult(
            check_name='raw_duplicates',
            passed=len(duplicates) == 0,
            message=f'Found {len(duplicates)} duplicate raw deliveries',
            details={'count': len(duplicates)},
            severity='error' if duplicates else 'info'
        ))

        # Check required fields
        missing_fields = defaultdict(int)
        for d in raw_deliveries:
            if not d.match_id:
                missing_fields['match_id'] += 1
            if not d.season:
                missing_fields['season'] += 1
            if not d.striker:
                missing_fields['striker'] += 1
            if not d.bowler:
                missing_fields['bowler'] += 1

        self.report.add_result(ValidationResult(
            check_name='raw_required_fields',
            passed=all(v == 0 for v in missing_fields.values()),
            message=f'Missing required fields: {dict(missing_fields)}',
            details=dict(missing_fields),
            severity='error' if any(v > 0 for v in missing_fields.values()) else 'info'
        ))

    def validate_cleaned_deliveries(self, cleaned: List[CleanedDelivery], cleaner: DataCleaner) -> None:
        """Validate cleaned delivery records."""
        self.report.total_cleaned_deliveries = len(cleaned)
        self.report.quality_issues = cleaner.get_quality_issues()

        # Check cricket scoring rules
        self._check_scoring_rules(cleaned)

        # Check ball counting consistency
        self._check_ball_counting(cleaned)

        # Check dismissal consistency
        self._check_dismissals(cleaned)

        # Check extras breakdown
        self._check_extras(cleaned)

        # Summary stats
        self.report.summary_stats = self._compute_summary_stats(cleaned)

    def _check_scoring_rules(self, cleaned: List[CleanedDelivery]) -> None:
        """Validate cricket scoring rules are correctly applied."""
        violations = []

        for d in cleaned:
            # Rule 1: Total runs = runs_off_bat + extras
            if d.total_runs != d.runs_off_bat + d.extras_total:
                violations.append(f"Match {d.match_id} ball {d.ball}: total_runs mismatch")

            # Rule 2: Bowler conceded = runs_off_bat + wides + noballs + penalty
            expected_bowler = d.runs_off_bat + d.wides + d.noballs + d.penalty
            if d.bowler_conceded_runs != expected_bowler:
                violations.append(f"Match {d.match_id} ball {d.ball}: bowler_conceded mismatch")

            # Rule 3: Batter runs = runs_off_bat (excludes byes/legbyes)
            if d.batter_runs != d.runs_off_bat:
                violations.append(f"Match {d.match_id} ball {d.ball}: batter_runs mismatch")

            # Rule 4: Boundary detection
            if d.runs_off_bat == 4 and not d.is_four:
                violations.append(f"Match {d.match_id} ball {d.ball}: is_four not set for 4 runs")
            if d.runs_off_bat == 6 and not d.is_six:
                violations.append(f"Match {d.match_id} ball {d.ball}: is_six not set for 6 runs")
            if d.is_boundary and d.runs_off_bat not in (4, 6):
                violations.append(f"Match {d.match_id} ball {d.ball}: is_boundary set incorrectly")

            # Rule 5: Legal delivery flag
            if d.wides > 0 and d.is_legal_delivery:
                violations.append(f"Match {d.match_id} ball {d.ball}: wide marked as legal")
            if d.wides == 0 and not d.is_legal_delivery and not d.is_noball:
                violations.append(f"Match {d.match_id} ball {d.ball}: non-wide marked as illegal")

        self.report.add_result(ValidationResult(
            check_name='cricket_scoring_rules',
            passed=len(violations) == 0,
            message=f'Scoring rule violations: {len(violations)}',
            details={'violations': violations[:10]},
            severity='error' if violations else 'info'
        ))

    def _check_ball_counting(self, cleaned: List[CleanedDelivery]) -> None:
        """Validate ball counting (overs, balls, wides)."""
        issues = []

        # Group by match and innings
        from collections import defaultdict
        innings_balls = defaultdict(list)
        for d in cleaned:
            if d.innings <= 2:  # Regular innings only
                innings_balls[(d.match_id, d.innings)].append(d)

        for (match_id, innings), deliveries in innings_balls.items():
            # Sort by actual_delivery_seq
            deliveries.sort(key=lambda x: x.actual_delivery_seq)

            # Check over progression
            max_over = max(d.over for d in deliveries)
            if max_over > 20:
                issues.append(f"Match {match_id} innings {innings}: over > 20 ({max_over})")

            # Count legal deliveries
            legal_count = sum(1 for d in deliveries if d.is_legal_delivery)
            if legal_count > 120:  # 20 overs * 6 balls
                issues.append(f"Match {match_id} innings {innings}: {legal_count} legal deliveries > 120")

            # Check for missing balls
            expected_balls = set()
            for over in range(max_over + 1):
                for ball in range(1, 7):
                    expected_balls.add((over, ball))

            actual_balls = set((d.over, d.ball_in_over) for d in deliveries if d.is_legal_delivery)
            missing = expected_balls - actual_balls
            # Only flag if significant missing (allow for early endings)
            if len(missing) > 10:
                issues.append(f"Match {match_id} innings {innings}: {len(missing)} expected legal balls missing")

        self.report.add_result(ValidationResult(
            check_name='ball_counting',
            passed=len(issues) == 0,
            message=f'Ball counting issues: {len(issues)}',
            details={'issues': issues[:10]},
            severity='warning' if issues else 'info'
        ))

    def _check_dismissals(self, cleaned: List[CleanedDelivery]) -> None:
        """Validate dismissal records."""
        issues = []

        for d in cleaned:
            if d.is_wicket:
                # Check player_dismissed is present
                if not d.player_dismissed:
                    issues.append(f"Match {d.match_id} ball {d.ball}: wicket without dismissed player")

                # Check dismissal kind is valid
                valid_kinds = {
                    'bowled', 'caught', 'caught and bowled', 'lbw', 'stumped',
                    'hit wicket', 'obstructing the field', 'run out', 'retired hurt', 'retired out'
                }
                if d.dismissal_kind not in valid_kinds:
                    issues.append(f"Match {d.match_id} ball {d.ball}: invalid dismissal kind '{d.dismissal_kind}'")

                # Run out should not be bowler wicket
                if d.dismissal_kind == 'run out' and d.is_bowler_wicket:
                    issues.append(f"Match {d.match_id} ball {d.ball}: run out marked as bowler wicket")

        self.report.add_result(ValidationResult(
            check_name='dismissals',
            passed=len(issues) == 0,
            message=f'Dismissal issues: {len(issues)}',
            details={'issues': issues[:10]},
            severity='warning' if issues else 'info'
        ))

    def _check_extras(self, cleaned: List[CleanedDelivery]) -> None:
        """Validate extras breakdown."""
        issues = []

        for d in cleaned:
            # Extras should equal sum of components
            expected = d.wides + d.noballs + d.byes + d.legbyes + d.penalty
            if d.extras_total != expected:
                issues.append(f"Match {d.match_id} ball {d.ball}: extras mismatch {d.extras_total} vs {expected}")

            # Wides should not be legal deliveries
            if d.wides > 0 and d.is_legal_delivery:
                issues.append(f"Match {d.match_id} ball {d.ball}: wides > 0 but legal delivery")

            # Byes/legbyes on wides (shouldn't happen normally)
            if d.wides > 0 and (d.byes > 0 or d.legbyes > 0):
                issues.append(f"Match {d.match_id} ball {d.ball}: byes/legbyes on wide")

        self.report.add_result(ValidationResult(
            check_name='extras_breakdown',
            passed=len(issues) == 0,
            message=f'Extras issues: {len(issues)}',
            details={'issues': issues[:10]},
            severity='warning' if issues else 'info'
        ))

    def _compute_summary_stats(self, cleaned: List[CleanedDelivery]) -> Dict:
        """Compute summary statistics."""
        total = len(cleaned)
        legal = sum(1 for d in cleaned if d.is_legal_delivery)
        wides = sum(1 for d in cleaned if d.is_wide)
        noballs = sum(1 for d in cleaned if d.is_noball)
        wickets = sum(1 for d in cleaned if d.is_wicket)
        boundaries = sum(1 for d in cleaned if d.is_boundary)
        fours = sum(1 for d in cleaned if d.is_four)
        sixes = sum(1 for d in cleaned if d.is_six)

        total_runs = sum(d.total_runs for d in cleaned)
        batter_runs = sum(d.batter_runs for d in cleaned)
        bowler_runs = sum(d.bowler_conceded_runs for d in cleaned)

        return {
            'total_deliveries': total,
            'legal_deliveries': legal,
            'wides': wides,
            'no_balls': noballs,
            'wickets': wickets,
            'boundaries': boundaries,
            'fours': fours,
            'sixes': sixes,
            'total_runs': total_runs,
            'batter_runs': batter_runs,
            'bowler_conceded_runs': bowler_runs,
            'runs_per_over': round(total_runs / (legal / 6), 2) if legal > 0 else 0,
        }

    def validate_batter_innings(self, innings_list: List[BatterInnings]) -> None:
        """Validate batter innings records."""
        self.report.total_batter_innings = len(innings_list)

        issues = []

        for bi in innings_list:
            # Strike rate calculation
            if bi.balls_faced > 0:
                expected_sr = round(bi.runs_scored / bi.balls_faced * 100, 2)
                if abs(bi.strike_rate - expected_sr) > 0.01:
                    issues.append(f"{bi.batter} match {bi.match_id}: SR mismatch {bi.strike_rate} vs {expected_sr}")

            # Balls faced should not exceed legal deliveries in innings (approx 120)
            if bi.balls_faced > 120:
                issues.append(f"{bi.batter} match {bi.match_id}: balls_faced {bi.balls_faced} > 120")

            # Runs should be non-negative
            if bi.runs_scored < 0:
                issues.append(f"{bi.batter} match {bi.match_id}: negative runs")

            # Boundaries consistency
            if bi.boundaries != bi.fours + bi.sixes:
                issues.append(f"{bi.batter} match {bi.match_id}: boundaries != fours + sixes")

        self.report.add_result(ValidationResult(
            check_name='batter_innings',
            passed=len(issues) == 0,
            message=f'Batter innings issues: {len(issues)}',
            details={'issues': issues[:10]},
            severity='warning' if issues else 'info'
        ))

    def validate_bowler_innings(self, innings_list: List[BowlerInnings]) -> None:
        """Validate bowler innings records."""
        self.report.total_bowler_innings = len(innings_list)

        issues = []

        for boli in innings_list:
            # Economy calculation
            if boli.balls_bowled > 0:
                expected_econ = round(boli.runs_conceded / (boli.balls_bowled / 6), 2)
                if abs(boli.economy - expected_econ) > 0.01:
                    issues.append(f"{boli.bowler} match {boli.match_id}: economy mismatch {boli.economy} vs {expected_econ}")

            # Strike rate calculation
            if boli.wickets > 0:
                expected_sr = round(boli.balls_bowled / boli.wickets, 2)
                if abs(boli.strike_rate - expected_sr) > 0.01:
                    issues.append(f"{boli.bowler} match {boli.match_id}: SR mismatch {boli.strike_rate} vs {expected_sr}")

                expected_avg = round(boli.runs_conceded / boli.wickets, 2)
                if abs(boli.average - expected_avg) > 0.01:
                    issues.append(f"{boli.bowler} match {boli.match_id}: avg mismatch {boli.average} vs {expected_avg}")

            # Balls bowled reasonable
            if boli.balls_bowled > 120:
                issues.append(f"{boli.bowler} match {boli.match_id}: balls_bowled {boli.balls_bowled} > 120")

        self.report.add_result(ValidationResult(
            check_name='bowler_innings',
            passed=len(issues) == 0,
            message=f'Bowler innings issues: {len(issues)}',
            details={'issues': issues[:10]},
            severity='warning' if issues else 'info'
        ))

    def validate_batter_seasons(self, seasons: Dict) -> None:
        """Validate batter season aggregates."""
        self.report.total_batter_seasons = len(seasons)

        issues = []

        for (batter, season), bs in seasons.items():
            # Average calculation
            if bs.dismissals > 0:
                expected_avg = round(bs.runs / bs.dismissals, 2)
                if abs(bs.average - expected_avg) > 0.01:
                    issues.append(f"{batter} {season}: avg mismatch {bs.average} vs {expected_avg}")

            # Strike rate
            if bs.balls_faced > 0:
                expected_sr = round(bs.runs / bs.balls_faced * 100, 2)
                if abs(bs.strike_rate - expected_sr) > 0.01:
                    issues.append(f"{batter} {season}: SR mismatch {bs.strike_rate} vs {expected_sr}")

            # Boundary rate
            if bs.balls_faced > 0:
                expected_br = round(bs.boundaries / bs.balls_faced, 4)
                if abs(bs.boundary_rate - expected_br) > 0.0001:
                    issues.append(f"{batter} {season}: boundary rate mismatch {bs.boundary_rate} vs {expected_br}")

            # Matches should be >= innings (can't have more innings than matches in T20)
            # Actually can have more innings than matches if super overs, but we filter those

        self.report.add_result(ValidationResult(
            check_name='batter_seasons',
            passed=len(issues) == 0,
            message=f'Batter season issues: {len(issues)}',
            details={'issues': issues[:10]},
            severity='warning' if issues else 'info'
        ))

    def validate_bowler_seasons(self, seasons: Dict) -> None:
        """Validate bowler season aggregates."""
        self.report.total_bowler_seasons = len(seasons)

        issues = []

        for (bowler, season), bs in seasons.items():
            # Economy
            if bs.overs > 0:
                expected_econ = round(bs.runs_conceded / bs.overs, 2)
                if abs(bs.economy - expected_econ) > 0.01:
                    issues.append(f"{bowler} {season}: economy mismatch {bs.economy} vs {expected_econ}")

            # Strike rate
            if bs.wickets > 0:
                expected_sr = round(bs.balls_bowled / bs.wickets, 2)
                if abs(bs.strike_rate - expected_sr) > 0.01:
                    issues.append(f"{bowler} {season}: SR mismatch {bs.strike_rate} vs {expected_sr}")

                expected_avg = round(bs.runs_conceded / bs.wickets, 2)
                if abs(bs.average - expected_avg) > 0.01:
                    issues.append(f"{bowler} {season}: avg mismatch {bs.average} vs {expected_avg}")

        self.report.add_result(ValidationResult(
            check_name='bowler_seasons',
            passed=len(issues) == 0,
            message=f'Bowler season issues: {len(issues)}',
            details={'issues': issues[:10]},
            severity='warning' if issues else 'info'
        ))

    def validate_batter_careers(self, careers: Dict) -> None:
        """Validate batter career aggregates."""
        self.report.total_batter_careers = len(careers)

        issues = []

        for batter, bc in careers.items():
            # Average
            if bc.dismissals > 0:
                expected_avg = round(bc.runs / bc.dismissals, 2)
                if abs(bc.average - expected_avg) > 0.01:
                    issues.append(f"{batter}: career avg mismatch {bc.average} vs {expected_avg}")

            # Strike rate
            if bc.balls_faced > 0:
                expected_sr = round(bc.runs / bc.balls_faced * 100, 2)
                if abs(bc.strike_rate - expected_sr) > 0.01:
                    issues.append(f"{batter}: career SR mismatch {bc.strike_rate} vs {expected_sr}")

        self.report.add_result(ValidationResult(
            check_name='batter_careers',
            passed=len(issues) == 0,
            message=f'Batter career issues: {len(issues)}',
            details={'issues': issues[:10]},
            severity='warning' if issues else 'info'
        ))

    def validate_bowler_careers(self, careers: Dict) -> None:
        """Validate bowler career aggregates."""
        self.report.total_bowler_careers = len(careers)

        issues = []

        for bowler, bc in careers.items():
            # Economy
            if bc.overs > 0:
                expected_econ = round(bc.runs_conceded / bc.overs, 2)
                if abs(bc.economy - expected_econ) > 0.01:
                    issues.append(f"{bowler}: career economy mismatch {bc.economy} vs {expected_econ}")

            # Strike rate
            if bc.wickets > 0:
                expected_sr = round(bc.balls_bowled / bc.wickets, 2)
                if abs(bc.strike_rate - expected_sr) > 0.01:
                    issues.append(f"{bowler}: career SR mismatch {bc.strike_rate} vs {expected_sr}")

                expected_avg = round(bc.runs_conceded / bc.wickets, 2)
                if abs(bc.average - expected_avg) > 0.01:
                    issues.append(f"{bowler}: career avg mismatch {bc.average} vs {expected_avg}")

        self.report.add_result(ValidationResult(
            check_name='bowler_careers',
            passed=len(issues) == 0,
            message=f'Bowler career issues: {len(issues)}',
            details={'issues': issues[:10]},
            severity='warning' if issues else 'info'
        ))

    def validate_all(self, processor: DataProcessor, cleaned: List[CleanedDelivery], cleaner: DataCleaner,
                     raw_deliveries: List[RawDelivery]) -> DataQualityReport:
        """Run all validations."""
        logger.info("Running validations...")

        self.validate_raw_deliveries(raw_deliveries)
        self.validate_cleaned_deliveries(cleaned, cleaner)
        self.validate_batter_innings(processor.get_batter_innings())
        self.validate_bowler_innings(processor.get_bowler_innings())
        self.validate_batter_seasons(processor.get_batter_seasons())
        self.validate_bowler_seasons(processor.get_bowler_seasons())
        self.validate_batter_careers(processor.get_batter_careers())
        self.validate_bowler_careers(processor.get_bowler_careers())

        logger.info("Validations complete")
        return self.report


def run_validation_pipeline(zip_path: str) -> DataQualityReport:
    """Run full pipeline with validation."""
    from src.data_loader import DataLoader
    from src.data_cleaning import DataCleaner

    logger.info(f"Loading data from {zip_path}...")
    with DataLoader(zip_path) as loader:
        raw_deliveries = list(loader.load_all_matches())

    logger.info(f"Loaded {len(raw_deliveries)} raw deliveries")
    logger.info("Cleaning deliveries...")
    cleaner = DataCleaner()
    cleaned_deliveries = cleaner.clean_all(raw_deliveries)

    logger.info("Processing derived records...")
    processor = DataProcessor()
    processor.process_deliveries(cleaned_deliveries)

    logger.info("Validating...")
    validator = DataValidator()
    report = validator.validate_all(processor, cleaned_deliveries, cleaner, raw_deliveries)

    return report