
from pathlib import Path
import inspect
import sys
import pandas as pd
import altair as alt
import duckdb
import matplotlib.pyplot as plt
import seaborn as sns
import yaml
import re
import sys
from pathlib import Path
from typing import Callable


# Auto-detect ROOT and setup sys.path (so other imports work)
_REPO_ROOT = Path(__file__).resolve().parents[0]
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONFIG_PATH = ROOT / "config.yml"

institutions = ['empa', 'epfl', 'psi', 'wsl', 'ethz', 'eawag', 'ethdomain']
institutions_dict = {'71824836':'empa', '5124864':'epfl', '2802229908':'psi', '2800262456':'wsl', '35440088':'ethz', '63664421':'eawag'} # used by scripts in mahmoud for visualization
lazy = False
year_first = 2010
year_last = 2023


def get_unit_params_dict(root_dir: Path | None = None) -> dict:
    base_dir = Path(root_dir) if root_dir is not None else _REPO_ROOT
    path = base_dir / "data" / "unit_params.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Missing unit params at {path}")
    try:
        df = pd.read_csv(path, sep=";", encoding="utf-8-sig")  # handles UTF-8 + Excel BOM
    except UnicodeDecodeError:
        df = pd.read_csv(path, sep=";", encoding="cp1252")

    return df.set_index("InstID").to_dict(orient="index")

def get_indicator_catalog_dict(root_dir: Path | None = None) -> dict:
    base_dir = Path(root_dir) if root_dir is not None else _REPO_ROOT
    path = base_dir / "data" / "indicator_catalog.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Missing indicator catalog at {path}")
    try:
        df = pd.read_csv(path, sep=";", encoding="utf-8-sig")  # handles UTF-8 + Excel BOM
    except UnicodeDecodeError:
        df = pd.read_csv(path, sep=";", encoding="cp1252")

    return df.set_index("indicator_id").to_dict(orient="index")

def get_duckdb_path(config_path: Path = CONFIG_PATH) -> Path:
    if not config_path.is_file():
        raise FileNotFoundError(
            f"Missing config file at {config_path}. "
            "Copy config.example.yml to config.yml and set duckdb_path."
        )

    config = yaml.safe_load(config_path.read_text()) or {}
    duckdb_path = config.get("duckdb_path")

    if not duckdb_path:
        raise ValueError("duckdb_path is missing in config.yml")

    db_path = Path(duckdb_path).expanduser()

    if not db_path.is_absolute():
        raise ValueError("duckdb_path must be an absolute path")

    if not db_path.is_file():
        raise FileNotFoundError(f"duckdb_path does not exist: {db_path}")

    return db_path


def connect_duckdb(read_only: bool = True, config_path: Path = CONFIG_PATH):
    return duckdb.connect(str(get_duckdb_path(config_path)), read_only=read_only)

def asset_base(script_file: str) -> Path:
    p = Path(script_file).resolve()
    try:
        rel = p.parent.relative_to(ROOT)
        if rel.parts[0] == "assets":
            return ROOT / "assets" / rel.parts[1]
    except Exception:
        pass
    return p.parent


def _normalize_lookup_key(text: str | None) -> str:
    if text is None:
        return ""
    key = str(text).strip().lower()
    key = key.replace("\u2019", "'").replace("`", "'").replace("\u00b4", "'")
    key = re.sub(r"\s+", " ", key)
    return key




# Common institution-name abbreviations for compact table displays.
# Keep this as a rendering helper; raw exports should keep full names.
_INSTITUTION_NAME_SHORTENING_MAP: dict[str, str] = {
    # Requested core mappings
    "university": "Univ",
    "universite": "Univ",
    "universit\u00e4t": "Univ",
    "universitat": "Univ",
    "universita": "Univ",
    "universidad": "Univ",
    "institute": "Inst",
    "institut": "Inst",
    "istituto": "Inst",
    "instituto": "Inst",
    "department": "Dept",
    "faculty": "Fac",
    "school": "Sch",
    "college": "Coll",
    "center": "Ctr",
    "centre": "Ctr",
    "laboratory": "Lab",
    "laboratories": "Labs",
    "research": "Res",
    "science": "Sci",
    "sciences": "Sci",
    "technology": "Technol",
    "technical": "Tech",
    "engineering": "Eng",
    "medicine": "Med",
    "medical": "Med",
    "clinical": "Clin",
    "biology": "Biol",
    "chemistry": "Chem",
    "physics": "Phys",
    "mathematics": "Math",
    "computer": "Comput",
    "informatics": "Inform",
    "information": "Inf",
    "systems": "Syst",
    "social": "Soc",
    "sociology": "Sociol",
    "psychology": "Psychol",
    "economics": "Econ",
    "public": "Publ",
    "national": "Natl",
    "international": "Int",
    "federal": "Fed",
    "state": "St",
    "central": "Cent",
    "education": "Educ",
    "environmental": "Environ",
    "hospital": "Hosp",
    "health": "Hlth",
    # Existing useful extensions
    "institution": "Inst",
    "society": "Soc",
    "organization": "Org",
    "organisation": "Org",
    "nuclear": "Nuclr",
    "imperial": "Imp",
    "academy": "Acad",
    "california": "Califor",
    "european": "Eur",
    "bioinformatics": "Bioinf",
    "recherche scientifique": "RS",
    "recherche": "Rech",
    "scientifique": "Scient",
}

