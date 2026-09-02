import io
import json
from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

AMFI_URL = (
    "https://portal.amfiindia.com/spages/"
    "AverageMarketCapitalization30Jun2026.xlsx"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
}


# =========================================================
# HELPERS
# =========================================================

def load_json(path, default):
    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return default


def safe_float(value):
    try:
        if value is None:
            return None

        number = float(value)

        if pd.isna(number):
            return None

        return number

    except Exception:
        return None


def normalize_category(value, rank):
    """
    Dashboard classification:

    Rank 1-100   = Large Cap
    Rank 101-250 = Mid Cap
    Rank 251-500 = Small Cap
    Rank 501+    = Micro Cap

    AMFI category is used where available.
    Rank is used as fallback / Micro Cap split.
    """

    text = str(
        value or ""
    ).strip().lower()

    if "large" in text:
        return "Large Cap"

    if "mid" in text:
        return "Mid Cap"

    if "small" in text:

        if (
            rank is not None
            and rank >= 501
        ):
            return "Micro Cap"

        return "Small Cap"

    # -----------------------------------------------------
    # FALLBACK USING RANK
    # -----------------------------------------------------

    if rank is not None:

        if rank <= 100:
            return "Large Cap"

        if rank <= 250:
            return "Mid Cap"

        if rank <= 500:
            return "Small Cap"

        return "Micro Cap"

    return None


# =========================================================
# MAIN
# =========================================================

