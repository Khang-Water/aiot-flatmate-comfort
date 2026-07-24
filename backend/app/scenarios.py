from pathlib import Path

from app.models import ScenarioDefinition, ScenarioSummary


class ScenarioRepository:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._scenarios: dict[str, ScenarioDefinition] = {}

    def load(self) -> None:
        scenarios = [
            ScenarioDefinition.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(self.directory.glob("*.json"))
        ]
        self._scenarios = {scenario.id: scenario for scenario in scenarios}

    def get(self, scenario_id: str) -> ScenarioDefinition | None:
        return self._scenarios.get(scenario_id)

    def summaries(self) -> list[ScenarioSummary]:
        return [
            ScenarioSummary(
                id=scenario.id,
                name_vi=scenario.name_vi,
                description_vi=scenario.description_vi,
                duration_minutes=scenario.duration_minutes,
            )
            for scenario in self._scenarios.values()
        ]
