import asyncio
import sys
import os
import logging

# Configure root-level logging for the entire system
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("SystemBoot")

# Calculate absolute paths to ensure imports work no matter where you run the script from
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
THE_ARCHITECT_DIR = os.path.join(PROJECT_ROOT, "The architect")

# Add the project root to the system path so sibling modules can find each other
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Critical: Because your folder is named "The architect" (with a space), standard Python 
# imports like `from The architect import...` will throw a SyntaxError. 
# By adding the folder directly to the path, we bypass this limitation.
if THE_ARCHITECT_DIR not in sys.path:
    sys.path.insert(0, THE_ARCHITECT_DIR)

try:
    # Now we can safely import from chat_to_architect.py as if it were in the root directory
    from chat_to_architect import ChatAnalyzer
except ImportError as e:
    logger.error(f"CRITICAL BOOT FAILURE: Could not import ChatAnalyzer. Ensure folders are correct. Error: {e}")
    sys.exit(1)

async def main_loop():
    """
    The main interactive loop for the hackathon demo.
    It takes user input from the terminal and feeds it into the ChatAnalyzer.
    """
    print("\n" + "="*60)
    print(" ALL THINGS AGENTIC - ARCHITECT TERMINAL BOOTING ")
    print("="*60)
    
    logger.info("Initializing system components...")
    
    # Instantiate the front-door of our system
    analyzer = ChatAnalyzer()
    
    # Hardcoded user_id for the hackathon demo (can be dynamic if you add a login module)
    current_user_id = "USER_12345"
    
    print("\n" + "="*60)
    print("✅ SYSTEM READY")
    print("Type your request below. Type 'exit' or 'quit' to shut down.")
    print("="*60)
    
    # Continuous interaction loop
    while True:
        try:
            # 1. ONLY user-facing prompt in the entire backend system
            user_input = input(f"\n[{current_user_id}] >> ")
            
            if user_input.lower().strip() in ['exit', 'quit']:
                print("\nShutting down The Arcitect. Goodbye!")
                break
                
            if not user_input.strip():
                continue
                
            print("\n--- Processing Request ---")
            
            # 2. Feed the chat into the Analyzer -> Architect -> Workers pipeline
            final_state = await analyzer.handle_incoming_message(current_user_id, user_input)
            
            # 3. Output the final system state/results to the terminal
            print("\n" + "="*60)
            print(" WORKFLOW COMPLETED ")
            print("="*60)
            if final_state and hasattr(final_state, 'tasks'):
                for task_id, task in final_state.tasks.items():
                    status = task.status
                    
                    # NEW LOGIC: Check for errors first!
                    if status == "FAILED" and task.error:
                        result = f"⚠️ ERROR: {task.error}"
                    else:
                        result = task.result if task.result else "No result generated."
                        
                    print(f"\nTask [{task_id}] - {task.description}\nStatus: {status}\nOutput: {result}")
            else:
                print("System processed the request but returned an unexpected state.")
                
        except KeyboardInterrupt:
            # Handle CTRL+C gracefully
            print("\nForce quitting...")
            break
        except Exception as e:
            logger.error(f"An unexpected error occurred during execution: {e}")

if __name__ == "__main__":
    # Ensure compatible async execution on Windows (prevents ProactorEventLoop errors)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    try:
        asyncio.run(main_loop())
    except Exception as fatal_e:
        logger.fatal(f"System crashed completely: {fatal_e}")
