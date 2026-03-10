from libs.schemas.base import NextActionType, ScaffoldLevel, TriggerType


class OrchestratorPolicy:
    def choose_action(self, trigger_types: set[TriggerType]) -> tuple[NextActionType, ScaffoldLevel | None]:
        if TriggerType.HELP_KEYWORD in trigger_types:
            return NextActionType.SCAFFOLD, ScaffoldLevel.L2
        if (
            TriggerType.STRESS_SIGNAL in trigger_types
            or TriggerType.OFFTRACK in trigger_types
            or TriggerType.LOOP in trigger_types
        ):
            return NextActionType.SCAFFOLD, ScaffoldLevel.L1
        return NextActionType.PROBE, None
