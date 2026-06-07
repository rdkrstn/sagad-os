import os
import yaml
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional

class AgentConfig(BaseModel):
    name: str
    intents: List[str]
    allowed_tools: List[str]
    system_prompt: str

class AgentRegistry:
    def __init__(self, agents_dir: str = None):
        if agents_dir is None:
            agents_dir = os.path.join(os.path.dirname(__file__), "agents")
        self.agents_dir = Path(agents_dir)
        self.agents: dict[str, AgentConfig] = {}
        self.load_agents()
        
    def load_agents(self):
        if not self.agents_dir.exists():
            return
            
        for file_path in self.agents_dir.glob("*.md"):
            try:
                content = file_path.read_text(encoding="utf-8")
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter = yaml.safe_load(parts[1]) or {}
                        body = parts[2].strip()
                        
                        config = AgentConfig(
                            name=frontmatter.get("name", file_path.stem),
                            intents=frontmatter.get("intents", []),
                            allowed_tools=frontmatter.get("allowed_tools", []),
                            system_prompt=body
                        )
                        for intent in config.intents:
                            self.agents[intent] = config
            except Exception as e:
                print(f"Error loading {file_path}: {e}")

    def get_agent(self, intent: str) -> Optional[AgentConfig]:
        return self.agents.get(intent)
