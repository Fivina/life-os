from app.intelligence_settings.schemas import AgentProfile


def agent_profile(metadata: dict | None, skill_name: str) -> AgentProfile:
    defaults = {"display_name": skill_name.replace("-", " ").title()}
    stored = ((metadata or {}).get("agent_profiles") or {}).get(skill_name)
    return AgentProfile.model_validate({**defaults, **(stored or {})})
