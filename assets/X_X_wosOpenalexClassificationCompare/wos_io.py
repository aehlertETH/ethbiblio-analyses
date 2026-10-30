"""
WoS savedrecs parser and coverage bridge loader.

Handles two export formats:
  - Tab-delimited (.txt with header row starting PT\tAU...)
  - Tagged plaintext (.txt with two-char field tags ending with ER)
"""

import ast
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd


def normalize_doi(raw: str | None) -> str | None:
    if raw is None or pd.isna(raw):
        return None
    d = str(raw).strip().lower()
    if not d or d in {"nan", "none", "null"}:
        return None
    for prefix in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/", "doi:"):
        d = d.replace(prefix, "")
    d = d.strip()
    match = re.search(r"10\.\d{4,9}/\S+", d)
    if not match:
        return None
    return match.group(0).rstrip(".,;)")


def _is_tab_delimited(path: Path) -> bool:
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        first_line = f.readline()
    return "\t" in first_line and first_line.strip().startswith("PT")


def _parse_tab_delimited(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t", dtype=str, encoding="utf-8-sig")
    cols_map = {
        "UT": "ut",
        "DI": "doi_raw",
        "PY": "wos_year",
        "DT": "document_type",
        "TI": "title",
        "SO": "source",
        "WC": "wos_categories",
    }
    out = pd.DataFrame()
    for src, dst in cols_map.items():
        out[dst] = df[src] if src in df.columns else None
    out["source_file"] = path.name
    return out


def _parse_tagged(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    records = []
    for block in re.split(r"\nER\s*\n", text):
        block = block.strip()
        if not block:
            continue
        rec: dict[str, str] = {}
        current_tag = None
        current_val: list[str] = []
        for line in block.splitlines():
            if len(line) >= 3 and line[2] == " " and line[:2].isalpha():
                if current_tag:
                    rec[current_tag] = " ".join(current_val).strip()
                current_tag = line[:2]
                current_val = [line[3:]]
            elif line.startswith("   ") and current_tag:
                current_val.append(line.strip())
        if current_tag:
            rec[current_tag] = " ".join(current_val).strip()
        if rec:
            records.append(rec)
    return records


def _parse_tagged_file(path: Path) -> pd.DataFrame:
    records = _parse_tagged(path)
    rows = []
    for r in records:
        rows.append({
            "ut": r.get("UT"),
            "doi_raw": r.get("DI"),
            "wos_year": r.get("PY"),
            "document_type": r.get("DT"),
            "title": r.get("TI"),
            "source": r.get("SO"),
            "wos_categories": r.get("WC"),
            "source_file": path.name,
        })
    return pd.DataFrame(rows)


def load_wos_folder(folder: Path) -> pd.DataFrame:
    """
    Load all savedrecs .txt files from a folder, auto-detecting format.
    Returns a DataFrame with normalized columns and deduplicated records.
    """
    txt_files = sorted(folder.glob("*.txt"))
    if not txt_files:
        return pd.DataFrame()

    frames = []
    for p in txt_files:
        if _is_tab_delimited(p):
            frames.append(_parse_tab_delimited(p))
        else:
            frames.append(_parse_tagged_file(p))

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined["doi_norm"] = combined["doi_raw"].apply(normalize_doi)

    n_before = len(combined)
    combined = combined.drop_duplicates(subset="ut", keep="first")
    n_after = len(combined)
    if n_before > n_after:
        print(f"    Deduped {n_before - n_after} duplicate UT records")

    return combined


def _xlsx_sheet_path(xlsx_path: Path, sheet_name: str) -> str:
    workbook_ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rels_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
    rel_attr = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

    with zipfile.ZipFile(xlsx_path) as z:
        workbook = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))

    rel_targets = {
        rel.attrib["Id"]: rel.attrib["Target"].lstrip("/")
        for rel in rels.findall("r:Relationship", rels_ns)
    }
    for sheet in workbook.findall("m:sheets/m:sheet", workbook_ns):
        if sheet.attrib.get("name") == sheet_name:
            target = rel_targets[sheet.attrib[rel_attr]]
            return target if target.startswith("xl/") else f"xl/{target}"
    raise ValueError(f"{xlsx_path}: sheet not found: {sheet_name}")


def _cell_column(cell_ref: str) -> str:
    return re.sub(r"[^A-Z]", "", cell_ref.upper())


def _cell_text(cell, ns: dict[str, str]) -> str | None:
    if cell.attrib.get("t") == "inlineStr":
        parts = [t.text or "" for t in cell.findall(".//m:t", ns)]
        return "".join(parts)
    value = cell.find("m:v", ns)
    return value.text if value is not None else None


def _read_records_sheet_xlsx(xlsx_path: Path) -> pd.DataFrame:
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    row_tag = f"{{{ns['m']}}}row"
    target_names = {"dois", "openalex_work_id"}
    sheet_path = _xlsx_sheet_path(xlsx_path, "records")
    header_by_col: dict[str, str] = {}
    target_cols: dict[str, str] = {}
    rows = []

    with zipfile.ZipFile(xlsx_path) as z:
        with z.open(sheet_path) as f:
            for _, elem in ET.iterparse(f, events=("end",)):
                if elem.tag != row_tag:
                    continue

                values = {}
                for cell in elem.findall("m:c", ns):
                    col = _cell_column(cell.attrib.get("r", ""))
                    if col:
                        values[col] = _cell_text(cell, ns)

                row_num = int(elem.attrib.get("r", "0"))
                if row_num == 1:
                    header_by_col = {col: str(value or "") for col, value in values.items()}
                    target_cols = {
                        col: name
                        for col, name in header_by_col.items()
                        if name in target_names
                    }
                else:
                    rows.append({name: values.get(col) for col, name in target_cols.items()})

                elem.clear()

    return pd.DataFrame(rows, columns=sorted(target_names))


def load_coverage_bridge(xlsx_path: Path) -> pd.DataFrame:
    """
    Load the DOI → work_id bridge from a coverage xlsx file.
    Returns DataFrame with columns: doi_norm, work_id
    """
    try:
        df = pd.read_excel(xlsx_path, sheet_name="records", dtype=str)
    except ImportError:
        df = _read_records_sheet_xlsx(xlsx_path)

    def extract_dois(dois_str):
        if pd.isna(dois_str) or not str(dois_str).strip():
            return []
        try:
            dois = ast.literal_eval(dois_str)
        except (ValueError, SyntaxError):
            dois = [dois_str]
        if not isinstance(dois, list):
            dois = [dois]
        normalized = []
        for doi in dois:
            doi_norm = normalize_doi(doi)
            if doi_norm and doi_norm not in normalized:
                normalized.append(doi_norm)
        return normalized

    def parse_work_id(raw):
        if pd.isna(raw) or not str(raw).strip():
            return None
        s = str(raw).strip().replace("W", "")
        try:
            return int(s)
        except ValueError:
            return None

    df["work_id"] = df["openalex_work_id"].apply(parse_work_id)
    df["doi_norm"] = df["dois"].apply(extract_dois)
    bridge = df[df["work_id"].notna()][["doi_norm", "work_id"]].explode("doi_norm").copy()
    bridge = bridge[bridge["doi_norm"].notna()]
    bridge = bridge.drop_duplicates(subset="doi_norm", keep="first")
    bridge["work_id"] = bridge["work_id"].astype("int64")
    return bridge
