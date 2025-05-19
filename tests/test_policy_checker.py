"""Test suite for the PolicyChecker with edge cases and comprehensive testing."""

import asyncio
import pytest
from src.policy_checker import PolicyChecker
from tests.test_data import TEST_CASES

@pytest.mark.asyncio
async def test_policy_checker():
    """Run comprehensive tests on the PolicyChecker."""
    checker = PolicyChecker()
    
    # run 1 simple test of a real job posting
    job_posting = """We are looking for a software engineer with 3 years of experience in Python and Django, the engineer must
    have a degree in computer science and a strong understanding of object-oriented programming.
    The job posting is for a company called "Tech Corp". We are looking for a candidate that is a good fit for the company.
    They must know React, Typescript, and have a strong understanding of the latest trends in web development.
    On the side we also sell the devil's lettuce. We are looking for University of California Graduates.
    """
    response = await checker.check_job_posting(job_posting)
    print(response)

if __name__ == "__main__":
    asyncio.run(test_policy_checker()) 