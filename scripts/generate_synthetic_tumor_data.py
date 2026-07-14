"""Generate a synthetic KISIM-style pathology Excel file for demos/tests.

NO REAL PATIENT DATA. Produces fabricated multi-row-per-patient pathology
entries that exercise the pipeline (confirmed diagnosis, progression, historical
comparison, blank reports, missing information).

    python3 scripts/generate_synthetic_tumor_data.py --out data/raw/synthetic_tumor_input.xlsx
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

COLUMNS = [
    "patnr", "lst_fnr", "anz_op", "min_opdat", "max_opdat",
    "p_nr", "p_fnr", "p_dat", "p_name", "p_kom",
]

ROWS = [
    # Patient with a single confirmed glioblastoma.
    dict(patnr="SYN001", p_nr="1", p_dat="2021-03-14", p_name="Histologie",
         p_kom="Histologisch gesichertes Glioblastom, IDH-Wildtyp, WHO Grad IV."),
    # Progression: earlier Gliom, later Glioblastom.
    dict(patnr="SYN002", p_nr="1", p_dat="2019-01-10", p_name="Histologie",
         p_kom="Diffuses Gliom, WHO Grad II."),
    dict(patnr="SYN002", p_nr="2", p_dat="2021-06-02", p_name="Histologie",
         p_kom="Progression zu Glioblastom, WHO Grad IV."),
    # Metastasis compared with a historical extracranial primary.
    dict(patnr="SYN003", p_nr="1", p_dat="2022-09-01", p_name="Histologie",
         p_kom="Hirnmetastase. Vergleich mit ampullaerem Adenokarzinom von 2007."),
    # Meningioma across two reports.
    dict(patnr="SYN004", p_nr="1", p_dat="2020-02-02", p_name="Histologie",
         p_kom="Meningeom WHO Grad I."),
    dict(patnr="SYN004", p_nr="2", p_dat="2020-02-05", p_name="Verlauf", p_kom=""),
    # Patient with only a blank pathology comment -> missing information.
    dict(patnr="SYN005", p_nr="1", p_dat="2018-05-05", p_name="Verlauf", p_kom="   "),
    # Vestibular schwannoma (synonym resolution).
    dict(patnr="SYN006", p_nr="1", p_dat="2023-01-20", p_name="Histologie",
         p_kom="Vestibularis-Schwannom (Akustikusneurinom)."),
]


def build_df() -> pd.DataFrame:
    return pd.DataFrame([{c: r.get(c, "") for c in COLUMNS} for r in ROWS], columns=COLUMNS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="data/raw/synthetic_tumor_input.xlsx")
    parser.add_argument("--sheet", default="Sheet1")
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    build_df().to_excel(out, index=False, sheet_name=args.sheet, engine="openpyxl")
    print(f"Wrote synthetic pathology data: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
