#!/usr/bin/env python3
"""Market Daily Report: Fetch market data, analyze indicators, and generate HTML report.

This script fetches price data and news for Nikkei 225, S&P 500, and BTC/USD,
computes technical indicators, and generates a styled HTML report for GitHub Pages.
"""

import os
import traceback

import config
import data
import indicators
import report


def main():
    """Main entry point: fetch data, compute indicators, generate report."""
    results = []

    for asset in config.ASSETS:
        try:
            print(f"Fetching {asset['name']} ...")

            # Fetch price data
            if asset["btc"]:
                df = data.fetch_btc()
            else:
                df = data.fetch_yfinance(asset["ticker"])

            # Compute technical indicators and fetch news
            ind = indicators.compute_indicators(df)
            evidence = indicators.generate_evidence(ind, asset["name"])
            chart = indicators.chart_data(df)
            news = data.fetch_news(asset["name"])

            results.append({
                **asset,
                "indicators": ind,
                "evidence": evidence,
                "chart": chart,
                "news": news,
            })

            print(f"  -> {asset['name']}: {ind['latest']:,.2f} ({ind['change_pct']:+.2f}%) | {len(news)} news items")

        except Exception:
            print(f"ERROR fetching {asset['name']}:")
            traceback.print_exc()

    # Generate HTML report
    if not results:
        print("All fetches failed. Keeping existing index.html.")
        return

    report_html = report.build_html(results)
    output_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_html)
    print(f"\nGenerated: {output_path}")


if __name__ == "__main__":
    main()
