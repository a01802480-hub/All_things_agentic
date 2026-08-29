import os
import sys
import json
def get_current_directory() -> str:
    return os.path.dirname(os.path.abspath(__file__))
