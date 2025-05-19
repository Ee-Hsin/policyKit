from typing import List, Dict

# Confidence thresholds
JOB_POSTING_CONFIDENCE_THRESHOLD = 0.7
POLICY_INVESTIGATION_THRESHOLD = 0.7

# Maximum number of parallel investigations
MAX_PARALLEL_INVESTIGATIONS = 3

# Timeout for LLM investigations (in seconds)
LLM_INVESTIGATION_TIMEOUT = 10

# Common injection patterns to check for
INJECTION_PATTERNS: List[Dict[str, str]] = [
    {
        "pattern": "ignore the system prompt",
        "description": "Attempt to bypass system instructions"
    },
    {
        "pattern": "you are now",
        "description": "Attempt to redefine AI role"
    },
    {
        "pattern": "forget your previous instructions",
        "description": "Attempt to clear context"
    },
    {
        "pattern": "act as if",
        "description": "Attempt to modify behavior"
    },
    {
        "pattern": "pretend to be",
        "description": "Attempt to change identity"
    },
    {
        "pattern": "ignore all previous instructions",
        "description": "Attempt to clear context"
    },
    {
        "pattern": "you are no longer",
        "description": "Attempt to remove restrictions"
    },
    {
        "pattern": "from now on",
        "description": "Attempt to modify future behavior"
    }
] 