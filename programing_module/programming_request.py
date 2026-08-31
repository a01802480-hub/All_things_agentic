class ProgrammingRequest:
    """
    Represents a structured request sent by the Main Agent
    to the Programming Module.
    """

    def __init__(
        self,
        user_goal=None,
        preliminary_plan=None,
        execution_context=None,
        missing_capability=None,
        capability_reason=None,
        expected_inputs=None,
        expected_outputs=None
    ):
        self.user_goal = user_goal
        self.preliminary_plan = preliminary_plan or []
        self.execution_context = execution_context or {}

        self.missing_capability = missing_capability
        self.capability_reason = capability_reason

        self.expected_inputs = expected_inputs or []
        self.expected_outputs = expected_outputs or []

    def get_missing_critical_fields(self):
        missing = []

        if not self.missing_capability:
            missing.append("missing_capability")

        if not self.expected_inputs:
            missing.append("expected_inputs")

        if not self.expected_outputs:
            missing.append("expected_outputs")

        return missing

    def get_missing_context_fields(self):
        missing = []

        if not self.user_goal:
            missing.append("user_goal")

        if not self.preliminary_plan:
            missing.append("preliminary_plan")

        if not self.execution_context:
            missing.append("execution_context")

        if not self.capability_reason:
            missing.append("capability_reason")

        return missing

    def validate(self):
        critical_missing = self.get_missing_critical_fields()
        context_missing = self.get_missing_context_fields()

        return {
            "is_valid": len(critical_missing) == 0,
            "missing_critical": critical_missing,
            "missing_context": context_missing
        }
        