_INSTITUTION_NAME_EXACT_ALIASES: dict[str, str] = {
    _normalize_lookup_key("Swiss Federal Laboratories for Materials Science and Technology"): "Empa",
    _normalize_lookup_key("École polytechnique fédérale de Lausanne"): "EPFL",
    _normalize_lookup_key("Ecole polytechnique federale de Lausanne"): "EPFL",
    _normalize_lookup_key("{\\'E}cole polytechnique f{\\'e}d{\\'e}rale de Lausanne"): "EPFL",
    _normalize_lookup_key("Paul Scherrer Institute"): "PSI",
    _normalize_lookup_key("Swiss Federal Institute for Forest, Snow and Landscape Research"): "WSL",
    _normalize_lookup_key("ETH Zurich"): "ETH Zurich",
    _normalize_lookup_key("Swiss Federal Institute of Aquatic Science and Technology"): "Eawag",
    _normalize_lookup_key("ETH Domain"): "ETH Domain",
    _normalize_lookup_key("Massachusetts Institute of Technology"): "MIT",
    _normalize_lookup_key("Centre National de la Recherche Scientifique"): "CNRS",
    _normalize_lookup_key("Commissariat \u00e0 l\u2019\u00c9nergie Atomique et aux \u00c9nergies Alternatives"): "CEA",
    _normalize_lookup_key("Commissariat \u00e0 l'\u00c9nergie Atomique et aux \u00c9nergies Alternatives"): "CEA",
    _normalize_lookup_key("European Organization for Nuclear Research"): "CERN",
    _normalize_lookup_key("California Institute of Technology"): "Caltech",
    _normalize_lookup_key("University of California, Berkeley"): "Univ Calif Berkeley",
    _normalize_lookup_key("University of California Berkeley"): "Univ Calif Berkeley",
    _normalize_lookup_key("Board of the Swiss Federal Institutes of Technology"): "ETH Board",
    _normalize_lookup_key("Ludwig-Maximilians-Universität München"): "LMU Munich",
    _normalize_lookup_key("Technical University of Munich"): "TU Munich",
}

_INSTITUTION_FULL_NAME_EXACT_ALIASES: dict[str, str] = {
    _normalize_lookup_key("Swiss Federal Laboratories for Materials Science and Technology"): "Empa",
    _normalize_lookup_key("École polytechnique fédérale de Lausanne"): "EPFL",
    _normalize_lookup_key("Ecole polytechnique federale de Lausanne"): "EPFL",
    _normalize_lookup_key("{\\'E}cole polytechnique f{\\'e}d{\\'e}rale de Lausanne"): "EPFL",
    _normalize_lookup_key("Paul Scherrer Institute"): "PSI",
    _normalize_lookup_key("Swiss Federal Institute for Forest, Snow and Landscape Research"): "WSL",
    _normalize_lookup_key("ETH Zurich"): "ETH Zurich",
    _normalize_lookup_key("Swiss Federal Institute of Aquatic Science and Technology"): "Eawag",
    _normalize_lookup_key("ETH Domain"): "ETH Domain",
}

_INSTITUTION_NAME_DROP_WORDS: set[str] = {
    "of", "the", "and", "for", "in", "at", "on", "to", "by", "with",
    "de", "du", "des", "la", "le", "les", "del", "della", "dei", "degli",
    "delle", "di", "da", "dos", "das", "van", "von", "der", "den", "und", "et", "y",
}

