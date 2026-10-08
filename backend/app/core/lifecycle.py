from fastapi import HTTPException, status

COMMITMENT_LEVELS = {"hard", "goal_critical", "maintenance", "optional"}
COMMITMENT_TYPES = {"hard", "semi_fixed"}
ACTION_LEVELS = {"goal_critical", "maintenance", "optional"}
ACTION_STATUSES = {"active", "completed", "cancelled", "missed", "archived"}
COMMITMENT_STATUSES = {"active", "completed", "cancelled", "missed", "archived"}
DOMAINS = {"learning", "fitness", "kitchen", "home", "admin", "personal"}

STATUS_TRANSITIONS = {
    "active": {"completed", "cancelled", "missed"},
    "completed": {"archived"},
    "cancelled": {"archived"},
    "missed": {"archived"},
    "archived": set(),
}


def normalize_token(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def validate_choice(value: str, allowed: set[str], field_name: str) -> str:
    normalized = normalize_token(value)
    if normalized not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {field_name}: {value}.",
        )
    return normalized


def validate_status_transition(current: str, target: str) -> str:
    normalized_target = validate_choice(target, ACTION_STATUSES, "status")
    if normalized_target not in STATUS_TRANSITIONS.get(current, set()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid status transition from {current} to {normalized_target}.",
        )
    return normalized_target
