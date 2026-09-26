                )
            )
            if num(
                row.get(
                    "bigMoveScore"
                )
            )
            is not None
            else -1
        ),
        reverse=True,
    )

    market_date = detect_market_date(
        stocks
    )

    summary = build_summary(
        rows
    )

    now = (
        datetime.now(
            timezone.utc
        )
        .replace(
            microsecond=0
        )
        .isoformat()
    )

    output = {
        "marketDate":
            market_date,

        "generatedAt":
            now,

        "scannerVersion":
            "2.2",

        "methodology": {
            "phase1":
                (
                    "RS + Stock Momentum + Industry Rating + "
                    "multi-period price strength + existing "
                    "fundamental/business triggers."
                ),

            "structuralTriggers":
                (
                    "Structural triggers are display-only and require a "
                    "theme keyword plus company-specific action/impact "
                    "evidence in the same research fragment. They do not "
                    "add points to Big Move Score."
                ),

            "technical":
                (
                    "Technical fields are added by "
                    "build_big_move_technical.py after this step."
                ),

            "freeFloat":
                (
                    "Free Float Shares and Free Float % are carried "
                    "from build_free_float.py. Free Float Shares are "
                    "filing-derived Public Shares less locked-in "
                    "Public Shares; not estimated from Market Cap / Price."
                ),

            "freeFloatScore":
                (
                    "Free Float is currently displayed/filterable but "
                    "NOT yet included in Big Move Score. Thresholds will "
                    "be calibrated after coverage/distribution validation."
                ),
        },

        "summary":
            summary,

        "rows":
            rows,
    }

    save_json(
        OUTPUT_PATH,
        output,
    )

    print({
        "stocksInput":
            len(stocks),

        "scannerRows":
            len(rows),

        "skipped":
            skipped,

        "score80Plus":
            summary[
                "score80Plus"
            ],

        "triggerPresent":
            summary[
                "triggerPresent"
            ],

        "freeFloatReady":
            summary[
                "freeFloatReady"
            ],

        "marketDate":
            market_date,
    })

    print(
        "Saved:"
    )

    print(
        OUTPUT_PATH
    )

    print()
    print(
        "IMPORTANT:"
    )
    print(
        "Free Float is NOT included in Big Move Score yet."
    )
    print(
        "build_big_move_technical.py runs after this file and "
        "adds technical score / breakout / consolidation fields."
    )
    print(
        "=============================================="
    )


if __name__ == "__main__":
    main()
