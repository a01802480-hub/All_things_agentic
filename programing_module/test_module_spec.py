from module_spec import ModuleSpec


print("=== TEST 1: Complete ModuleSpec ===")

complete_spec = ModuleSpec(
    module_name="PracticeAnalysisModule",

    purpose=(
        "Analyze historical guitar practice data "
        "to identify weaknesses and trends."
    ),

    inputs=[
        "practice_history"
    ],

    outputs=[
        "weaknesses",
        "trends",
        "recommendations"
    ],

    methods=[
        {
            "name": "analyze",
            "description": (
                "Analyze practice history and identify "
                "patterns and weaknesses."
            ),
            "inputs": [
                "practice_history"
            ],
            "outputs": [
                "weaknesses",
                "trends"
            ]
        }
    ],

    dependencies=[
        "LLMProvider",
        "MemoryModule"
    ]
)

print(complete_spec.validate())

print("\nModule Specification:")
print(complete_spec.to_dict())


print("\n=== TEST 2: Incomplete ModuleSpec ===")

incomplete_spec = ModuleSpec(
    module_name="IncompleteModule",
    purpose=None,
    inputs=[],
    outputs=[]
)

print(incomplete_spec.validate())
