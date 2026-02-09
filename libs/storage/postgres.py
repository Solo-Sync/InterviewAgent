from libs.schemas.base import Session, Turn


class SessionRepository:
    async def create_session(self, session: Session) -> Session:
        return session

    async def get_session(self, session_id: str) -> Session | None:
        return None

    async def list_turns(self, session_id: str, limit: int, cursor: str | None) -> tuple[list[Turn], str | None]:
        return [], None


class EventWriter:
    async def append(self, session_id: str, event_type: str, payload: dict, turn_id: str | None = None) -> None:
        return None
