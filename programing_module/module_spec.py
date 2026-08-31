class ModuleSpec:
    """
    Represents the technical specification
    of a module before code generation.
    """

    def __init__(
        self,
        module_name,
        purpose,
        inputs,
        outputs,
        methods=None,
        dependencies=None
    ):
        self.module_name = module_name
        self.purpose = purpose
        self.inputs = inputs
        self.outputs = outputs
        self.methods = methods or []
        self.dependencies = dependencies or []

    def get_missing_critical_fields(self):
        missing = []

        if not self.module_name:
            missing.append("module_name")

        if not self.purpose:
            missing.append("purpose")

        if not self.inputs:
            missing.append("inputs")

        if not self.outputs:
            missing.append("outputs")

        return missing

    def validate(self):
        missing = self.get_missing_critical_fields()

        return {
            "is_valid": len(missing) == 0,
            "missing_critical": missing
        }

    def to_dict(self):
        return {
            "module_name": self.module_name,
            "purpose": self.purpose,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "methods": self.methods,
            "dependencies": self.dependencies
        }
        