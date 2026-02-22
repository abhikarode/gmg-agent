"""
Garje Marathi AI Agent - Modern API-first implementation

This agent provides an API interface for the Garje Marathi community platform.
It uses local Ollama for LLM inference while being deployable on Vercel.

Key features:
- RESTful API endpoints
- Local Ollama integration for LLM inference
- Community data from almashines_data.json
- Web scraping for garjemarathi.com content
- Type-safe with Pydantic models
- Error handling and logging
"""

import json
import logging
import os
from typing import Optional
from dataclasses import dataclass
from enum import Enum

import requests
from bs4 import BeautifulSoup
import ollama

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ModelType(str, Enum):
    """Available Ollama models"""
    MISTRAL = "mistral"
    GLM = "glm-4.7-flash"


@dataclass
class User:
    """User profile data model"""
    unique_profile_id: str
    name: str
    email: str
    role: int
    city: str
    state: str
    country: str
    linkedin: Optional[str] = None
    phone: Optional[str] = None
    designation: Optional[str] = None
    company: Optional[str] = None


@dataclass
class Job:
    """Job posting data model"""
    designation: str
    company: str
    location: str
    job_type: str
    description: Optional[str] = None


@dataclass
class CommunityInfo:
    """Community information from website"""
    name: str
    description: str
    mission: Optional[str] = None
    contact_email: Optional[str] = None


class WebsiteScraper:
    """Scrapes community information from garjemarathi.com"""
    
    BASE_URL = "https://www.garjemarathi.com"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "GarjeMarathiAI/1.0"
        })
    
    def scrape_homepage(self) -> CommunityInfo:
        """Scrape community information from homepage"""
        try:
            response = self.session.get(self.BASE_URL, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Extract community name
            name = "Garje Marathi Global"
            title_tag = soup.find("title")
            if title_tag:
                name = title_tag.get_text(strip=True).split("|")[0].strip()
            
            # Extract description from meta tags or body
            description = self._extract_description(soup)
            
            # Extract contact email
            contact_email = self._extract_email(soup)
            
            return CommunityInfo(
                name=name,
                description=description,
                contact_email=contact_email
            )
            
        except requests.RequestException as e:
            logger.error(f"Failed to scrape homepage: {e}")
            return CommunityInfo(
                name="Garje Marathi Global",
                description="A global community platform for Marathi professionals and enthusiasts."
            )
    
    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract description from page content"""
        # Try meta description first
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            return meta["content"]
        
        # Try to find main content
        main = soup.find("main") or soup.find("div", class_="content") or soup.find("body")
        if main:
            text = main.get_text(strip=True, separator=" ")
            # Return first paragraph or first 200 chars
            paragraphs = text.split("\n\n")
            if paragraphs:
                return paragraphs[0][:200]
        
        return "A global community platform for Marathi professionals and enthusiasts."
    
    def _extract_email(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract contact email from page"""
        # Try mailto links
        mailto = soup.find("a", href=lambda x: x and x.startswith("mailto:"))
        if mailto:
            return mailto["href"].replace("mailto:", "")
        
        # Try to find email in text
        import re
        text = soup.get_text()
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        match = re.search(email_pattern, text)
        if match:
            return match.group()
        
        return None


class DataStore:
    """Manages community data from almashines_data.json"""
    
    def __init__(self, data_file: str = "almashines_data.json"):
        self.data_file = data_file
        self.data = self._load_data()
    
    def _load_data(self) -> dict:
        """Load data from JSON file"""
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Data file {self.data_file} not found")
            return {"users": [], "jobs": []}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse data file: {e}")
            return {"users": [], "jobs": []}
    
    def get_users(self) -> list:
        """Get all users"""
        return self.data.get("users", [])
    
    def get_jobs(self) -> list:
        """Get all jobs"""
        return self.data.get("jobs", [])
    
    def search_users(self, query: str, limit: int = 10) -> list[User]:
        """Search users by name, email, or role"""
        query_lower = query.lower()
        results = []
        
        for user in self.get_users():
            name = user.get("name", "").lower()
            email = user.get("primary_email", "").lower()
            role = str(user.get("role", "")).lower()
            city = user.get("current-city", "").lower()
            
            if (query_lower in name or 
                query_lower in email or 
                query_lower in role or
                query_lower in city):
                results.append(User(
                    unique_profile_id=user.get("unique_profile_id", ""),
                    name=user.get("name", "N/A"),
                    email=user.get("primary_email", "N/A"),
                    role=user.get("role", 0),
                    city=user.get("current-city", "N/A"),
                    state=user.get("current-state", "N/A"),
                    country=user.get("current-country", "N/A"),
                    linkedin=user.get("profile_url_linkedin"),
                    phone=user.get("primary_phone_number")
                ))
            
            if len(results) >= limit:
                break
        
        return results
    
    def search_jobs(self, query: str, limit: int = 10) -> list[Job]:
        """Search jobs by title, company, or location"""
        query_lower = query.lower()
        results = []
        
        for job in self.get_jobs():
            title = str(job.get("designation", "")).lower()
            company = str(job.get("company", "")).lower()
            location = str(job.get("location", "")).lower()
            desc = str(job.get("description", "")).lower()
            
            if (query_lower in title or 
                query_lower in company or 
                query_lower in location or
                query_lower in desc):
                results.append(Job(
                    designation=job.get("designation", "N/A"),
                    company=job.get("company", "N/A"),
                    location=job.get("location", "N/A"),
                    job_type=job.get("job_type", "N/A"),
                    description=job.get("description")
                ))
            
            if len(results) >= limit:
                break
        
        return results
    
    def get_stats(self) -> dict:
        """Get community statistics"""
        return {
            "total_users": len(self.get_users()),
            "total_jobs": len(self.get_jobs()),
            "users_with_profiles": len([u for u in self.get_users() if u.get("profile_pic")]),
            "users_with_work_experience": len([u for u in self.get_users() if u.get("work_experiences")])
        }


class AIAgent:
    """Main AI Agent for Garje Marathi Community"""
    
    def __init__(self, model: ModelType = ModelType.MISTRAL):
        self.model = model
        self.data_store = DataStore()
        self.scraper = WebsiteScraper()
        self.community_info = self.scraper.scrape_homepage()
        self.conversation_history: list[dict] = []
        
        logger.info(f"AI Agent initialized with model: {self.model}")
        logger.info(f"Community: {self.community_info.name}")
        logger.info(f"Stats: {self.data_store.get_stats()}")
    
    def _get_available_model(self) -> str:
        """Get the best available Ollama model"""
        try:
            models = ollama.list()
            available = [m["name"].split(":")[0] for m in models.get("models", [])]
            
            # Prefer mistral, fallback to glm
            if "mistral" in available:
                return "mistral"
            if "glm-4.7-flash" in available:
                return "glm-4.7-flash"
            
            logger.warning(f"No suitable model found. Available: {available}")
            return available[0] if available else "mistral"
            
        except Exception as e:
            logger.error(f"Failed to get available models: {e}")
            return "mistral"
    
    def _call_llm(self, prompt: str) -> str:
        """Call Ollama LLM with the given prompt"""
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                stream=False
            )
            
            # Handle both dict and ChatResponse types
            if hasattr(response, "message") and hasattr(response.message, "content"):
                return response.message.content.strip()
            elif isinstance(response, dict) and "message" in response:
                message = response["message"]
                if isinstance(message, dict) and "content" in message:
                    return message["content"].strip()
            
            return "I couldn't generate a response. Please try again."
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return "I'm having trouble connecting to the AI service. Please try again later."
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the AI"""
        return f"""You are a helpful AI assistant for the {self.community_info.name} community.

