from libs.schemas.base import NextActionType, SessionState


class SessionStateMachine:
    def next_state(self, current: SessionState, action: NextActionType) -> SessionState:
        if action == NextActionType.END:
            return SessionState.S_END
        if action == NextActionType.SCAFFOLD:
            return SessionState.S_SCAFFOLD
        if action == NextActionType.PROBE:
            return SessionState.S_PROBE
        if action == NextActionType.WAIT:
            return SessionState.S_WAIT
        if current == SessionState.S_INIT:
            return SessionState.S_WAIT
        return SessionState.S_EVAL_RT
