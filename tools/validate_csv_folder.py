import os
import pandas as pd
import re
import json

# Configuration
DIRECTORIES_TO_CHECK = [
    r"c:\Users\yucheng\Desktop\侑特資料\新侑特資料\csv",
    r"c:\Users\yucheng\Desktop\侑特資料\新侑特資料\P3_check_09"
]
OUTPUT_FILE = "COMBINED_VALIDATION_REPORT.md"

# Validation Rules
# Matches 7 digits + underscore + 2 digits (e.g., 1234567_01)
# OR matches 9 consecutive digits (e.g., 123456701)
LOT_NO_PATTERN = re.compile(r'(\d{7}_\d{2})|(\d{9})')
DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')

def normalize_lot_no(value):
    """
    Normalize lot no string.
    Example: "2507313 02 19" -> "2507313_02_19"
    Example: "2507313 02" -> "2507313_02"
    """
    if pd.isna(value):
        return value
    
    s = str(value).strip()
    
    # Pattern: 7 digits + space + 2 digits + space + 2 digits
    # Replace with underscores
    s = re.sub(r'(\d{7})\s+(\d{2})\s+(\d{2})', r'\1_\2_\3', s)
    
    # Pattern: 7 digits + space + 2 digits
    s = re.sub(r'(\d{7})\s+(\d{2})', r'\1_\2', s)
    
    return s

def validate_lot_no(value):
    if pd.isna(value):
        return False
    # Use search to find the pattern anywhere in the string
    return bool(LOT_NO_PATTERN.search(str(value).strip()))

def check_csv_files():
    all_results = []
    total_files = 0
    
    for data_dir in DIRECTORIES_TO_CHECK:
        if not os.path.exists(data_dir):
            print(f"Directory not found: {data_dir}")
            continue

        files = [f for f in os.listdir(data_dir) if f.lower().endswith('.csv')]
        print(f"Found {len(files)} CSV files in {data_dir}")
        total_files += len(files)

        for filename in files:
            filepath = os.path.join(data_dir, filename)
            try:
                df = pd.read_csv(filepath, encoding='utf-8-sig')
            except Exception as e:
                try:
                    df = pd.read_csv(filepath, encoding='cp950') # Try Big5/CP950
                except Exception as e2:
                    all_results.append({
                        "filename": filename,
                        "directory": data_dir,
                        "error": f"Failed to read file: {str(e)} / {str(e2)}"
                    })
                    continue

            file_errors = []
            file_modified = False
            
            # Check Lot No
            lot_no_col = None
            
            # Case-insensitive column search
            df_columns_lower = {str(col).lower().strip(): col for col in df.columns}
            target_cols = ['p3_no.', 'lot no', 'lot_no', 'batch no', 'batch_no', 'lot', 'p3_no']
            
            for target in target_cols:
                if target in df_columns_lower:
                    lot_no_col = df_columns_lower[target]
                    break
            
            if lot_no_col:
                # Apply normalization
                original_values = df[lot_no_col].copy()
                df[lot_no_col] = df[lot_no_col].apply(normalize_lot_no)
                
                # Check if any values changed
                if not df[lot_no_col].equals(original_values):
                    file_modified = True
                    print(f"Normalized Lot No in {filename}")
                
                # Check if ANY row is valid
                valid_rows = df[df[lot_no_col].apply(validate_lot_no)]
                
                if valid_rows.empty:
                    # If NO rows are valid, then the file fails validation
                    file_errors.append(f"No valid Lot No found in column '{lot_no_col}'. Expected 7+2 format (e.g. 1234567_01 or 123456701).")
                else:
                    # If at least one row is valid, the file passes.
                    pass
            else:
                # If no lot_no column, check filename
                match = re.search(r'(\d{7}_\d{2})', filename)
                if not match:
                     file_errors.append("Missing Lot No in filename and no Lot No column found")

            # Save file if modified
            if file_modified:
                try:
                    df.to_csv(filepath, index=False, encoding='utf-8-sig')
                    print(f"Saved modified file: {filename}")
                except Exception as e:
                    file_errors.append(f"Failed to save modified file: {str(e)}")

            if file_errors:
                all_results.append({
                    "filename": filename,
                    "directory": data_dir,
                    "errors": file_errors
                })

    # Generate Report
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("# Combined CSV Validation Report\n\n")
        f.write(f"Checked {total_files} files in:\n")
        for d in DIRECTORIES_TO_CHECK:
            f.write(f"- `{d}`\n")
        f.write("\n")
        
        if not all_results:
            f.write("## All files passed validation!\n")
        else:
            f.write(f"## Found issues in {len(all_results)} files\n\n")
            for item in all_results:
                f.write(f"### {item['filename']} ({os.path.basename(item['directory'])})\n")
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
    check_csv_files()
