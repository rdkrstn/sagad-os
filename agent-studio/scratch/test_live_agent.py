import os
import sys
from pathlib import Path

# Add parent directory to path so agent_studio is importable
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from agent_studio.graph import graph
from agent_studio.state import AgentStudioState

def test_interactive_message(message: str, intent: str = "general_support"):
    print(f"\n--- Testing Message: '{message}' (Assigned Intent: {intent}) ---")
    
    # Check what model we are using
    model_name = os.getenv("LITELLM_MODEL") or os.getenv("OPENAI_MODEL") or "default (gpt-4o-mini)"
    print(f"Using Model: {model_name}")
    
    # Check for keys
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    
    print(f"Environment Keys Detected: OpenAI={bool(openai_key)}, Gemini={bool(gemini_key)}, Anthropic={bool(anthropic_key)}")
    
    state: AgentStudioState = {
        "incoming_message": message,
        "normalized_message": message,
        "intent": intent,
        "risk_level": "low",
        "retrieved_knowledge": []
    }
    
    try:
        print("Invoking graph node...")
        result = graph.invoke(state)
        print("Response received successfully!")
        print("Draft Reply:")
        print(result.get("draft_reply", "No reply generated."))
    except Exception as e:
        print(f"Error executing graph: {e}")

if __name__ == "__main__":
    # Test message that routes to the general support agent
    test_interactive_message("Hello, I need help resetting my login password.")