def main():

    stocks_path = (
        DATA /
        "stocks.json"
    )

    stocks = load_json(
        stocks_path,
        []
    )

    if not isinstance(
        stocks,
        list
    ):
        raise RuntimeError(
            "stocks.json must contain a list"
        )


    # =====================================================
    # DOWNLOAD AMFI MARKET CAP FILE
    # =====================================================

    print(
        "Downloading AMFI market-cap classification file..."
    )

    response = requests.get(
        AMFI_URL,
        headers=HEADERS,
        timeout=60,
    )

    response.raise_for_status()


    # =====================================================
    # FIND HEADER ROW
    # =====================================================

    excel = pd.read_excel(
        io.BytesIO(
            response.content
        ),
        sheet_name=0,
        header=None,
    )

    header_row = None


    for i in range(
        min(
            25,
            len(excel)
        )
    ):

        row_text = " ".join(
            str(x)
            for x
            in excel.iloc[i].tolist()
        ).lower()

        if (
            "isin" in row_text
            and
            "categor" in row_text
        ):
            header_row = i
            break


    if header_row is None:

        raise RuntimeError(
            "AMFI header row not found"
        )


    # =====================================================
    # READ AMFI DATA
    # =====================================================

    df = pd.read_excel(
        io.BytesIO(
            response.content
        ),
        sheet_name=0,
        header=header_row,
    )

    df.columns = [
        str(c).strip()
        for c in df.columns
    ]


    # =====================================================
    # IDENTIFY COLUMNS
    # =====================================================

    isin_col = None
    category_col = None
    rank_col = None
    market_cap_col = None


    for col in df.columns:

        low = (
            str(col)
            .strip()
            .lower()
        )


        # -------------------------------------------------
        # ISIN
        # -------------------------------------------------

        if (
            isin_col is None
            and "isin" in low
        ):
            isin_col = col


        # -------------------------------------------------
        # CATEGORY
        # -------------------------------------------------

        if (
            category_col is None
            and "categor" in low
        ):
            category_col = col


        # -------------------------------------------------
        # RANK
        # -------------------------------------------------

        if (
            rank_col is None
            and
            (
                "sr. no" in low
                or
                "sr no" in low
                or
                low == "rank"
                or
                "ranking" in low
            )
        ):
            rank_col = col


        # -------------------------------------------------
        # AMFI AVERAGE MARKET CAPITALISATION
        # -------------------------------------------------

        if (
            market_cap_col is None
            and
            (
                (
                    "market" in low
                    and
                    "cap" in low
                )
                or
                "mcap" in low
            )
        ):
            market_cap_col = col


    if isin_col is None:

        raise RuntimeError(
            "ISIN column not found"
        )


    if category_col is None:

        raise RuntimeError(
            "Category column not found"
        )


    if market_cap_col is None:

        print(
            "WARNING: "
            "AMFI average market-cap column "
            "not identified."
        )


    print(
        {
            "isinColumn":
                isin_col,

            "categoryColumn":
                category_col,

            "rankColumn":
                rank_col,

            "amfiAverageMarketCapColumn":
                market_cap_col,
        }
    )


    # =====================================================
    # BUILD AMFI ISIN MAP
    # =====================================================

    amfi_by_isin = {}


    for _, record in df.iterrows():

        isin = str(
            record.get(
                isin_col,
                ""
            )
        ).strip()


        if (
            not isin
            or
            isin.lower() == "nan"
        ):
            continue


        # -------------------------------------------------
        # RANK
        # -------------------------------------------------

        rank = None


        if rank_col is not None:

            try:

                rank_value = safe_float(
                    record.get(
                        rank_col
                    )
                )

                if rank_value is not None:
                    rank = int(
                        rank_value
                    )

            except Exception:
                rank = None


        # -------------------------------------------------
        # CATEGORY
        # -------------------------------------------------

        category = normalize_category(
            record.get(
                category_col
            ),
            rank,
        )


        # -------------------------------------------------
        # AMFI 6-MONTH AVERAGE MARKET CAP
        #
        # IMPORTANT:
        #
        # THIS IS NOT CURRENT MARKET CAP.
        #
        # Therefore it must NEVER be saved as
        # row["marketCapCr"].
        # -------------------------------------------------

        amfi_average_market_cap_cr = None


        if market_cap_col is not None:

            amfi_average_market_cap_cr = (
                safe_float(
                    record.get(
                        market_cap_col
                    )
                )
            )


        amfi_by_isin[
            isin
        ] = {

            "category":
                category,

            "rank":
                rank,

            "amfiAverageMarketCapCr":
                amfi_average_market_cap_cr,
        }


    # =====================================================
    # APPLY AMFI CLASSIFICATION TO STOCKS.JSON
    # =====================================================

    matched = 0
    average_market_cap_matched = 0


    counts = {

        "Large Cap": 0,
        "Mid Cap": 0,
        "Small Cap": 0,
        "Micro Cap": 0,

    }


    for row in stocks:

        isin = str(
            row.get(
                "isin"
            )
            or ""
        ).strip()


        info = (
            amfi_by_isin
            .get(isin)
        )


        # -------------------------------------------------
        # REMOVE OLD / WRONG CURRENT MARKET CAP
        # -------------------------------------------------
        #
        # Previous version stored AMFI average market cap
        # inside marketCapCr.
        #
        # That number looked like CURRENT market cap on
        # the website, which is incorrect.
        #
        # Until a genuine current market-cap source is
        # connected, marketCapCr stays None.
        # -------------------------------------------------

        row[
            "marketCapCr"
        ] = None


        # -------------------------------------------------
        # NO AMFI MATCH
        # -------------------------------------------------

        if not info:

            row[
                "marketCapCategory"
            ] = None

            row[
                "marketCapRank"
            ] = None

            row[
                "amfiAverageMarketCapCr"
            ] = None

            row[
                "marketCapSource"
            ] = None

            continue


        # -------------------------------------------------
        # AMFI MATCH
        # -------------------------------------------------

        category = info.get(
            "category"
        )

        rank = info.get(
            "rank"
        )

        amfi_average_market_cap_cr = (
            info.get(
                "amfiAverageMarketCapCr"
            )
        )


        row[
            "marketCapCategory"
        ] = category


        row[
            "marketCapRank"
        ] = rank


        row[
            "amfiAverageMarketCapCr"
        ] = (

            round(
                amfi_average_market_cap_cr,
                2
            )

            if
            amfi_average_market_cap_cr
            is not None

            else None
        )


        row[
            "marketCapSource"
        ] = (
            "AMFI Average Market Capitalisation "
            "30-Jun-2026"
        )


        matched += 1


        if (
            amfi_average_market_cap_cr
            is not None
        ):
            average_market_cap_matched += 1


        if category:

            counts[
                category
            ] = (
                counts.get(
                    category,
                    0
                )
                +
                1
            )


    # =====================================================
    # SAVE STOCKS.JSON
    # =====================================================

    stocks_path.write_text(

        json.dumps(
            stocks,
            ensure_ascii=False,
            separators=(
                ",",
                ":"
            ),
        ),

        encoding="utf-8",

    )


    # =====================================================
    # LOG
    # =====================================================

    print()

    print(
        "=============================================="
    )

    print(
        "MARKET CAP CLASSIFICATION COMPLETE"
    )

    print(
        "=============================================="
    )

    print(
        {
            "stocks":
                len(stocks),

            "amfiMatched":
                matched,

            "amfiAverageMarketCapMatched":
                average_market_cap_matched,

            "categoryCounts":
                counts,

            "currentMarketCapCr":
                "NOT POPULATED",

            "reason":
                (
                    "AMFI value is historical "
                    "6-month average market cap, "
                    "not current market cap"
                ),

            "source":
                (
                    "AMFI Average Market "
                    "Capitalisation 30-Jun-2026"
                ),
        }
    )

    print()

    print(
        "IMPORTANT:"
    )

    print(
        "marketCapCr = None"
    )

    print(
        "amfiAverageMarketCapCr = AMFI average value"
    )

    print(
        "marketCapCategory = AMFI/rank classification"
    )

    print(
        "marketCapRank = AMFI rank"
    )

    print(
        "=============================================="
    )


if __name__ == "__main__":
    main()
