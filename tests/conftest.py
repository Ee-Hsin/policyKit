"""Test fixtures for the policy checker tests."""

import pytest
from app.services.policy_checker import PolicyChecker

@pytest.fixture
async def policy_checker():
    """Create a PolicyChecker instance for testing."""
    checker = PolicyChecker()
    return checker

@pytest.fixture
def sample_valid_job_posting():
    """Return a sample valid job posting."""
    return """Senior Software Engineer
We are looking for a Senior Software Engineer to join our team.
Requirements:
- 5+ years of experience
- Strong Python skills
- Bachelor's degree in Computer Science or related field
Salary: $120k-$150k
Benefits: Health insurance, 401k, PTO"""

@pytest.fixture
def sample_invalid_job_posting():
    """Return a sample invalid job posting with policy violations."""
    return """Junior Developer
Looking for young, energetic developers fresh out of college.
Must be under 30 and willing to work long hours.
Prefer male candidates who can commit to the job without family distractions.
Salary: $60k""" 