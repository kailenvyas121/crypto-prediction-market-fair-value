"""Retail attention proxy: daily English-Wikipedia pageviews of the Bitcoin article (Wikimedia REST API)."""

from __future__ import annotations

import pandas as pd

from pinpricer.config import RAW_DIR, study_window
from pinpricer.data import store
from pinpricer.data.http import HttpClient

URL = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/"
       "{article}/daily/{start}/{end}")


def run(articles: tuple[str, ...] = ("Bitcoin", "Cryptocurrency")) -> None:
    start, end = study_window(with_warmup=True)
    http = HttpClient(rate=2)
    out = RAW_DIR / "attention"
    for a in articles:
        d = http.get_json(URL.format(article=a, start=start.strftime("%Y%m%d"), end=end.strftime("%Y%m%d")))
        df = pd.DataFrame([{"date": pd.Timestamp(x["timestamp"][:8], tz="UTC"), "views": x["views"]}
                           for x in d["items"]])
        store.write_part(df, out, f"wikipedia_{a}")
        print(f"wikipedia {a}: {len(df)} days")
