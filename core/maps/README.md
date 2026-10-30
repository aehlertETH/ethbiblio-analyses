# Central Map Assets

This folder centralizes shared map files used by reporting assets.

## Lookup policy

Assets should resolve map files in this order:

1. Asset-local folder (`assets/<asset_name>/...`) for self-contained portability.
2. Central fallback folder (`core/maps/...`).

Assets must not depend on map files stored in other asset folders.

## Files in this directory

- `ne_50m_admin_0_countries.zip`
- `ne_110m_admin_0_countries.zip`
- `swissBOUNDARIES3D_1_5_LV95_LN02.gpkg`

## Notes

- Keep canonical shared map datasets here to avoid duplication across assets.
- If a specific asset needs to be shipped standalone, copy only the required map file(s) into that asset folder.
