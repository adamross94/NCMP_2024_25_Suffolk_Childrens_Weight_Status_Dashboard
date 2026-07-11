"""
Prepare Suffolk NCMP 2024/25 data for Power BI.

Input:
  data/raw/NCMP-2024-2025-academic-year-data-tables_v2.ods

Outputs:
  data/processed/ncmp_suffolk_powerbi_ready.csv
  data/processed/ncmp_suffolk_data_quality.csv

Requires:
  pip install pandas odfpy
"""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_FILE = ROOT / "data" / "raw" / "NCMP-2024-2025-academic-year-data-tables_v2.ods"
OUT_DIR = ROOT / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Areas used in the dashboard.
AREAS = {
    "England": "England",
    "Suffolk": "Upper-tier local authority",
    "Ipswich": "Lower-tier local authority",
    "East Suffolk": "Lower-tier local authority",
    "West Suffolk": "Lower-tier local authority",
    "Babergh": "Lower-tier local authority",
    "Mid Suffolk": "Lower-tier local authority",
}

# ODS sheets used from the official NCMP workbook.
# Tables 9a/9b = upper-tier local authorities, Reception / Year 6.
# Tables 10a/10b = lower-tier local authorities, Reception / Year 6.
MEASURE_SHEETS = [
    ("Table_9a", "Reception", "Upper-tier local authority"),
    ("Table_9b", "Year 6", "Upper-tier local authority"),
    ("Table_10a", "Reception", "Lower-tier local authority"),
    ("Table_10b", "Year 6", "Lower-tier local authority"),
]


def read_table(sheet_name: str) -> pd.DataFrame:
    """Read an NCMP table where the real header row starts on row 5."""
    return pd.read_excel(RAW_FILE, sheet_name=sheet_name, engine="odf", header=4)


def clean_measure_table(sheet_name: str, year_group: str, default_area_level: str) -> pd.DataFrame:
    df = read_table(sheet_name)

    # Keep only the areas needed for the dashboard.
    df = df[df["Local authority name"].isin(AREAS.keys())].copy()

    # The England row has 'not applicable' in the local authority name in some tables,
    # but has 'England' in the geographic region name. Handle both patterns safely.
    england_mask = df["Geographic region name"].eq("England")
    df.loc[england_mask, "Local authority name"] = "England"
    df.loc[england_mask, "Local authority code"] = "E92000001"

    # Assign area level used in the dashboard.
    def area_level(area_name: str) -> str:
        if area_name == "England":
            return "England"
        if area_name == "Suffolk":
            return "Upper-tier local authority"
        return default_area_level

    output = pd.DataFrame({
        "AreaName": df["Local authority name"],
        "AreaCode": df["Local authority code"],
        "AreaLevel": df["Local authority name"].map(area_level),
        "Region": df["Geographic region name"],
        "YearGroup": year_group,
        "SchoolYear": df["School  year"],
        "MeasuredCount": pd.to_numeric(df["Number of children measured"], errors="coerce"),
        "ObesityPct": pd.to_numeric(df["Obesity prevalence"], errors="coerce"),
        "ExcessWeightPct": pd.to_numeric(df["Overweight and obesity combined prevalence"], errors="coerce"),
        "OverweightPct": pd.to_numeric(df["Overweight prevalence"], errors="coerce"),
        "SevereObesityPct": pd.to_numeric(df["Severe obesity prevalence"], errors="coerce"),
    })

    return output


# Build the Power BI-ready file.
measure_frames = [clean_measure_table(*sheet_info) for sheet_info in MEASURE_SHEETS]
measures = pd.concat(measure_frames, ignore_index=True)

# Remove accidental duplicates caused by England appearing in both upper and lower-tier tables.
# Keep one England row per year group.
measures = measures.drop_duplicates(subset=["AreaName", "YearGroup"], keep="first")

area_order = {
    "England": 0,
    "Suffolk": 1,
    "Ipswich": 2,
    "East Suffolk": 3,
    "West Suffolk": 4,
    "Babergh": 5,
    "Mid Suffolk": 6,
}
measures["AreaSort"] = measures["AreaName"].map(area_order).fillna(99).astype(int)
measures["YearGroupSort"] = measures["YearGroup"].map({"Reception": 1, "Year 6": 2}).astype(int)

measures = measures.sort_values(["AreaSort", "YearGroupSort"]).reset_index(drop=True)
measures.to_csv(OUT_DIR / "ncmp_suffolk_powerbi_ready.csv", index=False)

# Build a small data quality extract for optional source notes.
dq = read_table("Table_12")
dq = dq[dq["Local authority name"].isin(["England", "Suffolk"])].copy()
dq_out = dq[[
    "Local authority name",
    "Local authority code",
    "Reception participation rate",
    "Year 6 participation rate",
    "Data quality note: Low participation (equal to or less than 90%)",
]].rename(columns={
    "Local authority name": "AreaName",
    "Local authority code": "AreaCode",
    "Reception participation rate": "ReceptionParticipationRate",
    "Year 6 participation rate": "Year6ParticipationRate",
    "Data quality note: Low participation (equal to or less than 90%)": "LowParticipationNote",
})

dq_out.to_csv(OUT_DIR / "ncmp_suffolk_data_quality.csv", index=False)

print("Created:")
print(f"- {OUT_DIR / 'ncmp_suffolk_powerbi_ready.csv'}")
print(f"- {OUT_DIR / 'ncmp_suffolk_data_quality.csv'}")
