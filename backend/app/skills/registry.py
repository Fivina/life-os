from __future__ import annotations

from pathlib import Path
from typing import get_args

import yaml

from app.assistant.schemas import AssistantRole
from app.assistant.tools import ToolRegistry
from app.core.config import Settings
from app.skills.models import LoadedSkill, SkillManifest


class SkillConfigurationError(RuntimeError):
    pass


class SkillRegistry:
    def __init__(self, settings: Settings, tools: ToolRegistry | None = None):
        self.settings = settings
        self.tools = tools or ToolRegistry()
        self.skills: dict[str, LoadedSkill] = {}
        self.role_index: dict[str, str] = {}

    def load(self) -> "SkillRegistry":
        root = Path(self.settings.skills_directory)
        if not root.exists():
            raise SkillConfigurationError(f"Skills directory does not exist: {root}")
        loaded: dict[str, LoadedSkill] = {}
        roles: dict[str, str] = {}
        for manifest_path in sorted(root.glob("*/skill.yaml")):
            try:
                raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
                manifest = SkillManifest.model_validate(raw)
            except Exception as exc:
                raise SkillConfigurationError(f"Invalid skill manifest {manifest_path}: {exc}") from exc
            instructions_path = manifest_path.parent / "SKILL.md"
            if not instructions_path.exists():
                raise SkillConfigurationError(f"Missing SKILL.md for skill {manifest.name}")
            if manifest.name in loaded:
                raise SkillConfigurationError(f"Duplicate skill name: {manifest.name}")
            unknown_tools = sorted(set(manifest.allowed_tools) - set(self.tools.tools))
            if unknown_tools:
                raise SkillConfigurationError(f"Skill {manifest.name} references unknown tools: {', '.join(unknown_tools)}")
            for role in manifest.assistant_roles:
                if role in roles:
                    raise SkillConfigurationError(f"Assistant role {role} is assigned to more than one skill")
                roles[role] = manifest.name
            loaded[manifest.name] = LoadedSkill(
                manifest=manifest,
                instructions=instructions_path.read_text(encoding="utf-8").strip(),
                source_directory=str(manifest_path.parent),
            )
        if not loaded:
            raise SkillConfigurationError(f"No skill manifests found in {root}")
        for skill in loaded.values():
            for name in skill.manifest.allowed_agents:
                target = loaded.get(name)
                if target is None:
                    raise SkillConfigurationError(f"Skill {skill.manifest.name} references unknown agent: {name}")
                roles_for_target = target.manifest.assistant_roles
                if (len(roles_for_target) != 1 or roles_for_target[0] == "GENERAL_ASSISTANT"
                        or roles_for_target[0] not in get_args(AssistantRole) or target.manifest.allowed_agents):
                    raise SkillConfigurationError(f"Delegation target {name} must be an interactive leaf specialist")
                if f"consult_{name.replace('-', '_')}" in self.tools.tools:
                    raise SkillConfigurationError(f"Agent tool name collides with a domain tool: {name}")
        self.skills = loaded
        self.role_index = roles
        return self

    def get(self, name: str, *, require_enabled: bool = True) -> LoadedSkill:
        skill = self.skills.get(name)
        if skill is None:
            raise SkillConfigurationError(f"Unknown skill: {name}")
        if require_enabled and not skill.manifest.enabled:
            raise SkillConfigurationError(f"Skill is disabled: {name}")
        return skill

    def for_role(self, role: AssistantRole) -> LoadedSkill:
        name = self.role_index.get(role)
        if name is None:
            raise SkillConfigurationError(f"No skill is configured for assistant role {role}")
        return self.get(name)

    def constitution(self) -> str:
        path = Path(self.settings.skills_directory) / "CONSTITUTION.md"
        if not path.exists():
            raise SkillConfigurationError(f"Missing skill constitution: {path}")
        return path.read_text(encoding="utf-8").strip()
