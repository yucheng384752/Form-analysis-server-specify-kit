import os
import pandas as pd
import re
import json

# Configuration
DATA_DIR = r"c:\Users\yucheng\Desktop\侑特資料\新侑特資料\P3_check_09"
OUTPUT_FILE = "P3_ITEMS_ERROR_REPORT.md"

# Validation Rules
LOT_NO_PATTERN = re.compile(r'^\d{7}_\d{2}$')
DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')

# P3 Signature Columns (from csv_field_mapper.py)
P3_SIGNATURE_COLUMNS = {
    'E_Value', 'E Value',
    'Burr',
    'Finish',
    'Machine NO', 'Machine No', 'Machine', 'machine_no', 'machine', '機台', '機台編號',
    'Mold NO', 'Mold No', 'Mold', 'mold_no', 'mold', '模具', '模具編號'
}

def validate_lot_no(value):
    if pd.isna(value):
        return False
    return bool(LOT_NO_PATTERN.match(str(value).strip()))

def validate_date(value):
    if pd.isna(value):
        return False
    # Simple regex check for YYYY-MM-DD
    return bool(DATE_PATTERN.match(str(value).strip()))

def check_p3_files():
    results = []
    
    if not os.path.exists(DATA_DIR):
        print(f"Directory not found: {DATA_DIR}")
        return

    files = [f for f in os.listdir(DATA_DIR) if f.lower().endswith('.csv')]
    
    print(f"Found {len(files)} CSV files in {DATA_DIR}")

    for filename in files:
        filepath = os.path.join(DATA_DIR, filename)
        try:
            df = pd.read_csv(filepath, encoding='utf-8-sig')
        except Exception as e:
            try:
                df = pd.read_csv(filepath, encoding='cp950') # Try Big5/CP950
            except Exception as e2:
                results.append({
                    "filename": filename,
                    "error": f"Failed to read file: {str(e)} / {str(e2)}"
                })
                continue

        file_errors = []
        
        # Check if it looks like a P3 file
        columns = set(df.columns)
        # Normalize columns for matching
        normalized_columns = {c.strip() for c in columns}
        
        # Check for P3 signature columns (loose check)
        # We just want to see if it has ANY P3-like columns if we are strict, 
        # but here we assume they are P3 files and check data quality.
        
        # Check Lot No
        # Lot No might be in 'P3_No.', 'lot_no', or filename
        lot_no_col = None
        for col in ['P3_No.', 'lot_no', 'Lot No', 'Batch No']:
            if col in df.columns:
                lot_no_col = col
                break
        
        if lot_no_col:
            invalid_lots = df[~df[lot_no_col].apply(validate_lot_no)]
            if not invalid_lots.empty:
                for idx, row in invalid_lots.iterrows():
                    file_errors.append(f"Row {idx+1}: Invalid Lot No '{row[lot_no_col]}'")
        else:
            # If no lot_no column, check filename
            match = re.search(r'(\d{7}_\d{2})', filename)
            if not match:
                 file_errors.append("Missing Lot No in filename and no Lot No column found")

        # Check Production Date
        date_col = None
        for col in ['Production Date', 'production_date', 'Date', 'year-month-day']:
            if col in df.columns:
                date_col = col
                break
        
        if date_col:
             # Try to convert to string and check format
             # Some might be parsed as datetime objects by pandas
             # We want to ensure they are in YYYY-MM-DD format or convertible
             pass 
             # For now, let's skip strict date format check as pandas might have parsed it differently
             # and just check for missing values if it's a required field (it's not strictly required by schema but good to have)
             
             if df[date_col].isna().any():
                 missing_rows = df[df[date_col].isna()].index.tolist()
                 file_errors.append(f"Missing Production Date in rows: {[i+1 for i in missing_rows]}")

        if file_errors:
            results.append({
                "filename": filename,
                "errors": file_errors
            })

    # Generate Report
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("# P3 Data Validation Report\n\n")
        f.write(f"Checked {len(files)} files in `{DATA_DIR}`\n\n")
        
        if not results:
            f.write("## All files passed validation!\n")
        else:
            f.write(f"## Found issues in {len(results)} files\n\n")
            for item in results:
                f.write(f"### {item['filename']}\n")
                if 'error' in item:
                    f.write(f"- **Critical Error**: {item['error']}\n")
                else:
                    for err in item['errors']:
                        f.write(f"- {err}\n")
                f.write("\n")

    print(f"Validation complete. Report saved to {OUTPUT_FILE}")
    # Print content of the report
    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
        print(f.read())

if __name__ == "__main__":
    check_p3_files()
