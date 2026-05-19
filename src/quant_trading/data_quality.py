from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from quant_trading.data_cache import get_or_fetch_a_share_history
from quant_trading.data_sources import DataSourceConfig, fetch_a_share_history


PRICE_COLUMNS = ["open", "high", "low", "close"]
COMPARE_COLUMNS = PRICE_COLUMNS + ["volume"]


@dataclass(frozen=True)
class SourceCheck:
    requested_source: str
    actual_source: str
    rows: int
    cache_status: str
    error: str | None = None


@dataclass(frozen=True)
class CrossCheckResult:
    source_checks: list[SourceCheck]
    differences: pd.DataFrame
    missing_dates: pd.DataFrame

    @property
    def passed(self) -> bool:
        return self.differences.empty and self.missing_dates.empty and all(check.error is None for check in self.source_checks)


def cross_check_a_share_sources(
    symbol: str,
    start_date: str,
    end_date: str,
    sources: list[str],
    adjust: str = "qfq",
    cache_path: str | Path | None = None,
    refresh: bool = False,
    price_tolerance: float = 0.01,
    volume_tolerance_ratio: float = 0.001,
) -> CrossCheckResult:
    """Compare daily OHLCV data from multiple sources for the same stock and date range."""
    if len(sources) < 2:
        raise ValueError("at least two sources are required for cross check")

    datasets: dict[str, pd.DataFrame] = {}
    checks: list[SourceCheck] = []
    for source in sources:
        config = DataSourceConfig(source=source, adjust=adjust)
        try:
            if cache_path is None:
                data = fetch_a_share_history(symbol, start_date, end_date, config)
                data.attrs["cache_status"] = "disabled"
            else:
                data = get_or_fetch_a_share_history(symbol, start_date, end_date, cache_path, config, refresh)
            requested_source = source.lower()
            datasets[requested_source] = data
            checks.append(
                SourceCheck(
                    requested_source=requested_source,
                    actual_source=data.attrs.get("source", requested_source),
                    rows=len(data),
                    cache_status=data.attrs.get("cache_status", "disabled"),
                )
            )
        except Exception as exc:
            checks.append(
                SourceCheck(
                    requested_source=source.lower(),
                    actual_source="",
                    rows=0,
                    cache_status="error",
                    error=str(exc),
                )
            )

    usable = {source: data for source, data in datasets.items() if not data.empty}
    if len(usable) < 2:
        return CrossCheckResult(checks, pd.DataFrame(), _build_missing_dates(usable))

    baseline_source = next(iter(usable))
    baseline = _indexed(usable[baseline_source])
    differences = []

    for source, data in list(usable.items())[1:]:
        current = _indexed(data)
        common_dates = baseline.index.intersection(current.index)
        for date in common_dates:
            for column in COMPARE_COLUMNS:
                left = float(baseline.loc[date, column])
                right = float(current.loc[date, column])
                tolerance = price_tolerance if column in PRICE_COLUMNS else max(abs(left), abs(right), 1.0) * volume_tolerance_ratio
                diff = abs(left - right)
                if diff > tolerance:
                    differences.append(
                        {
                            "date": date,
                            "column": column,
                            "baseline_source": baseline_source,
                            "compare_source": source,
                            "baseline_value": left,
                            "compare_value": right,
                            "abs_diff": diff,
                            "tolerance": tolerance,
                        }
                    )

    diff_frame = pd.DataFrame(differences)
    if not diff_frame.empty:
        diff_frame = diff_frame.sort_values(["date", "compare_source", "column"]).reset_index(drop=True)

    return CrossCheckResult(checks, diff_frame, _build_missing_dates(usable))


def _indexed(data: pd.DataFrame) -> pd.DataFrame:
    frame = data.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.set_index("date").sort_index()


def _build_missing_dates(datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if len(datasets) < 2:
        return pd.DataFrame(columns=["date", "source"])

    date_sets = {source: set(pd.to_datetime(data["date"])) for source, data in datasets.items()}
    all_dates = set().union(*date_sets.values())
    rows = []
    for source, dates in date_sets.items():
        for date in sorted(all_dates - dates):
            rows.append({"date": date, "source": source})
    return pd.DataFrame(rows, columns=["date", "source"])