_COUNTRY_NAME_SHORT_EXACT_ALIASES: dict[str, str] = {
    _normalize_lookup_key("United Kingdom of Great Britain and Northern Ireland"): "United Kingdom",
    _normalize_lookup_key("United States of America"): "USA",
    _normalize_lookup_key("Russian Federation"): "Russia",
    _normalize_lookup_key("Korea, Republic of"): "South Korea",
    _normalize_lookup_key("Korea, Democratic People's Republic of"): "North Korea",
    _normalize_lookup_key("Iran, Islamic Republic of"): "Iran",
    _normalize_lookup_key("Syrian Arab Republic"): "Syria",
    _normalize_lookup_key("Viet Nam"): "Vietnam",
    _normalize_lookup_key("Lao People's Democratic Republic"): "Laos",
    _normalize_lookup_key("Moldova, Republic of"): "Moldova",
    _normalize_lookup_key("Tanzania, United Republic of"): "Tanzania",
    _normalize_lookup_key("Bolivia, Plurinational State of"): "Bolivia",
    _normalize_lookup_key("Venezuela, Bolivarian Republic of"): "Venezuela",
    _normalize_lookup_key("Taiwan, Province of China"): "Taiwan",
    _normalize_lookup_key("Palestine, State of"): "Palestine",
    _normalize_lookup_key("Brunei Darussalam"): "Brunei",
    _normalize_lookup_key("Macedonia, the former Yugoslav Republic of"): "North Macedonia",
    _normalize_lookup_key("Micronesia, Federated States of"): "Micronesia",
    _normalize_lookup_key("Congo, Democratic Republic of the"): "DR Congo",
    _normalize_lookup_key("Democratic Republic of the Congo"): "DR Congo",
    _normalize_lookup_key("Congo"): "Congo",
    _normalize_lookup_key("Czech Republic"): "Czechia",
    _normalize_lookup_key("Türkiye"): "Turkey", #potentially Türkiye see UN 2022 change
    _normalize_lookup_key("Turkey"): "Turkey", #potentially Türkiye see UN 2022 change
}

_COUNTRY_NAME_FULL_EXACT_ALIASES: dict[str, str] = {
    _normalize_lookup_key("United Kingdom of Great Britain and Northern Ireland"): "the United Kingdom",
    _normalize_lookup_key("United Kingdom"): "the United Kingdom",
    _normalize_lookup_key("United States of America"): "the USA",
    _normalize_lookup_key("USA"): "the USA",
    _normalize_lookup_key("Russian Federation"): "the Russian Federation",
    _normalize_lookup_key("Netherlands"): "the Netherlands",
    _normalize_lookup_key("Philippines"): "the Philippines",
    _normalize_lookup_key("Bahamas"): "the Bahamas",
    _normalize_lookup_key("Gambia"): "the Gambia",
    _normalize_lookup_key("Korea, Republic of"): "South Korea",
    _normalize_lookup_key("Korea, Democratic People's Republic of"): "North Korea",
    _normalize_lookup_key("Iran, Islamic Republic of"): "Iran",
    _normalize_lookup_key("Syrian Arab Republic"): "Syria",
    _normalize_lookup_key("Viet Nam"): "Vietnam",
    _normalize_lookup_key("Lao People's Democratic Republic"): "Laos",
    _normalize_lookup_key("Moldova, Republic of"): "Moldova",
    _normalize_lookup_key("Tanzania, United Republic of"): "Tanzania",
    _normalize_lookup_key("Bolivia, Plurinational State of"): "Bolivia",
    _normalize_lookup_key("Venezuela, Bolivarian Republic of"): "Venezuela",
    _normalize_lookup_key("Taiwan, Province of China"): "Taiwan",
    _normalize_lookup_key("Palestine, State of"): "Palestine",
    _normalize_lookup_key("Brunei Darussalam"): "Brunei",
    _normalize_lookup_key("Macedonia, the former Yugoslav Republic of"): "North Macedonia",
    _normalize_lookup_key("Micronesia, Federated States of"): "Micronesia",
    _normalize_lookup_key("Congo, Democratic Republic of the"): "the Democratic Republic of the Congo",
    _normalize_lookup_key("Democratic Republic of the Congo"): "the Democratic Republic of the Congo",
    _normalize_lookup_key("Congo"): "the Republic of the Congo",
    _normalize_lookup_key("Holy See"): "the Holy See",
    _normalize_lookup_key("Czech Republic"): "the Czech Republic",
    _normalize_lookup_key("Türkiye"): "Turkey", #potentially Türkiye see UN 2022 change
}


