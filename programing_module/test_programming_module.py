from programming_request import ProgrammingRequest
from programming_module import ProgrammingModule


programming_module = ProgrammingModule()


print("=== TEST 1: Valid Programming Request ===")

valid_request = ProgrammingRequest(
    user_goal="Improve guitar practice",

    preliminary_plan=[
        "Retrieve practice history",
        "Analyze technical weaknesses",
        "Generate recommendations"
    ],

    execution_context={
        "current_step": 2,
        "current_task": "Analyze practice history",
        "previous_steps": [
            "Retrieve practice history"
        ],
        "next_steps": [
            "Generate personalized recommendations"
        ]
    },

    missing_capability="practice_analysis",

    capability_reason=(
        "Analyze historical guitar practice data "
        "to identify weaknesses and trends."
    ),

    expected_inputs=[
        "practice_history"
    ],

    expected_outputs=[
        "weaknesses",
        "trends",
        "recommendations"
    ]
)


result = programming_module.process_request(valid_request)

print("Success:", result["success"])
print("Validation:", result["validation"])

print("\nGenerated Module Specification:")

if result["module_spec"]:
    print(result["module_spec"].to_dict())


print("\n=== TEST 2: Invalid Programming Request ===")

invalid_request = ProgrammingRequest(
    user_goal="Improve guitar practice",
    missing_capability="practice_analysis"
)

result = programming_module.process_request(invalid_request)

print("Success:", result["success"])
print("Validation:", result["validation"])
print("Module Spec:", result["module_spec"])
