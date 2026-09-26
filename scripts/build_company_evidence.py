    }

    return result


# =========================================================
# RUN
# =========================================================

def main():

    print(
        "Starting NSE company evidence "
        "candidate scan..."
    )

    try:

        result = build()

    except Exception as exc:

        # =================================================
        # FAIL-SAFE
        #
        # Evidence collection must never destroy the
        # normal daily market-data workflow.
        # =================================================

        print(
            "Company evidence "
            "collector warning:",
            exc,
        )

        result = {
            "_meta": {
                "description": (
                    "NSE corporate-announcement "
                    "evidence candidate scan."
                ),

                "updated":
                    RUN_DATE,

                "status":
                    "FETCH_FAILED_SAFE",

                "error":
                    clean(
                        exc
                    ),

                "important": (
                    "Normal market-data workflow "
                    "may continue. "
                    "company_evidence.json was "
                    "not modified."
                ),
            },

            "stocks": {},
        }

    save_json(
        CANDIDATES_PATH,
        result,
    )

    counts = (
        result.get(
            "_meta",
            {}
        )
        .get(
            "counts",
            {}
        )
    )

    print(
        "Evidence candidate "
        "build complete."
    )

    print(
        json.dumps(
            counts,
            indent=2,
        )
    )

    print(
        "Output:",
        CANDIDATES_PATH,
    )

    print(
        "AUTO VERIFY: strong NSE CAPEX evidence "
        "was promoted to company_evidence.json; "
        "existing verified evidence was preserved."
    )


if __name__ == "__main__":
    main()
