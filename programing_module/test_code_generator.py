import sys
import 

sys.path.append(os.path.dirname(__file__))

from programming_module import ProgrammingModule
from programming_request import ProgrammingRequest


request = ProgrammingRequest(
    user_goal="Analyze guitar practice history",
    preliminary_plan="Review historical practice data",
    execution_context="The agent needs to identify weaknesses",
    missing_capability="Practice analysis",
    capability_reason="No existing module can analyze practice history",
    expected_inputs=["practice_history"],
    expected_outputs=["weaknesses", "trends", "recommendations"]
)

programming_module = ProgrammingModule()

result = programming_module.process_request(request)

print("\n=== VALIDATION ===")
print(result["validation"])

print("\n=== MODULE SPEC ===")
print(result["module_spec"].to_dict())

print("\n=== GENERATED CODE ===")
print(result["generated_code"])