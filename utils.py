import json
import os
import pandas as pd
import streamlit as st
try:
    from streamlit_gsheets import GSheetsConnection
except ImportError:
    GSheetsConnection = None
from datetime import datetime, timezone, timedelta

DATA_FILE = "data.json"

def get_kst_time():
    """Returns current time in KST (Korea Standard Time)."""
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst)

def get_timestamp_str():
    """Returns formatted timestamp string."""
    return get_kst_time().strftime("%Y-%m-%d %H:%M:%S")

def _get_gsheet_conn():
    """Helper to get GSheet connection safely."""
    try:
        return st.connection("gsheets", type=GSheetsConnection)
    except Exception:
        return None

def load_data(filepath=DATA_FILE):
    """
    Loads data from Google Sheets if configured, otherwise from local JSON.
    Returns a list of dictionaries.
    """
    # Try Google Sheets first
    try:
        conn = _get_gsheet_conn()
        # simplified check: if connection works and secrets exist
        if conn:
            # Read first available worksheet (default)
            df = conn.read(ttl=0) 
            if not df.empty:
                # Convert date/int columns if needed or just return records
                # GSheets often reads as strings or floats, let's just convert to records
                # Handle potential NaN
                df = df.fillna("")
                return df.to_dict(orient="records")
            else:
                return []
    except Exception as e:
        # If any error (e.g. no secrets), fall back to local
        pass

    # Fallback to local JSON
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

def save_data(new_items, filepath=DATA_FILE):
    """
    Appends new items to Google Sheets if configured, AND always synchronizes local JSON
    to ensure the dashboard has a reliable fallback if GSheets read fails.
    """
    if not new_items:
        return

    # Try Google Sheets
    try:
        conn = _get_gsheet_conn()
        if conn:
             # Read current from GSheet to append correctly
            try:
                current_df = conn.read(ttl=0)
            except:
                current_df = pd.DataFrame()
                
            new_df = pd.DataFrame(new_items)
            
            # Concat
            if not current_df.empty:
                updated_df = pd.concat([current_df, new_df], ignore_index=True)
            else:
                updated_df = new_df
                
            # Write back to GSheets
            conn.update(data=updated_df)
            st.cache_data.clear()
            
            # CRITICAL FIX:
            # Also save this complete updated dataset to local JSON.
            # This ensures that if the dashboard fails to load the huge GSheet,
            # the local fallback file is 100% up-to-date.
            updated_data = updated_df.to_dict(orient="records")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(updated_data, f, ensure_ascii=False, indent=2)
                
            print(f"[System] Data saved to GSheets and synced to local {filepath} ({len(updated_data)} records)")
            return
            
    except Exception as e:
        print(f"GSheets save failed: {e}, falling back to local only.")
        pass

    # Fallback (Google Sheets failed or not configured)
    # Just append to local file
    current_data = load_data(filepath)
    updated_data = current_data + new_items
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(updated_data, f, ensure_ascii=False, indent=2)
    print(f"[System] Data saved to local only {filepath} ({len(updated_data)} records)")

def clear_data(filepath=DATA_FILE):
    """
    Clears all data from Google Sheets (if connected) AND local storage.
    """
    # 1. Clear Google Sheets
    try:
        conn = _get_gsheet_conn()
        if conn:
            # Try to preserve columns if possible
            try:
                # Read 0 rows just to get columns? Or read all.
                # If sheet is already empty, this might return empty DF.
                df = conn.read(ttl=0)
                cols = df.columns if not df.empty else []
            except:
                cols = []
            
            # Create empty DF with same columns if they existed, else just empty
            empty_df = pd.DataFrame(columns=cols) if len(cols) > 0 else pd.DataFrame()
            
            # Update
            conn.update(data=empty_df)
            st.cache_data.clear()
            
    except Exception as e:
        # Ignore specific harmless error (1, 0) which implies empty range update success
        if str(e) != "(1, 0)":
            print(f"GSheets clear failed: {e}")
        
    # 2. Clear Local File
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception as e:
            print(f"Local delete failed: {e}")

def clean_price(price_str):
    """
    Converts Korean price string (e.g., '10억 5,000', '3억 5,000') to integer (KRW).
    Examples:
    '15억' -> 1500000000
    '3억 5,000' -> 350000000
    """
    if not isinstance(price_str, str):
        return 0
    
    price_str = price_str.replace(",", "").strip()
    
    # Handle '억'
    if "억" in price_str:
        parts = price_str.split("억")
        uk_part = parts[0].strip()
        cheown_part = parts[1].strip() if len(parts) > 1 else ""
        
        uk_val = int(uk_part) * 100000000 if uk_part else 0
        cheown_val = int(cheown_part) * 10000 if cheown_part else 0
        
        return uk_val + cheown_val
    else:
        # Just numbers (less likely in high value real estate but possible)
        try:
            return int(price_str)
        except ValueError:
            return 0

def clean_area(area_str):
    """
    Extracts number from area string if needed.
    """
    # Usually strictly numeric or '112/84m2'
    # Return as string for display or float for calculation
    return area_str
