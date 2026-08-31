from programming_request import ProgrammingRequest

print("=== TEST 1: Complete Request ===")

complete_request = ProgrammingRequest(
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
        "No existing module can analyze historical "
        "practice data and identify weaknesses."
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

print(complete_request.validate())


print("\n=== TEST 2: Incomplete Request ===")

incomplete_request = ProgrammingRequest(
    user_goal="Improve guitar practice",

    missing_capability="practice_analysis"
)

print(incomplete_request.validate())
