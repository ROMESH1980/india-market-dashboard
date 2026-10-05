#!/usr/bin/env python3
"""Build source-backed industry heatmap and weekly/monthly stock & industry race data.

Uses existing build_rs_rating NSE downloader, matching and corporate-action logic.
Never changes stocks.json or existing research scores. Output is written atomically.
"""
from __future__ import annotations

import json
import math
import os
import statistics
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
sys.path.insert(0, str(ROOT / 'scripts'))

import build_rs_rating as rs

OUTPUT = DATA / 'industry_heatmap.json'

PERIODS = {
    '1W': 7,
    '1M': 1,
    '3M': 3,
    '6M': 6,
    '1Y': 12,
}


def month_back(day: date, count: int) -> date:
    return rs.subtract_months(day, count)


def round_value(value):
    return (
        round(value, 3)
        if value is not None and math.isfinite(value)
        else None
    )


def valid_number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) and n > 0 else None
    except (ValueError, TypeError):
        return None


def target_dates(today):
    weekly = [
        today - timedelta(weeks=i)
        for i in range(52, -1, -1)
    ]

    monthly = [
        month_back(today, i)
        for i in range(12, -1, -1)
    ]

    period = {
        '1W': today - timedelta(days=7),
        '1M': month_back(today, 1),
        '3M': month_back(today, 3),
        '6M': month_back(today, 6),
        '1Y': month_back(today, 12),
    }

    return weekly, monthly, period


def load_snapshot(path):
    result = json.loads(
        path.read_text(encoding='utf-8')
    )

    if not isinstance(result, list) or not result:
        raise ValueError(
            'stocks.json must be a nonempty list'
        )

    return result


def build_stock_race(prices, targets):
    """
    Build an individual stock race series.

    IMPORTANT:
    The baseline is the FIRST AVAILABLE historical point for that stock,
    not necessarily targets[0].

    This allows recently listed stocks / stocks with shorter history
    to appear in the race chart instead of producing an all-null series.
    """

    available_targets = [
        t for t in targets
        if t in prices and valid_number(prices[t]) is not None
    ]

    if not available_targets:
        return {
            'dates': [],
            'values': [],
        }

    base_target = available_targets[0]
    base_price = valid_number(prices[base_target])

    if base_price is None:
        return {
            'dates': [],
            'values': [],
        }

    dates = []
    values = []

    for t in available_targets:
        price = valid_number(prices[t])

        if price is None:
            continue

        value = (price / base_price - 1) * 100

        dates.append(t.isoformat())
        values.append(round_value(value))

    return {
        'dates': dates,
        'values': values,
    }


