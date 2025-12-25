import os
import pandas as pd
import glob
import re

directory = r"c:\Users\yucheng\Desktop\侑特資料\新侑特資料\P3_check_09"
target_file_pattern = "P3_0902_P24.csv"

def check_files():
    files = glob.glob(os.path.join(directory, "*.csv"))
    
    print(f"Scanning {len(files)} files in {directory}...\n")
    
    # Pattern for "standard" lot no (7 digits + 2 digits + 2 digits, separators can be _ or space)
    # e.g. 2507173_02_17 or 2507173 02 17
    # But P3_0902_P24 has "32-H5 UT-1 2507173 02 17"
    
    # Let's just list what we find
    
    summary = []
    
    for file_path in files:
        filename = os.path.basename(file_path)
        try:
            # Try reading with default encoding, then utf-8, then big5 (common for traditional chinese csv)
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='big5')
            except:
                df = pd.read_csv(file_path, encoding='cp950')

            columns = df.columns.tolist()
            has_p3_no = "P3_No." in columns
            has_lot_no = "lot no" in columns
            
            # Check for data matching P3_0902_P24 style (long string in lot no)
            sample_lot_no = None
            if has_lot_no and not df.empty:
                sample_lot_no = str(df.iloc[0]['lot no'])
            
            # Validation check
            # "Current validation method" usually expects P3_No. to exist for P3 files
            # OR if using lot no, it expects a parseable format.
            
            is_valid_format = True
            invalid_reason = []
            
            if not has_p3_no:
                is_valid_format = False
                invalid_reason.append("Missing P3_No. column")
            
            if has_lot_no:
                # Check if lot_no follows the simple 7_2_2 format
                # Regex for 7 digits, separator, 2 digits, separator, 2 digits
                # simple_pattern = re.compile(r'^\d{7}[_ ]\d{2}[_ ]\d{2}$')
                # invalid_rows = []
                # for idx, row in df.iterrows():
                #     val = str(row['lot no'])
                #     if not simple_pattern.match(val):
                #         invalid_rows.append(val)
                #         if len(invalid_rows) > 0: break
                
                # if invalid_rows:
                #    invalid_reason.append(f"lot no format mismatch (e.g. {invalid_rows[0]})")
                pass

            summary.append({
                "file": filename,
                "has_p3_no": has_p3_no,
                "has_lot_no": has_lot_no,
                "sample_lot_no": sample_lot_no,
                "invalid_reasons": invalid_reason
            })

        except Exception as e:
            print(f"Error reading {filename}: {e}")

    # Filter for files that look like P3_0902_P24 (Missing P3_No, has lot no with extra text)
    print("-" * 80)
    print("Files similar to P3_0902_P24 (Missing P3_No., Has 'lot no'):")
    print("-" * 80)
    
    similar_files = [s for s in summary if not s['has_p3_no'] and s['has_lot_no']]
    
    for s in similar_files:
        print(f"File: {s['file']}")
        print(f"  Sample lot no: {s['sample_lot_no']}")
        print(f"  Issues: {', '.join(s['invalid_reasons'])}")
        print("")

    print("-" * 80)
    print("Other files with issues:")
    print("-" * 80)
    other_issues = [s for s in summary if s not in similar_files and s['invalid_reasons']]
    for s in other_issues:
        print(f"File: {s['file']}")
        print(f"  Issues: {', '.join(s['invalid_reasons'])}")

if __name__ == "__main__":
    check_files()
