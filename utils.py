import os
import json
import pandas as pd
import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta

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
    Fetches distinct 'atclNm' (Complex Names) from recent data.
    Used for Sidebar population without loading full dataset.
    """
    if not IS_SUPABASE_READY:
        return []

    try:
        # Fetch only 'atclNm' from recent 5000 rows to get active complexes
        # Note: Supabase doesn't support 'distinct' easily via client select
        response = supabase.table("listings").select("atclNm").order("timestamp", desc=True).limit(5000).execute()
        if response.data:
            df = pd.DataFrame(response.data)
            return sorted(df['atclNm'].dropna().unique())
        return []
    except Exception as e:
        print(f"[Supabase] Get Complexes failed: {e}")
        return []

def load_data(target_complexes=None):
    """
    Loads data from Supabase 'listings' table.
    Args:
        target_complexes (list): Optional. List of complex names to filter by.
    Returns: List of dictionaries (records).
    """
    if not IS_SUPABASE_READY:
        return []

    try:
        query = supabase.table("listings").select("*").order("timestamp", desc=True)
        
        # Filter if specified (Lazy Loading)
        if target_complexes and len(target_complexes) > 0:
            query = query.in_("atclNm", target_complexes)
        
        # Limit 100,000 is now effective for the SPECIFIC complex(es)
        response = query.limit(100000).execute()
        return response.data
        
    except Exception as e:
        print(f"[Supabase] Load failed: {e}")
        return []

def save_data(new_items):
    """
    Upserts new items into Supabase 'listings' table.
    Uses 'articleNo' as the conflict key (Primary Key).
    """
    if not new_items or not IS_SUPABASE_READY:
        return

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
        response = supabase.table("listings").insert(cleaned_items).execute()
        
        print(f"[System] Successfully inserted {len(cleaned_items)} records to Supabase.")
        return True
        
    except Exception as e:
        print(f"[Supabase] Save failed: {e}")
        return False

def clear_data():
    """
    Deletes ALL data from 'listings' table.
    """
    if not IS_SUPABASE_READY:
        return

    try:
        # neq usually used to filter. 'articleNo' != '0' (assuming no article has id 0, or just use a condition that covers all)
        # Better: delete where articleNo is NOT NULL
        supabase.table("listings").delete().neq("articleNo", "0").execute()
        st.cache_data.clear()
        print("[System] Supabase table cleared.")
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
