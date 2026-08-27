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
            path.read_text()
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


def normalize_category(
    value,
    rank
):
    text = str(
        value or ""
    ).strip().lower()

    if "large" in text:
        return "Large Cap"

    if "mid" in text:
        return "Mid Cap"

    if "small" in text:

        # Dashboard custom classification:
        #
        # Rank 1-100   = Large Cap
        # Rank 101-250 = Mid Cap
        # Rank 251-500 = Small Cap
        # Rank 501+    = Micro Cap

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


    # =====================================================
    # DOWNLOAD AMFI MARKET CAP FILE
    # =====================================================

    response = requests.get(
        AMFI_URL,
        headers=HEADERS,
        timeout=60,
    )

    response.raise_for_status()


    raw_excel = (
        io.BytesIO(
            response.content
        )
    )


    # =====================================================
    # FIND HEADER ROW
    # =====================================================

    excel = pd.read_excel(
        raw_excel,
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


    # Need fresh BytesIO because
    # pandas has already read previous stream.

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
            and
            "isin" in low
        ):
            isin_col = col


        # -------------------------------------------------
        # CATEGORY
        # -------------------------------------------------

        if (
            category_col is None
            and
            "categor" in low
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
        # MARKET CAPITALISATION
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
            "Market-cap value column "
            "not identified in AMFI file."
        )


    print({
        "isinColumn":
            isin_col,

        "categoryColumn":
            category_col,

        "rankColumn":
            rank_col,

        "marketCapColumn":
            market_cap_col,
    })


    # =====================================================
    # BUILD ISIN MAP
    # =====================================================

    market_cap_by_isin = {}


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

                rank = int(
                    float(
                        record.get(
                            rank_col
                        )
                    )
                )

            except Exception:
                rank = None


        # -------------------------------------------------
        # CATEGORY
        # -------------------------------------------------

        category = (
            normalize_category(
                record.get(
                    category_col
                ),
                rank,
            )
        )


        # -------------------------------------------------
        # ACTUAL MARKET CAP ₹ CR
        # -------------------------------------------------

        market_cap_cr = None


        if market_cap_col is not None:

            market_cap_cr = (
                safe_float(
                    record.get(
                        market_cap_col
                    )
                )
            )


        market_cap_by_isin[
            isin
        ] = {

            "category":
                category,

            "marketCapCr":
                market_cap_cr,

            "marketCapRank":
                rank,
        }


    # =====================================================
    # APPLY TO STOCKS.JSON
    # =====================================================

    matched = 0

    market_cap_value_matched = 0


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
            market_cap_by_isin
            .get(isin)
        )


        # -------------------------------------------------
        # NO MATCH
        # -------------------------------------------------

        if not info:

            row[
                "marketCapCategory"
            ] = None

            row[
                "marketCapCr"
            ] = None

            row[
                "marketCapRank"
            ] = None

            continue


        category = (
            info.get(
                "category"
            )
        )


        market_cap_cr = (
            info.get(
                "marketCapCr"
            )
        )


        rank = (
            info.get(
                "marketCapRank"
            )
        )


        row[
            "marketCapCategory"
        ] = category


        row[
            "marketCapCr"
        ] = (

            round(
                market_cap_cr,
                2
            )

            if market_cap_cr
            is not None

            else None
        )


        row[
            "marketCapRank"
        ] = rank


        matched += 1


        if (
            market_cap_cr
            is not None
        ):
            market_cap_value_matched += 1


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
    # SAVE
    # =====================================================

    stocks_path.write_text(

        json.dumps(
            stocks,
            ensure_ascii=False,
            separators=(
                ",",
                ":"
            ),
        )

    )


    # =====================================================
    # LOG
    # =====================================================

    print({

        "stocks":
            len(stocks),

        "marketCapMatched":
            matched,

        "marketCapValueMatched":
            market_cap_value_matched,

        "categoryCounts":
            counts,

        "source":
            "AMFI Average Market Capitalisation",

    })


if __name__ == "__main__":
    main()
