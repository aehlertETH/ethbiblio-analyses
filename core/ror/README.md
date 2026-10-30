# Central ROR Assets

This folder centralizes shared ROR source data used by geo assets.

## Canonical Source

- Put the official ROR full dump zip in this folder (for example from Zenodo).
- The canonical source is a `*.zip` dump containing flattened CSV/JSON.
- Example source used in this project: `https://zenodo.org/records/18985120`.

## Lookup Policy

Assets resolve institution coordinates in this order:

1. Asset-local derived cache (`assets/<asset>/ror_geo_cache.csv`)
2. Central full dump (`core/ror/*.zip`)
3. ROR API (`https://api.ror.org/v2/organizations/<ror_id>`)

If specific institution IDs/RORs are missing in the dump, scripts log that and can fall back to API.

## Force Modes and Controls (env vars)

Configured centrally in `core/asset.py`:

- `ETH_BIBLIO_ROR_RESOLUTION_MODE=auto|dump|api`
- `ETH_BIBLIO_ROR_ALLOW_API_FETCH=true|false`
- `ETH_BIBLIO_ROR_SKIP_MISSING_LOOKUP=true|false`
- `ETH_BIBLIO_ROR_API_SLEEP_SEC=<float_seconds>`

Behavior:

- `auto` (default): local cache -> dump -> API
- `dump`: ignore local cache, rebuild from dump, then API for missing IDs
- `api`: ignore local cache and dump, fetch all requested IDs from API
- `ETH_BIBLIO_ROR_SKIP_MISSING_LOOKUP=true`: do not resolve missing IDs beyond the primary source

Primary source by mode:

- `auto`: asset-local cache chain
- `dump`: central full dump
- `api`: ROR API

`ETH_BIBLIO_ROR_API_SLEEP_SEC` controls the pause between API requests (default `0.05`, minimum `0`).

## Performance Cache

- On first use, `core/ror.py` builds a compact sidecar index next to the dump zip (`<dump>.zip.index.csv`).
- Later runs load this sidecar instead of reparsing the full dump zip, which is much faster.
- Within a single script run, `core/ror.py` memoizes both the asset-local cache and dump lookup in memory, so institution loops do not repeatedly hit disk.
## Notes

- This folder is intended for local data only (outside version control).
- Keep only documentation tracked here; keep dump payloads and derived files untracked.

