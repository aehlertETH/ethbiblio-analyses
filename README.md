# Open Bibliometric Study of the ETH Domain (2014–2023): Analyses

This repository contains the Python source code, a configuration example, small
reference data, and map files used to generate tables and figures for the ETH
Domain bibliometric reports. A compatible local DuckDB data warehouse is
required to run the assets.

## Included and excluded material

Included are 44 asset scripts, their shared Python modules, the indicator and
unit catalogues, ROR coordinate caches, and shared
map data.

The repository deliberately excludes generated asset outputs, the local DuckDB
database, local configuration, raw Web of Science exports, execution logs, and
snapshot manifests. The Web of Science comparison asset remains as source code;
its licensed inputs must be supplied separately. See
[`data/wos_exports/README.md`](data/wos_exports/README.md).

## Set up

Install Git and Python, then clone the repository.

### macOS and Linux

```bash
git clone https://github.com/aehlertETH/ethbiblio-analyses.git
cd ethbiblio-analyses
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements.maps.txt
cp config.example.yml config.yml
```

### Windows PowerShell

```powershell
git clone https://github.com/aehlertETH/ethbiblio-analyses.git
cd ethbiblio-analyses
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements.maps.txt
Copy-Item config.example.yml config.yml
```

In Command Prompt, activate the environment with
`.venv\Scripts\activate.bat` and copy the configuration with
`copy config.example.yml config.yml`.

Set `duckdb_path` in `config.yml` to the absolute path of a compatible local
DuckDB data warehouse. Do not commit `config.yml` or the database file.

## Run assets

Run an individual asset from the repository root:

```bash
python -m assets.1_2_bibliometricPerformanceTrendTableShort.script
```

Run the complete public asset set:

```bash
python scripts/run_assets.py run
```

The runner intentionally skips the Web of Science comparison asset because its
licensed source exports are not distributed in this repository. It records
status and logs in `.asset-run/` and supports `--resume`, `--retry-failed`, and
`--skip-existing`.

## Citation and licence

The repository's own code and documentation are licensed under the
[MIT License](LICENSE). Citation metadata are provided in
[`CITATION.cff`](CITATION.cff). The analyses use a compatible local DuckDB
data warehouse built by the associated ETH Domain data-warehouse pipeline:
https://doi.org/10.5281/zenodo.23728218.

Included third-party data retain their own terms and acknowledgements; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
