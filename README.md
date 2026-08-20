# India Market Intelligence — Free EOD

A zero-monthly-cost, static research dashboard designed for GitHub Pages.

## Included now
- **3,115 NSE securities** from the official NSE Equity + SME master downloaded on 19-Aug-2026.
- Full-universe search with pagination.
- NSE/NSE merge by ISIN.
- Scheduled GitHub Action for NSE and NSE security-master refresh.
- No invented fundamentals or scores: unavailable fields remain `Pending`.

## Why GitHub Pages
Use a **public GitHub repository**. GitHub Pages is available with GitHub Free for public repositories, and standard GitHub-hosted Actions are free for public repositories (subject to GitHub's terms/limits).

## Deployment
1. Create a public GitHub repository.
2. Upload all files from this project.
3. Repository **Settings → Pages → Source: GitHub Actions**.
4. Open **Actions → Update market data → Run workflow** once.
5. The Pages workflow will publish the website.
6. After that, `update-data.yml` runs Monday-Friday after market close.

## Current data policy
The repository ships with current NSE security-master data. NSE is fetched by the scheduled collector from an official NSE API endpoint. If NSE blocks or changes the endpoint, the workflow preserves older NSE rows and reports the failure instead of silently deleting them.

## Signals
The UI has:
- Sector Strength
- Macro Support
- Value Migration
- Future Growth
- Fundamental Quality
- CAPEX
- Overall Score

These remain blank until sufficient reliable source data exists. This is deliberate. A zero-cost source for exchange-wide, structured fundamentals/CAPEX is not guaranteed, so the project does not manufacture those values.

## Future free extensions
- NSE/NSE EOD Bhavcopy importer for price, volume and turnover.
- Relative-strength and sector-strength calculation from EOD history.
- Filing parser for quarterly results and CAPEX disclosures.
- Announcement keyword classifier for capacity expansion/order book/policy tailwinds.

## Important
This is an EOD research website, not a real-time market-data terminal. Verify exchange filings before any investment decision.
