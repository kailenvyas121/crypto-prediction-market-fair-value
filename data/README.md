# data/

Local cache, gitignored. Rebuild with `make data`. See `docs/DATA.md` for every dataset's source, schema and size.

```
raw/        API responses as pulled (parquet), partitioned by source
interim/    cleaned and joined (e.g. USD spot composite)
processed/  model-ready panels (e.g. calibration panel)
```
