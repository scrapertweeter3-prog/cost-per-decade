#!/usr/bin/env python3
"""costperdecade.py - buy-it-for-life math: cost per decade, cost per use,
and whether the durable option actually beats the cheap one over a horizon.

The yardstick: price alone is a bad comparator when lifespans differ.
A $40 item replaced every 2 years costs more per decade than a $280 item
that lasts 20. This tool does that arithmetic, plus the break-even year
and an honest verdict (durable wins / cheap wins / wash), so the numbers
come before the brand loyalty.

Stdlib only. Exit codes: 0 durable wins or wash, 1 cheap wins,
2 usage error (bad numbers).
"""

import argparse
import json
import math
import sys


def _positive(text):
    try:
        val = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}")
    if val <= 0:
        raise argparse.ArgumentTypeError(f"must be > 0, got {val}")
    return val


def _nonneg(text):
    try:
        val = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}")
    if val < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {val}")
    return val


def purchases_over(horizon_years, life_years):
    """How many units you must own to cover a horizon: ceil(horizon/life)."""
    return int(math.ceil(horizon_years / life_years - 1e-9)) or 1


def break_even_year(price_durable, life_durable, price_cheap, life_cheap,
                    horizon_years):
    """First year the cheap stack has spent at least as much as the durable.

    Both buyers pay for their first unit at year 0; replacements land when
    a unit dies (year life, 2*life, ... strictly inside the horizon), so
    the year-horizon totals match purchases_over() exactly. Returns 0 when
    the durable is cheaper up front, None if the cheap stack never catches
    up inside the horizon.
    """
    horizon = int(horizon_years)
    durable_spend = price_durable
    cheap_spend = price_cheap
    if cheap_spend >= durable_spend:
        return 0
    durable_next = life_durable
    cheap_next = life_cheap
    for year in range(1, horizon):
        if year >= durable_next:
            durable_spend += price_durable
            durable_next += life_durable
        if year >= cheap_next:
            cheap_spend += price_cheap
            cheap_next += life_cheap
        if cheap_spend >= durable_spend:
            return year
    return None


def warranty_class(warranty_years, life_years):
    if warranty_years <= 0:
        return "no warranty stated"
    covered = warranty_years / life_years
    if warranty_years >= life_years:
        return f"covered for life ({int(warranty_years)}y warranty on {int(life_years)}y expected life)"
    if covered >= 0.5:
        return f"solid ({int(warranty_years)}y warranty covers {covered:.0%} of expected life)"
    return (f"thin ({int(warranty_years)}y warranty covers only "
            f"{covered:.0%} of expected life)")


def main():
    ap = argparse.ArgumentParser(
        description="Cost per decade: does the durable option pay?")
    ap.add_argument("--price", type=_positive, required=True,
                    help="durable item price ($)")
    ap.add_argument("--life", type=_positive, required=True,
                    help="expected lifespan of the durable item (years)")
    ap.add_argument("--uses-year", type=_positive, default=0,
                    help="uses per year, for cost per use (default: skip)")
    ap.add_argument("--alt-price", type=_positive,
                    help="cheap alternative price ($)")
    ap.add_argument("--alt-life", type=_positive,
                    help="cheap alternative lifespan (years)")
    ap.add_argument("--warranty", type=_nonneg, default=0,
                    help="durable item warranty length (years)")
    ap.add_argument("--horizon", type=_positive, default=30,
                    help="comparison window in years (default: 30)")
    ap.add_argument("--json", action="store_true", help="machine output")
    args = ap.parse_args()

    if bool(args.alt_price) != bool(args.alt_life):
        ap.error("--alt-price and --alt-life go together")
    if args.alt_price and args.alt_price >= args.price * 100:
        ap.error("alt price within 100x of durable price: inputs swapped?")

    cost_per_decade = args.price / args.life * 10.0
    cost_per_use = (args.price / (args.life * args.uses_year)
                    if args.uses_year else None)

    result = {
        "item_cost_per_decade": round(cost_per_decade, 2),
        "item_cost_per_use": (round(cost_per_use, 4)
                              if cost_per_use is not None else None),
        "warranty": warranty_class(args.warranty, args.life),
    }
    verdict = "single item: cost per decade shown, no alternative given"
    exit_code = 0
    alt_cpd = d_total = c_total = None
    d_buys = c_buys = be = None

    if args.alt_price:
        alt_cpd = args.alt_price / args.alt_life * 10.0
        d_buys = purchases_over(args.horizon, args.life)
        c_buys = purchases_over(args.horizon, args.alt_life)
        d_total = d_buys * args.price
        c_total = c_buys * args.alt_price
        be = break_even_year(args.price, args.life, args.alt_price,
                             args.alt_life, args.horizon)
        result.update({
            "alt_cost_per_decade": round(alt_cpd, 2),
            "horizon_years": args.horizon,
            "durable_purchases": d_buys,
            "durable_total": round(d_total, 2),
            "cheap_purchases": c_buys,
            "cheap_total": round(c_total, 2),
            "break_even_year": be,
        })
        if d_total < c_total:
            saved = c_total - d_total
            if be == 0:
                verdict = (f"durable wins from the start, saves "
                           f"${saved:,.0f} over {args.horizon:g}y")
            else:
                verdict = (f"durable wins, break-even year {be}, saves "
                           f"${saved:,.0f} over {args.horizon:g}y")
        elif d_total == c_total:
            verdict = f"wash: both cost ${d_total:,.0f} over {args.horizon:g}y"
        else:
            verdict = (f"premium never recoups by year {int(args.horizon)}: "
                       f"cheap wins by ${d_total - c_total:,.0f}")
            exit_code = 1

    result["verdict"] = verdict

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"== cost per decade ({args.horizon:g}y horizon)")
        print(f"Cost per decade        {cost_per_decade:>8,.2f}  "
              f"(${args.price:,.0f} / {args.life:g}y)")
        if cost_per_use is not None:
            print(f"Cost per use           {cost_per_use:>8,.4f}  "
                  f"({args.uses_year:g} uses/y)")
        print(f"Warranty               {result['warranty']}")
        if args.alt_price:
            print(f"Alt cost per decade    {alt_cpd:>8,.2f}  "
                  f"(${args.alt_price:,.0f} / {args.alt_life:g}y)")
            print(f"Durable over horizon   {d_total:>8,.0f}  "
                  f"({d_buys} purchases)")
            print(f"Cheap over horizon     {c_total:>8,.0f}  "
                  f"({c_buys} purchases)")
            if be is not None:
                print(f"Break-even             year {be}")
        print(f"Verdict: {verdict}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
