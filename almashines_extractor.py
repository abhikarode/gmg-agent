import requests
import json
from typing import List, Dict, Optional
import time

class AlmaShinesExtractor:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://www.almashines.com/data/api"
        self.all_data = {}
    
    def _make_request(self, endpoint: str, params: Dict) -> Dict:
        """Make API request with authentication"""
        url = f"{self.base_url}/{endpoint}"
        payload = {
            "apikey": self.api_key,
            "apisecret": self.api_secret,
            **params
        }
        
        try:
            response = requests.post(url, data=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error calling {endpoint}: {str(e)}")
            return {"success": 0, "error": str(e)}
    
    def extract_all_users(self) -> List[Dict]:
        """Extract all users with pagination"""
        all_users = []
        stream = 1
        limit = 200  # Max limit per request
        
        print("🔄 Extracting users...")
        while True:
            response = self._make_request("listUsers", {
                "stream": stream,
                "limit": limit
            })
            
            if response.get("success") == 1 and response.get("data"):
                users = response["data"]
                all_users.extend(users)
                print(f"   ✓ Fetched {len(users)} users (stream {stream})")
                
                if len(users) < limit:
                    break
                stream += 1
                time.sleep(0.5)  # Rate limiting
            else:
                if response.get("error"):
                    print(f"   ✗ Error: {response.get('error')}")
                break
        
        self.all_data["users"] = all_users
        print(f"✅ Total users extracted: {len(all_users)}\n")
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