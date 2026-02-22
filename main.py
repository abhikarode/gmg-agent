import os
from dotenv import load_dotenv
from almashines_extractor import AlmaShinesExtractor
from ai_agent import AlmaShinesAIAgent

def main():
    # Load environment variables
    load_dotenv()
    
    print("\n" + "=" * 60)
    print("🚀 Garje Marathi Community AI Agent")
    print("=" * 60 + "\n")
    
    # Check if data already exists
    import os.path
    data_file = "almashines_data.json"
    
    if not os.path.exists(data_file):
        # Only extract if data doesn't exist
        print("📊 Data not found. Extracting from AlmaShines...\n")
        
        # Get API credentials
        API_KEY = os.getenv("ALMASHINES_API_KEY")
        API_SECRET = os.getenv("ALMASHINES_API_SECRET")
        
        if not API_KEY or not API_SECRET:
            print("❌ Error: Please set ALMASHINES_API_KEY and ALMASHINES_API_SECRET")
            print("   Create a .env file with your credentials")
            return
        
        # Extract data
        print("📊 Step 1: Extracting data from AlmaShines...\n")
        extractor = AlmaShinesExtractor(API_KEY, API_SECRET)
        # Pass None instead of empty list to skip form extraction
        data = extractor.extract_all(form_ids=None)
        extractor.save_to_file(data_file)
    else:
        print(f"✅ Using existing data from {data_file}\n")
    
    # Verify data file exists before initializing agent
    if not os.path.exists(data_file):
        print(f"❌ Error: Data file {data_file} not found")
        return
    
    # Initialize AI agent
    print("🤖 Step 2: Initializing AI Agent...\n")
    agent = AlmaShinesAIAgent(data_file)
    
    # Start interactive chat
    print("💬 Step 3: Starting Interactive Chat...\n")
    agent.interactive_chat()

if __name__ == "__main__":
    main()