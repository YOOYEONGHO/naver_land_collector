import requests
import time
import random
from utils import get_timestamp_str, clean_price

class NaverLandCrawler:
    def __init__(self):
        self.base_url = "https://m.land.naver.com/complex/getComplexArticleList"
        # Common headers to mimic a browser
        self.base_url = "https://m.land.naver.com/complex/getComplexArticleList"
        # Common headers to mimic a mobile browser
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36",
            "Referer": "https://m.land.naver.com/",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
        }

    def fetch_listings(self, region_code=None, complex_no=None, trade_type="A1"):
        """
        Fetches listings based on Region Code (cortarNo) or Complex ID (hscpNo).
        Note: Naver API usually works better with specific complex IDs ('hscpNo') or 
        via the map-based 'cluster' API for regions. 
        For this implementation, we will use a known endpoint structure for 'complex' 
        which is stricter but easier to demonstrate if we have a complex ID.
        
        If region_code is provided without complex_no, it's harder because Naver groups by clusters.
        We will try to support 'complex' based crawling primarily as it's the target for "Fake Listing" (At specific apartments).
        
        Args:
            complex_no (str): Naver's complex ID (e.g., '1116' for a specific Apt).
            trade_type (str): 'A1' (Sale/Maemae), 'B1' (Jeonse), 'B2' (Wolse). Default 'A1'.
        """
        
        # Endpoint: https://m.land.naver.com/complex/getComplexArticleList
        # Params: hscpNo, traditionalTpCd (A1:Deal, B1:Jeonse, B2:Rent), order=date_desc, showR0=N
        
        if not complex_no:
            # Fallback or error, but let's assume user provides complex ID for 'Targeted Evidence Collection'
            # Or we could provide a default one for Gangnam Eunma Apt: '1116' if empty?
            # Let's require it or use a default if None mostly for testing.
             raise ValueError("Complex ID (hscpNo) is required for targeted crawling.")

        params = {
            "hscpNo": complex_no,
            "tradTpCd": trade_type, 
            "order": "date_desc", # Newest first
            "showR0": "N", # Hide completed deals?
            "page": 1
        }
        
        all_articles = []
        page = 1
        
        batch_timestamp = get_timestamp_str()
        
        while True:
            params["page"] = page
            try:
                response = requests.get(self.base_url, headers=self.headers, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                # Check response structure
                if "result" not in data or "list" not in data["result"]:
                    print(f"Failed to fetch data or end of list: {data}")
                    break
                    
                listings = data["result"]["list"]
                if not listings:
                    break
                
                for item in listings:
                    # Parse relevant fields
                    # Different response structures exist. We map carefully.
                    mapped_item = {
                        "articleNo": item.get("atclNo"),
                        "atclNm": item.get("atclNm"),
                        "tradePrice": item.get("prcInfo"), # Correct field is prcInfo
                        "floorInfo": item.get("flrInfo"),
                        "spc1": item.get("spc1"), # Supply Area
                        "spc2": item.get("spc2"), # Exclusive Area
                        "atclFetrDesc": item.get("atclFetrDesc"),
                        "regDate": item.get("atclCfmYmd"), # Often Used as Reg Date
                        "rletTpNm": item.get("rletTpNm"),
                        "cfmYmd": item.get("atclCfmYmd"), # Confirm Date
                        "tradTpNm": item.get("tradTpNm"), # Deal Type Name
                        "direction": item.get("direction"), # South/East etc
                        "buildingName": item.get("bildNm"), # e.g. 101dong
                        "realtorName": item.get("rltrNm"), # Realtor
                        "timestamp": batch_timestamp,
                        
                        # Processed fields
                        "price_int": clean_price(item.get("prcInfo"))
                    }
                    all_articles.append(mapped_item)
                
                # Pagination limit for safety/demo
                if len(listings) < 20 or page >= 5: # Assuming page size is roughly 20
                    break
                
                page += 1
                time.sleep(random.uniform(0.5, 1.5)) # Polite delay
                
            except Exception as e:
                print(f"Error crawling page {page}: {e}")
                break
                
        return all_articles

if __name__ == "__main__":
    # Internal test
    crawler = NaverLandCrawler()
    # Test with a known ID (e.g., Gangnam Eunma: 1116)
    try:
        results = crawler.fetch_listings(complex_no="1116")
        print(f"Fetched {len(results)} listings.")
        if results:
            print(results[0])
    except Exception as e:
        print(e)
