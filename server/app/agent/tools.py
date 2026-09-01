"""Tool contracts exposed to the compliance agent."""

AGENT_TOOLS = [
    {
        "type": "function",
        "name": "resolve_scope",
        "description": (
            "Resolve the posting's hiring locations into policy jurisdictions. Use this before "
            "the first compliance check and after hiring locations change."
        ),
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        "strict": True,
    },
    {
        "type": "function",
        "name": "set_hiring_locations",
        "description": (
            "Save hiring locations supplied by the recruiter. Use only when a user message "
            "clearly provides or corrects those locations."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "locations": {"type": "array", "items": {"type": "string"}, "minItems": 1}
            },
            "required": ["locations"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "run_compliance_check",
        "description": (
            "Run the constrained full-coverage checker against every applicable policy. "
            "Use before proposing edits and again after an approved revision."
        ),
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        "strict": True,
    },
    {
        "type": "function",
        "name": "search_policies",
        "description": (
            "Search indexed policy passages when a finding needs deeper investigation. Search "
            "is supporting research and does not replace the full compliance check."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 3},
                "category": {"type": ["string", "null"]},
                "jurisdiction": {"type": ["string", "null"]},
            },
            "required": ["query", "category", "jurisdiction"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "read_policy",
        "description": "Read one complete canonical policy from PostgreSQL by stable policy key.",
        "parameters": {
            "type": "object",
            "properties": {"policy_key": {"type": "string"}},
            "required": ["policy_key"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "search_reviewed_precedents",
        "description": (
            "Find similar cases that a human reviewer approved. Use only for ambiguous language; "
            "a precedent is evidence, not an automatic verdict."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 3},
                "category": {"type": ["string", "null"]},
                "jurisdiction": {"type": ["string", "null"]},
            },
            "required": ["query", "category", "jurisdiction"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "propose_revision",
        "description": (
            "Save one revised posting and its exact changes for recruiter approval. Preserve the "
            "role's meaning and address only supported compliance findings."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "revised_text": {"type": "string", "minLength": 30},
                "changes": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "original_text": {"type": "string", "minLength": 1},
                            "replacement_text": {"type": "string"},
                            "reason": {"type": "string", "minLength": 1},
                            "policy_keys": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 1,
                            },
                        },
                        "required": [
                            "original_text",
                            "replacement_text",
                            "reason",
                            "policy_keys",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["revised_text", "changes"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "ask_recruiter",
        "description": (
            "Pause and ask one focused question when a fact required for compliance or a safe "
            "revision is missing."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "minLength": 5},
                "reason": {"type": "string", "minLength": 5},
            },
            "required": ["question", "reason"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "escalate_to_reviewer",
        "description": (
            "Stop and request human policy judgment when evidence conflicts, a rule is ambiguous, "
            "or no safe revision can preserve the posting's meaning."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "minLength": 5},
                "policy_keys": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["summary", "policy_keys"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "complete_session",
        "description": (
            "Request ready-to-publish status. Python will reject this unless the latest approved "
            "draft has a complete check with no violations or uncertainties."
        ),
        "parameters": {
            "type": "object",
            "properties": {"summary": {"type": "string", "minLength": 5}},
            "required": ["summary"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]
