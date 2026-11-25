import requests
import json
from typing import List, Dict, Optional
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class AlmaShinesExtractor:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://www.almashines.com/data/api"
        self.all_data = {}
        self.session = requests.Session()
        self.session.mount("https://", HTTPAdapter(max_retries=Retry(
            total=3, status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods={"POST"}, backoff_factor=0.5,
        )))
    
    def _make_request(self, endpoint: str, params: Dict) -> Dict:
        """Make API request with authentication"""
        url = f"{self.base_url}/{endpoint}"
        payload = {
            "apikey": self.api_key,
            "apisecret": self.api_secret,
            **params
        }
        
        try:
            response = self.session.post(url, data=payload, timeout=10, allow_redirects=False)
            if response.is_redirect:
                raise requests.RequestException("Unexpected AlmaShines redirect")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as error:
            print(f"Error calling {endpoint}: {type(error).__name__}")
            return {"success": 0, "error": type(error).__name__}
    
    def extract_all_users(self) -> List[Dict]:
        """Extract all users with pagination"""
        all_users = []
        seen_ids = set()
        limit = 200
        for stream in range(1, 101):
            response = self._make_request("listUsers", {
                "stream": stream,
                "limit": limit
            })
            users = response.get("data") if isinstance(response, dict) and response.get("success") == 1 else None
            if not isinstance(users, list) or len(users) > limit:
                raise ValueError(f"Could not verify AlmaShines member page {stream}.")
            for user in users:
                member_id = user.get("unique_profile_id") if isinstance(user, dict) else None
                if not isinstance(member_id, str) or not member_id.strip() or member_id.strip() in seen_ids:
                    raise ValueError(f"Missing or duplicate profile ID on AlmaShines member page {stream}.")
                seen_ids.add(member_id.strip())
            all_users.extend(users)
            print(f"AlmaShines member page {stream}: {len(users)} rows")
            if len(users) < limit:
                break
            time.sleep(0.5)
        else:
            raise ValueError("AlmaShines member export exceeded 100 pages.")
        if not all_users:
            raise ValueError("AlmaShines returned an empty member directory.")
        self.all_data["users"] = all_users
        return all_users
    
    def extract_all_jobs(self) -> List[Dict]:
        """Extract all jobs with filtering"""
        all_jobs = []
        stream = 1
        limit = 50
        
        print("🔄 Extracting jobs...")
        while True:
            response = self._make_request("listJobs", {
                "stream": stream,
                "limit": limit
            })
            
            if response.get("success") == 1 and response.get("jobs"):
                jobs = response["jobs"]
                all_jobs.extend(jobs)
                print(f"   ✓ Fetched {len(jobs)} jobs (stream {stream})")
                
                if len(jobs) < limit:
                    break
                stream += 1
                time.sleep(0.5)
            else:
                if response.get("error"):
                    print(f"   ✗ Error: {response.get('error')}")
                break
        
        self.all_data["jobs"] = all_jobs
        print(f"✅ Total jobs extracted: {len(all_jobs)}\n")
        return all_jobs
    
    def extract_form_data(self, form_id: int) -> Dict:
        """Extract form details and all responses"""
        print(f"🔄 Extracting form {form_id}...")
        
        # Get form structure
        form_details = self._make_request("getFormDetails", {
            "form_id": form_id
        })
        
        if form_details.get("success") != 1:
            print(f"   ✗ Failed to get form details")
            return {}
        
        # Get form responses
        all_responses = []
        stream = 1
        limit = 100
        
        while True:
            response = self._make_request("listFormResponses", {
                "form_id": form_id,
                "stream": stream,
                "limit": limit
            })
            
            if response.get("success") == 1 and response.get("data"):
                responses = response["data"]
                all_responses.extend(responses)
                print(f"   ✓ Fetched {len(responses)} responses (stream {stream})")
                
                if len(responses) < limit:
                    break
                stream += 1
                time.sleep(0.5)
            else:
                break
        
        form_data = {
            "form_id": form_id,
            "details": form_details.get("data", {}),
            "responses": all_responses,
            "response_count": len(all_responses)
        }
        
        print(f"✅ Form {form_id}: {len(all_responses)} responses\n")
        return form_data
    
    def extract_recently_updated_users(self, hours: int = 720) -> List[Dict]:
        """Extract recently updated users"""
        print(f"🔄 Extracting recently updated users (last {hours} hours)...")
        
        response = self._make_request("listRecentlyUpdatedUsers", {
            "stream": 1,
            "limit": 200,
            "updatedInLastXHours": hours
        })
        
        users = response.get("data", []) if response.get("success") == 1 else []
        print(f"✅ Recently updated users: {len(users)}\n")
        return users
    
    def save_to_file(self, filename: str = "almashines_data.json"):
        """Save extracted data to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.all_data, f, indent=2, ensure_ascii=False)
        print(f"💾 Data saved to {filename}")
    
    def extract_all(self, form_ids: Optional[List[int]] = None):
        """Extract all available data"""
        print("=" * 50)
        print("🚀 Starting AlmaShines Data Extraction")
        print("=" * 50 + "\n")
        
        self.extract_all_users()
        self.extract_all_jobs()
        self.extract_recently_updated_users()
        
        if form_ids:
            self.all_data["forms"] = []
            for form_id in form_ids:
                form_data = self.extract_form_data(form_id)
                if form_data:
                    self.all_data["forms"].append(form_data)
        
        print("=" * 50)
        print("✅ Extraction Complete!")
        print("=" * 50)
        
        return self.all_data