Community Information:
- Name: {self.community_info.name}
- Description: {self.community_info.description}
- Contact Email: {self.community_info.contact_email or 'Not available'}

Your Role:
1. Answer questions about the community based on the data
2. Help users find other members
3. Help users find job opportunities
4. Provide community statistics
5. Be friendly, professional, and helpful

Data Sources:
- Member information from almashines_data.json
- Job postings from almashines_data.json
- Community info from garjemarathi.com

When responding:
- Be concise and to the point
- Use bullet points for lists
- Include relevant details like names, locations, and roles
- If you don't know something, say so honestly
- Don't make up information

Format your responses in markdown for better readability."""

    def _format_users(self, users: list[User]) -> str:
        """Format users for display"""
        if not users:
            return "No members found matching your search."
        
        result = f"Found {len(users)} member(s):\n\n"
        for user in users:
            result += f"**{user.name}**\n"
            result += f"- 📧 {user.email}\n"
            if user.phone:
                result += f"- 📱 {user.phone}\n"
            if user.linkedin:
                result += f"- 🔗 {user.linkedin}\n"
            if user.designation and user.company:
                result += f"- 💼 {user.designation} at {user.company}\n"
            if user.city or user.state or user.country:
                location_parts = [p for p in [user.city, user.state, user.country] if p]
                result += f"- 📍 {', '.join(location_parts)}\n"
            result += "\n"
        
        return result
    
    def _format_jobs(self, jobs: list[Job]) -> str:
        """Format jobs for display"""
        if not jobs:
            return "No job opportunities found matching your search."
        
        result = f"Found {len(jobs)} job opportunity/ies:\n\n"
        for job in jobs:
            result += f"**{job.designation}** at {job.company}\n"
            result += f"- 📍 {job.location}\n"
            result += f"- 📋 Type: {job.job_type}\n"
            if job.description:
                result += f"- 📝 {job.description[:200]}...\n"
            result += "\n"
        
        return result
    
    def handle_query(self, user_message: str) -> str:
        """Handle a user query and return a response"""
        message_lower = user_message.lower().strip()
        
        # Clear conversation context
        self.conversation_history = []
        
        # Handle member search
        if any(phrase in message_lower for phrase in [
            "find member", "search member", "search for member", 
            "look for member", "find user", "search user"
        ]):
            query = message_lower.replace("find member", "").replace("search member", "")
            query = query.replace("search for member", "").replace("look for member", "")
            query = query.replace("find user", "").replace("search user", "").strip()
            
            if query:
                users = self.data_store.search_users(query)
                return self._format_users(users)
            else:
                return "Please provide a name, email, or role to search for members."
        
        # Handle job search
        if any(phrase in message_lower for phrase in [
            "find job", "search job", "show job", "show me jobs",
            "list jobs", "search for job", "job opening", "job opportunity"
        ]):
            query = message_lower.replace("find job", "").replace("search job", "")
            query = query.replace("show job", "").replace("show me jobs", "")
            query = query.replace("list jobs", "").replace("search for job", "").strip()
            
            if query:
                jobs = self.data_store.search_jobs(query)
                return self._format_jobs(jobs)
            else:
                # Show all jobs if no query
                jobs = self.data_store.search_jobs("")
                return self._format_jobs(jobs)
        
        # Handle stats query
        if any(phrase in message_lower for phrase in [
            "how many", "total", "statistics", "stats", "count",
            "number of members", "how many members", "member count"
        ]):
            stats = self.data_store.get_stats()
            return f"""**Community Statistics:**