def _word_pattern(term: str) -> str:
    return rf"\b{re.escape(term)}\b"


def shorten_institution_name(
    name: str | None,
    extra_rules: dict[str, str] | list[tuple[str, str]] | None = None,
    drop_words: set[str] | None = None,
) -> str:
    """
    Shorten institution names for display in width-constrained assets.

    - Uses case-insensitive whole-word substitutions.
    - Removes common connector words (drop words).
    - Leaves source data untouched; apply only at render time.
    - `extra_rules` can be a dict of word->abbr or regex-style tuples.
    """
    if name is None:
        return ""

    out = str(name).strip()
    if not out:
        return out

    exact_alias = _INSTITUTION_NAME_EXACT_ALIASES.get(_normalize_lookup_key(out))
    if exact_alias:
        return exact_alias

    word_map = {k.lower(): v for k, v in _INSTITUTION_NAME_SHORTENING_MAP.items()}
    regex_rules: list[tuple[str, str]] = []

    # Backward-compatible support for old tuple-based regex rules.
    if extra_rules:
        if isinstance(extra_rules, dict):
            word_map.update({str(k).lower(): str(v) for k, v in extra_rules.items()})
        else:
            for left, right in extra_rules:
                key = str(left)
                val = str(right)
                if re.search(r"[\\\[\]\(\)\?\+\*\{\}\|]", key):
                    regex_rules.append((key, val))
                else:
                    word_map[key.lower()] = val

    # Replace longer terms first to avoid partial overlaps.
    for term in sorted(word_map.keys(), key=len, reverse=True):
        out = re.sub(_word_pattern(term), word_map[term], out, flags=re.IGNORECASE)

    # Remove connector words.
    drops = set(_INSTITUTION_NAME_DROP_WORDS)
    if drop_words:
        drops.update({str(w).lower() for w in drop_words})
    for term in sorted(drops, key=len, reverse=True):
        out = re.sub(_word_pattern(term), " ", out, flags=re.IGNORECASE)

    # Optional extra regex substitutions.
    for pattern, replacement in regex_rules:
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)

    # Cleanup spacing/punctuation artifacts.
    out = re.sub(r"\s+([,;:/\)])", r"\1", out)
    out = re.sub(r"([\(])\s+", r"\1", out)
    out = re.sub(r"\s{2,}", " ", out)
    out = out.strip(" ,;:/")
    return out


def shorten_country_name(
    name: str | None,
    extra_aliases: dict[str, str] | None = None,
) -> str:
    """
    Apply exact country display aliases (no token-based shortening).
    """
    if name is None:
        return ""

    out = str(name).strip()
    if not out:
        return out

    alias_map = dict(_COUNTRY_NAME_SHORT_EXACT_ALIASES)
    if extra_aliases:
        alias_map.update({_normalize_lookup_key(k): str(v) for k, v in extra_aliases.items()})

    return alias_map.get(_normalize_lookup_key(out), out)


def full_institution_name(
    name: str | None,
    extra_aliases: dict[str, str] | None = None,
) -> str:
    """
    Return the institution name for full-name lookup surfaces.
    """
    if name is None:
        return ""

    out = str(name).strip()
    if not out:
        return out

    alias_map = dict(_INSTITUTION_FULL_NAME_EXACT_ALIASES)
    if extra_aliases:
        alias_map.update({_normalize_lookup_key(k): str(v) for k, v in extra_aliases.items()})

    return alias_map.get(_normalize_lookup_key(out), out)


def full_country_name(
    name: str | None,
    extra_aliases: dict[str, str] | None = None,
) -> str:
    """
    Return a prose-ready country display name, including a leading article where idiomatic.
    """
    if name is None:
        return ""

    out = str(name).strip()
    if not out:
        return out

    alias_map = dict(_COUNTRY_NAME_FULL_EXACT_ALIASES)
    if extra_aliases:
        alias_map.update({_normalize_lookup_key(k): str(v) for k, v in extra_aliases.items()})

    return alias_map.get(_normalize_lookup_key(out), out)


# Alias for readability in some assets.
abbreviate_institution_name = shorten_institution_name
abbreviate_country_name = shorten_country_name
expand_country_name = full_country_name




