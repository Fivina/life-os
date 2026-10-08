from app.domains.base import DomainModule


class KitchenDomain(DomainModule):
    name = "kitchen"

    def get_state(self, user_id: str) -> dict:
        return {"domain": self.name, "status": "v0.8_active", "owns": ["inventory", "recipes", "nutrition", "shopping_needs"]}

    def get_metrics(self, user_id: str) -> dict:
        return {"inventory": "lot_based", "recommendations": "deterministic", "planner_bridge": "candidate_actions"}

    def get_goals(self, user_id: str) -> list[dict]:
        return []

    def get_constraints(self, user_id: str) -> list[dict]:
        return []

    def generate_candidate_actions(self, user_id: str) -> list[dict]:
        # Candidate Actions are synced by the Kitchen service because it needs a database session.
        return []

    def handle_event(self, event: dict) -> None:
        return None

    def build_agent_context(self, user_id: str) -> dict:
        return {
            "allowed_context": ["inventory_lots", "recipes", "nutrition_targets", "shopping_needs", "recommendations"],
            "role": "CHEF",
            "boundary": "Kitchen never writes PlanBlocks directly.",
        }
