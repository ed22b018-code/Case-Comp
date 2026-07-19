import sys
import pandas as pd
from pathlib import Path

# Setup paths to import from pipeline
ROOT_DIR = Path(__file__).resolve().parent.parent
PIPELINE_DIR = ROOT_DIR / "pipeline"
sys.path.insert(0, str(PIPELINE_DIR))

from crosswalk.build_crosswalk import load_or_build_crosswalk
from crosswalk.reconcile import reconcile, load_overrides

CENSUS_URL = "https://raw.githubusercontent.com/nishusharma1608/India-Census-2011-Analysis/master/india-districts-census-2011.csv"
NFHS_URL = "https://raw.githubusercontent.com/SaiSiddhardhaKalla/NFHS/master/India.csv"

OUTPUT_DIR = PIPELINE_DIR / "raw" / "indicators"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def map_districts_to_ids(df, name_col):
    """
    Given a dataframe and the name of its district column,
    reconcile with the crosswalk and return a merged df with 'district_id'.
    """
    xwalk = load_or_build_crosswalk(PIPELINE_DIR)
    overrides = load_overrides()
    
    unique_names = df[name_col].dropna().unique().tolist()
    exact_df, fuzzy_df, no_match_df = reconcile(unique_names, xwalk, cutoff=80.0, overrides=overrides)
    
    # Create mapping dict from source_name -> canonical_district_id
    mapping = {}
    for _, r in pd.concat([exact_df, fuzzy_df], ignore_index=True).iterrows():
        mapping[r["source_name"]] = r["canonical_district_id"]
        
    df["district_id"] = df[name_col].map(mapping)
    return df.dropna(subset=["district_id"]).copy()

def fetch_and_process_census():
    print("Fetching Census 2011 data...")
    df = pd.read_csv(CENSUS_URL)
    
    # 1. urban_pop_pct: Proxy using (Urban_Households / Households) * 100
    if "Urban_Households" in df.columns and "Households" in df.columns:
        df["urban_pop_pct"] = (df["Urban_Households"] / df["Households"]) * 100
    else:
        print("Warning: Missing household columns for urban_pop_pct")
        
    # 2. literacy_rate: (Literate / Population) * 100
    if "Literate" in df.columns and "Population" in df.columns:
        df["literacy_rate"] = (df["Literate"] / df["Population"]) * 100
    else:
        print("Warning: Missing columns for literacy_rate")

    df = map_districts_to_ids(df, name_col="District name")
    
    # Export urban_pop_pct
    urban_df = df[["district_id", "urban_pop_pct"]].copy()
    urban_df["year"] = 2011
    urban_df.rename(columns={"urban_pop_pct": "value"}, inplace=True)
    urban_path = OUTPUT_DIR / "urban_pop_pct.csv"
    urban_df.to_csv(urban_path, index=False)
    print(f"Saved {urban_path}")

    # Export literacy_rate
    lit_df = df[["district_id", "literacy_rate"]].copy()
    lit_df["year"] = 2011
    lit_df.rename(columns={"literacy_rate": "value"}, inplace=True)
    lit_path = OUTPUT_DIR / "literacy_rate.csv"
    lit_df.to_csv(lit_path, index=False)
    print(f"Saved {lit_path}")

def fetch_and_process_nfhs():
    print("Fetching NFHS-5 data...")
    df = pd.read_csv(NFHS_URL)
    
    # Ensure District name column exists for mapping
    # In NFHS, it's 'DISTRICT' or 'District'
    name_col = "DISTRICT" if "DISTRICT" in df.columns else "District"
    
    # Map district names first
    mapped_df = map_districts_to_ids(df, name_col=name_col)
    
    # 3. health_insurance_cov
    # Search indicator column for "health scheme" or "insurance"
    ins_mask = mapped_df["Indicator"].str.contains("health scheme|insurance", case=False, na=False)
    ins_df = mapped_df[ins_mask].copy()
    if not ins_df.empty:
        # Group by district and mean just in case there are multiple matches
        ins_agg = ins_df.groupby("district_id")["NFHS 5"].mean().reset_index()
        ins_agg["year"] = 2020
        ins_agg.rename(columns={"NFHS 5": "value"}, inplace=True)
        ins_path = OUTPUT_DIR / "health_insurance_cov.csv"
        ins_agg.to_csv(ins_path, index=False)
        print(f"Saved {ins_path}")
    else:
        print("Warning: No indicator matched health insurance.")

    # 4. chronic_disease_prev
    # Search for blood sugar, diabetes, hypertension
    chron_mask = mapped_df["Indicator"].str.contains("blood sugar|diabetes|hypertension", case=False, na=False)
    chron_df = mapped_df[chron_mask].copy()
    if not chron_df.empty:
        # We average them to create a proxy
        chron_agg = chron_df.groupby("district_id")["NFHS 5"].mean().reset_index()
        chron_agg["year"] = 2020
        chron_agg.rename(columns={"NFHS 5": "value"}, inplace=True)
        chron_path = OUTPUT_DIR / "chronic_disease_prev.csv"
        chron_agg.to_csv(chron_path, index=False)
        print(f"Saved {chron_path}")
    else:
        print("Warning: No indicator matched chronic diseases.")

def main():
    fetch_and_process_census()
    fetch_and_process_nfhs()
    print("Done generating indicators.")

if __name__ == "__main__":
    main()
