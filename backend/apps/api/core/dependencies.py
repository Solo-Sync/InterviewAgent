from services.orchestrator.service import OrchestratorService

orchestrator = OrchestratorService()


def get_orchestrator() -> OrchestratorService:
    return orchestrator
