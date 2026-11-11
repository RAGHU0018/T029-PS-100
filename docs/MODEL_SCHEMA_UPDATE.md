# Model schema alignment — PS-100 sample data

The domain models have been updated to represent the official sample-data fields.

## Key mappings
- Zone: `zone_name`, `severity_level`, `road_status`, `serving_depot_id`.
- Camp: `camp_name`, `children`, `elderly`, `pregnant`, `opened_ts`; `vulnerable_count` is derived from the three categories when supplied.
- Item: `unit_weight_kg`; CSV-facing aliases are available for `item_name`, `daily_norm_per_person`, and `priority_class`.
- Vehicle: capacity is represented in kilograms, and CSV driver/duty fields are supported. Specs: truck 5000 kg / 30 km/h, boat 1000 kg / 20 km/h, helicopter 2000 kg / 120 km/h.
- StockBatch: `source` supports `GOVT` and `DONATION`; opening stock can omit `received_at` because that column is absent from `stock_batches.csv`.
- Request: `stock_on_hand` and CSV-facing aliases `qty` and `request_ts`.
- Delivery: `trip_id` and delivery CSV quantities are supported. Discrepancy reconciliation must compare the delivery row against its planned manifest because the deliveries CSV does not contain dispatched quantity.
- Depot: `depot_name` is supported.

## Timestamp convention
The sample pack timestamps are local IST values without an offset. Keep parsing/localization in the future CSV loading layer (interpret as `Asia/Kolkata`) before passing timestamps into models that require timezone-aware datetimes. `Camp.opened_ts` is currently accepted as a datetime and can hold the localized value.

## Validation
Run `python -m pytest tests -v` from the project root.
