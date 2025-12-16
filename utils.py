import os
import json
import pandas as pd
import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta
from config import COMPLEX_INFO  # Import config

# --- Supabase Initialization ---
# Initialize connection using st.secrets
# Handle cases where secrets might be missing (e.g. during initial setup)
try:
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    IS_SUPABASE_READY = True
except Exception as e:
    IS_SUPABASE_READY = False
    print(f"[System] Supabase secrets missing or invalid: {e}")

DATA_FILE = "data.json" # Keep for fallback or migration, but primary is DB

def get_kst_time():
    """Returns current time in KST (Korea Standard Time)."""
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst)

def get_timestamp_str():
    """Returns formatted timestamp string."""
    return get_kst_time().strftime("%Y-%m-%d %H:%M:%S")

def get_complex_list():
    """
    Returns list of complex names defined in config.
    """
    return list(COMPLEX_INFO.values())

def get_complex_id_by_name(name):
    """
    Helper to get ID from Name
    """
    for pid, pname in COMPLEX_INFO.items():
        if pname == name:
            return pid
    return None

def load_data(target_complexes=None):
    """
    Loads data from Supabase complex-specific tables.
    Args:
        target_complexes (list): Optional. List of complex NAMES to filter by.
    Returns: List of dictionaries (records).
    """
    if not IS_SUPABASE_READY:
        return []

    all_data = []

    # If no target specified, maybe load all? Or just return empty to be safe/fast?
    # Let's default to loading ALL configured complexes if None
    if not target_complexes:
        target_complexes = list(COMPLEX_INFO.values())

    try:
        for name in target_complexes:
            cid = get_complex_id_by_name(name)
            if not cid:
                continue
            
            table_name = f"listings_{cid}"
            
            # Query with Pagination loop to bypass API limit (usually 1000)
            rows_per_batch = 1000
            current_start = 0
            max_limit = 50000 # Safety hard cap
            
            while True:
                current_end = current_start + rows_per_batch - 1
                try:
                    response = supabase.table(table_name).select("*") \
                                .order("timestamp", desc=True) \
                                .range(current_start, current_end).execute()
                                
                    if not response.data:
                        break
                        
                    all_data.extend(response.data)
                    
                    if len(response.data) < rows_per_batch:
                        break # End of data
                        
                    current_start += rows_per_batch
                    
                    if len(all_data) >= max_limit:
                        print(f"[Supabase] {table_name} max limit reached ({max_limit})")
                        break
                        
                except Exception as loop_e:
                    print(f"[Supabase] Pagination error on {table_name}: {loop_e}")
                    break
        
        return all_data
        
    except Exception as e:
        print(f"[Supabase] Load failed: {e}")
        return []

def save_data(new_items, complex_id="108064"):
    """
    Upserts new items into Supabase complex-specific table.
    """
    if not new_items or not IS_SUPABASE_READY:
        return False
        
    table_name = f"listings_{complex_id}"

    try:
        # Define valid columns matching the created SQL table
        # User will add 'atclFetrDesc' and 'cfmYmd'
        VALID_COLUMNS = {
            "articleNo", "atclNm", "rletTpNm", "tradTpNm", "price", "price_int", 
            "spc1", "spc2", "floorInfo", "direction", "lat", "lng", 
            "tradePrice", "realtorName", "buildingName", "timestamp", "created_at",
            "atclFetrDesc", "cfmYmd"
        }
        
        # Filter and Clean Data
        cleaned_items = []
        for item in new_items:
            # 1. Filter columns
            filtered = {k: v for k, v in item.items() if k in VALID_COLUMNS}
            
            # 2. Fix types (price_int)
            if "price_int" in filtered and filtered["price_int"] is not None:
                try:
                    filtered["price_int"] = int(float(filtered["price_int"]))
                except:
                    filtered["price_int"] = None
            
            cleaned_items.append(filtered)

        if not cleaned_items:
            return False

        # Insert (append history)
        response = supabase.table(table_name).insert(cleaned_items).execute()
        
        print(f"[System] Successfully inserted {len(cleaned_items)} records into {table_name}.")
        return True
        
    except Exception as e:
        print(f"[Supabase] Save failed to {table_name}: {e}")
        return False

def clear_data():
    """
    Deletes ALL data from ALL configured tables.
    """
    if not IS_SUPABASE_READY:
        return

    try:
        for cid in COMPLEX_INFO.keys():
            table_name = f"listings_{cid}"
            # neq usually used to filter. 'articleNo' != '0' (assuming no article has id 0)
            supabase.table(table_name).delete().neq("articleNo", "0").execute()
            print(f"[System] Cleared table {table_name}")
            
        st.cache_data.clear()
        print("[System] All Supabase tables cleared.")
    except Exception as e:
        print(f"[Supabase] Clear failed: {e}")


def clean_price(price_str):
    """
    Converts Korean price string to integer.
    """
    if not isinstance(price_str, str):
        return 0
    price_str = price_str.replace(",", "").strip()
    if "억" in price_str:
        parts = price_str.split("억")
        uk = int(parts[0]) * 100000000 if parts[0] else 0
        rest = int(parts[1]) * 10000 if len(parts) > 1 and parts[1] else 0
        return uk + rest
    try:
        return int(price_str)
    except:
        return 0

def clean_area(area_str):
    return area_str