- 👥 Total Members: {stats['total_users']}
- 💼 Job Opportunities: {stats['total_jobs']}
- 📸 Profiles with Photos: {stats['users_with_profiles']}
- 💼 Members with Work Experience: {stats['users_with_work_experience']}"""
        
        # Handle general questions about the community
        if any(phrase in message_lower for phrase in [
            "about community", "about garje", "what is garje",
            "community info", "community details", "who are we"
        ]):
            return f"""**{self.community_info.name}**

{self.community_info.description}

This is a global community platform for Marathi professionals and enthusiasts. We connect members through networking, job opportunities, and community events.

For more information, visit: https://www.garjemarathi.com"""
        
        # Default: use LLM for general conversation
        prompt = f"""User asked: "{user_message}"

Available data:
- {self.data_store.get_stats()['total_users']} community members
- {self.data_store.get_stats()['total_jobs']} job opportunities

Please provide a helpful response based on this context."""
        
        return self._call_llm(prompt)
    
    def chat(self, user_message: str) -> str:
        """Main chat method - handles a single message"""
        response = self.handle_query(user_message)
        return response
    
    def interactive_chat(self):
        """Start an interactive chat session (for local testing)"""
        print("\n" + "=" * 60)
        print("🤖 Garje Marathi AI Assistant")
        print("=" * 60)
        print(f"Model: {self.model}")
        print(f"Community: {self.community_info.name}")
        print(f"Members: {self.data_store.get_stats()['total_users']}")
        print(f"Jobs: {self.data_store.get_stats()['total_jobs']}")
        print("\n💡 Try asking:")
        print("  - 'Find member [name]'")
        print("  - 'Show jobs in [location]'")
        print("  - 'How many members?'")
        print("  - 'What is Garje Marathi?'\n")
        print("Type 'exit' to quit\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if user_input.lower() == "exit":
                    print("\n👋 Thank you for using Garje Marathi AI Assistant!")
                    break
                
                if not user_input:
                    continue
                
                response = self.chat(user_input)
                print(f"\nAssistant: {response}\n")
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                print(f"❌ An error occurred: {e}\n")


# API endpoint handler for Vercel
def handler(event: dict, context: dict) -> dict:
    """
    Vercel serverless function handler
    
    Expected request format:
    {
        "message": "Your question here",
        "model": "mistral"  // optional, defaults to mistral
    }
    
    Returns:
    {
        "statusCode": 200,
        "body": json.dumps({
            "response": "AI response here",
            "model": "mistral"
        })
    }
    """
    try:
        # Parse request
        body = json.loads(event.get("body", "{}"))
        user_message = body.get("message", "")
        model = body.get("model", "mistral")
        
        if not user_message:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Missing 'message' in request body"
                })
            }
        
        # Initialize agent and get response
        agent = AIAgent(model=model)
        response = agent.chat(user_message)
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "response": response,
                "model": model
            })
        }
        
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "Invalid JSON in request body"
            })
        }
    except Exception as e:
        logger.error(f"Handler error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Internal server error"
            })
        }


if __name__ == "__main__":
    # Run interactive chat for local testing
    agent = AIAgent()
    agent.interactive_chat()
