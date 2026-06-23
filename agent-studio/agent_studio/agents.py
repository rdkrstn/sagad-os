import os
import re
import yaml
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional

class AgentConfig(BaseModel):
    id: str
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
                            id=file_path.stem,
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

    def get_all_agents(self) -> List[AgentConfig]:
        unique_agents = {id(config): config for config in self.agents.values()}
        return list(unique_agents.values())

    def reload_agents(self) -> None:
        self.agents.clear()
        self.load_agents()

    def save_agent(
        self,
        agent_id: str,
        name: str,
        intents: List[str],
        allowed_tools: List[str],
        system_prompt: str,
        original_id: Optional[str] = None,
    ) -> AgentConfig:
        safe_id = re.sub(r"[^a-z0-9_]", "_", agent_id.lower().strip())
        if not safe_id:
            raise ValueError("Agent ID cannot be empty.")

        # Delete old file if renaming
        if original_id and original_id != safe_id:
            old_path = self.agents_dir / f"{original_id}.md"
            if old_path.exists():
                old_path.unlink()

        frontmatter_data = yaml.dump(
            {"name": name, "intents": intents, "allowed_tools": allowed_tools},
            default_flow_style=True,
        ).strip()
        content = f"---\n{frontmatter_data}\n---\n{system_prompt.strip()}\n"
        file_path = self.agents_dir / f"{safe_id}.md"
        file_path.write_text(content, encoding="utf-8")
        self.reload_agents()

        config = AgentConfig(
            id=safe_id,
            name=name,
            intents=intents,
            allowed_tools=allowed_tools,
            system_prompt=system_prompt.strip(),
        )
        return config

    def delete_agent(self, agent_id: str) -> bool:
        # Match the same id normalization save_agent applies, so a hyphenated id
        # (e.g. "e2e-test") deletes the file it actually wrote ("e2e_test.md").
        safe_id = re.sub(r"[^a-z0-9_]", "_", agent_id.lower().strip())
        file_path = self.agents_dir / f"{safe_id}.md"
        if file_path.exists():
            file_path.unlink()
            self.reload_agents()
            return True
        return False