def compute(stocks, fetch, actions, today):
    weekly, monthly, period = target_dates(today)

    requested = sorted(
        set(
            weekly
            + monthly
            + list(period.values())
        )
    )

    copies = {}
    failures = {}

    for target in requested:
        try:
            item = fetch(target)
            copies[target] = item

            print(
                f'Loaded {target} -> {item["date"]}',
                flush=True
            )

        except Exception as exc:
            failures[target.isoformat()] = str(exc)[:250]

            print(
                f'WARNING: {target}: {exc}',
                flush=True
            )

    if not copies:
        raise RuntimeError(
            'No historical NSE bhavcopies available; '
            'preserving previous output'
        )

    # ---------------------------------------------------------
    # Build adjusted historical price series for every stock.
    # ---------------------------------------------------------

    all_rows = {}
    industry_members = defaultdict(list)

    for stock in stocks:
        symbol = str(
            stock.get('symbol') or ''
        ).strip().upper()

        industry = str(
            stock.get('industry') or ''
        ).strip()

        current = valid_number(
            stock.get('price')
        )

        if (
            not symbol
            or not industry
            or current is None
            or industry.lower()
            in ('unclassified', 'unknown', 'n/a')
        ):
            continue

        series = {}

        for target, bhav in copies.items():

            raw = rs.lookup_price(
                stock,
                bhav
            )

            if raw is None:
                continue

            adjusted, _, _ = (
                rs.adjust_historical_price(
                    stock,
                    raw,
                    bhav['date'],
                    today,
                    actions
                )
            )

            adjusted = valid_number(adjusted)

            if adjusted is not None:
                series[target] = adjusted

        # Current EOD value is authoritative.
        series[today] = current

        # Even if older history is limited,
        # keep the stock as long as current price exists.
        all_rows[symbol] = (
            stock,
            series
        )

        industry_members[industry].append(
            symbol
        )

    # ---------------------------------------------------------
    # Individual stock return
    # ---------------------------------------------------------

    def stock_return(series, baseline):
        old = series.get(baseline)
        current = series.get(today)

        if old is None or current is None:
            return None

        old = valid_number(old)
        current = valid_number(current)

        if old is None or current is None:
            return None

        return (
            current / old - 1
        ) * 100

    # ---------------------------------------------------------
    # Industry Race
    #
    # KEEP EXISTING FIXED COHORT LOGIC.
    # This prevents artificial industry jumps caused by stocks
    # entering/leaving the sample.
    # ---------------------------------------------------------

    def race(symbols, targets):

        valid_symbols = [
            s
            for s in symbols
            if all(
                t in all_rows[s][1]
                for t in targets
            )
        ]

        if not valid_symbols:
            return {
                'eligible': 0,
                'dates': [],
                'values': [],
            }

        base = targets[0]

        values = []

        for t in targets:

            point_values = [
                (
                    all_rows[s][1][t]
                    / all_rows[s][1][base]
                    - 1
                ) * 100
                for s in valid_symbols
            ]

            values.append(
                round_value(
                    statistics.fmean(
                        point_values
                    )
                )
            )

        return {
            'eligible': len(valid_symbols),
            'dates': [
                t.isoformat()
                for t in targets
            ],
            'values': values,
        }

    # ---------------------------------------------------------
    # Build final Industry + Stock output
    # ---------------------------------------------------------

    industries = []
    stocks_output = {}

    for industry, symbols in sorted(
        industry_members.items()
    ):

        returns = {}
        coverage = {}

        for label, baseline in period.items():

            vals = [
                stock_return(
                    all_rows[s][1],
                    baseline
                )
                for s in symbols
            ]

            vals = [
                v
                for v in vals
                if v is not None
            ]

            returns[label] = (
                round_value(
                    statistics.fmean(vals)
                )
                if vals
                else None
            )

            coverage[label] = len(vals)

        ratings = [
            all_rows[s][0].get(
                'industryRating'
            )
            for s in symbols
        ]

        ratings = [
            float(v)
            for v in ratings
            if isinstance(v, (int, float))
            and math.isfinite(v)
        ]

        industries.append({
            'industry': industry,
            'stockCount': len(symbols),

            'returns': returns,

            'coverage': coverage,

            'rating': (
                round_value(
                    statistics.median(
                        ratings
                    )
                )
                if ratings
                else None
            ),

            'weekly': race(
                symbols,
                weekly
            ),

            'monthly': race(
                symbols,
                monthly
            ),

            'symbols': sorted(symbols),
        })

        # -----------------------------------------------------
        # Individual Stock Race
        # -----------------------------------------------------

        for symbol in symbols:

            stock, prices = all_rows[symbol]

            weekly_race = build_stock_race(
                prices,
                weekly
            )

            monthly_race = build_stock_race(
                prices,
                monthly
            )

            stocks_output[symbol] = {

                'name': (
                    stock.get('name')
                    or symbol
                ),

                'industry': industry,

                'returns': {
                    label: round_value(
                        stock_return(
                            prices,
                            baseline
                        )
                    )
                    for label, baseline
                    in period.items()
                },

                'weekly': weekly_race,

                'monthly': monthly_race,
            }

    # ---------------------------------------------------------
    # Do not publish if NSE historical snapshots themselves
    # were unavailable.
    # ---------------------------------------------------------

    if any(
        t not in copies
        for t in requested
    ):
        raise RuntimeError(
            f'{len(failures)} missing historical snapshots; '
            'preserving previous output'
        )

    return {

        'meta': {

            'asOf': today.isoformat(),

            'method':
                'Equal-weight mean of adjusted stock returns',

            'ratingMethod':
                'Median of existing stock industryRating '
                'values (not a newly computed rating)',

            'historyMethod':
                'Industry race uses fixed cohort; '
                'individual stock race uses first available '
                'historical point as baseline; no interpolation',

            'industryCount':
                len(industries),

            'stockCount':
                len(stocks_output),

            'weeklyPoints':
                len(weekly),

            'monthlyPoints':
                len(monthly),

            'snapshotDates': {
                t.isoformat():
                    copies[t]['date'].isoformat()
                for t in requested
            },

            'notes':
                'NSE bhavcopy close adjusted for recorded '
                'splits/bonuses; individual stocks with shorter '
                'history begin from their first available point.',
        },

        'industries':
            industries,

        'stocks':
            stocks_output,
    }


def main():

    stocks = load_snapshot(
        DATA / 'stocks.json'
    )

    today = rs.get_latest_stock_date(
        stocks
    )

    actions = (
        rs.load_corporate_action_adjustments()
    )

    rs.warmup_nse_session()

    result = compute(
        stocks,
        rs.load_nearest_bhavcopy,
        actions,
        today
    )

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    tmp = OUTPUT.with_suffix(
        '.json.tmp'
    )

    tmp.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            separators=(',', ':'),
            allow_nan=False
        ),
        encoding='utf-8'
    )

    os.replace(
        tmp,
        OUTPUT
    )

    print(
        f'OK: {OUTPUT}, '
        f'industries={len(result["industries"])}, '
        f'stocks={len(result["stocks"])}'
    )


if __name__ == '__main__':
    main()
