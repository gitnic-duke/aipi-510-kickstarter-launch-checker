"""Transform + validate (task T5): keep successful/failed campaigns, drop leaky
post-launch columns, build launch-day features, run data quality checks, and
write gs://<bucket>/processed/vN/kickstarter.parquet plus _meta.json.
A change to cleaning logic = a new version folder; never overwrite."""
