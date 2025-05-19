"""Policy checker for job postings using OpenAI's API."""

import os
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re
from openai import AsyncOpenAI
from src.config import (
    JOB_POSTING_CONFIDENCE_THRESHOLD,
    POLICY_INVESTIGATION_THRESHOLD,
    MAX_PARALLEL_INVESTIGATIONS,
    LLM_INVESTIGATION_TIMEOUT,
    INJECTION_PATTERNS
)
from src.models import (
    SecurityCheck,
    SecurityIssue,
    JobPostingVerification,
    PolicyCategoryScore,
    PolicyCategoryScoreList,
    PolicyViolationContent,
    PolicyInvestigationResult,
    FinalOutput,
    PolicyCategory
)
from src.prompts import (
    get_job_posting_instructions,
    get_category_selection_instructions,
    get_policy_investigation_instructions
)

class PolicyChecker:
    def __init__(self, policies_file: str = "sample_policies.json", api_key: Optional[str] = None):
        self.policies_data = self._load_policies(policies_file)
        self.client = AsyncOpenAI(api_key=api_key)
    
    def _load_policies(self, policies_file: str) -> Dict:
        """Load policies from JSON file."""
        file_path = Path(__file__).parent / policies_file
        print(f"Loading policies from: {file_path}")
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: Policies file not found at {file_path}")
            raise
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in policies file: {e}")
            raise
        except Exception as e:
            print(f"Error loading policies: {e}")
            raise
    
    async def check_job_posting(self, 
                              job_description: str, 
                              image_path: Optional[str] = None) -> FinalOutput:
        """
        Check a job posting against all policies.
        
        Args:
            job_description: The text content of the job posting
            image_path: Optional path to an image associated with the job posting
            
        Returns:
            FinalOutput containing any policy violations found
        """
        
        # Step 1: Check for security issues first
        security_check = await self._check_security(job_description)
        if not security_check.is_safe:
            return FinalOutput(
                has_violations=True,
                violations=[
                    PolicyViolationContent(
                        policy_id="SECURITY",
                        policy_title="Security Issue Detected",
                        violated_content=job_description,
                        justification=security_check.reasoning,
                        confidence=security_check.confidence
                    )
                ],
                metadata={
                    "security_issues": security_check.security_issues,
                    "security_confidence": security_check.confidence
                }
            )
        print("--------------------------------")
        print("security_check", security_check)
        print("--------------------------------")
        # Step 2: Verify if it's a job posting
        verification = await self._verify_job_posting(job_description)
        if not verification.is_job_posting or verification.confidence < JOB_POSTING_CONFIDENCE_THRESHOLD:
            return FinalOutput(
                has_violations=True,
                violations=[
                    PolicyViolationContent(
                        policy_id="INVALID",
                        policy_title="Not a Job Posting",
                        violated_content=job_description,
                        justification=f"Content does not appear to be a job posting (confidence: {verification.confidence})",
                        confidence=verification.confidence
                    )
                ]
            )
        print("--------------------------------")
        print("verification", verification)
        print("--------------------------------")
        # Step 3: Orchestrate policy investigations
        categories_to_investigate = await self._orchestrate_investigations(job_description)
        print("--------------------------------")
        print("categories_to_investigate", categories_to_investigate)
        print("--------------------------------")
        # Step 4: Run parallel investigations
        investigation_results = await self._run_parallel_investigations(
            job_description, 
            categories_to_investigate
        )
        print("--------------------------------")
        print("investigation_results", investigation_results)
        print("--------------------------------")
        # Step 5: Aggregate results
        all_violations = []
        for result in investigation_results:
            all_violations.extend(result.violations)
            
        print("--------------------------------")
        print("all_violations", all_violations)
        print("--------------------------------")
        
        # Step 6: Create final output with validation
        return FinalOutput(
            has_violations=len(all_violations) > 0,
            violations=all_violations,
            metadata={
                "total_categories_checked": len(categories_to_investigate),
                "categories_investigated": [r.category.value for r in investigation_results]
            }
        )

    async def _check_security(self, text: str) -> SecurityCheck:
        """Check for security issues including prompt injections."""
        # First check for known injection patterns
        injection_issues = []
        text_lower = text.lower()
        
        for pattern in INJECTION_PATTERNS:
            if pattern["pattern"] in text_lower:
                injection_issues.append(SecurityIssue(
                    type="injection_pattern",
                    pattern=pattern["pattern"],
                    description=pattern["description"]
                ))
        
        # If we found injection patterns, return immediately
        if injection_issues:
            return SecurityCheck(
                is_safe=False,
                confidence=1.0,
                security_issues=injection_issues,
                reasoning="Detected potential prompt injection patterns"
            )
        # If no injection patterns, return safe
        return SecurityCheck(
            is_safe=True,
            confidence=1.0,
            security_issues=[],
            reasoning="No injection patterns detected"
        )
        
        # If no obvious injection patterns, use LLM to check for more subtle issues
        # response = await self.client.responses.parse(

    async def _verify_job_posting(self, text: str) -> JobPostingVerification:
        """Verify if the content is a job posting using structured output."""
        response = await self.client.responses.parse(
            model="gpt-4o",
            input=text,
            instructions=get_job_posting_instructions(),
            text_format=JobPostingVerification
        )
        return response.output[0].content[0].parsed

    async def _orchestrate_investigations(self, text: str) -> List[PolicyCategoryScore]:
        """Determine which policy categories need investigation."""
        # Get category descriptions for context
        print("--------------------------------")
        print("policies_data", self.policies_data)
        print("--------------------------------")
        
        # Only use categories that exist in policies_data
        category_descriptions = {
            category.value: self.policies_data["categories"][category.value]["description"]
            for category in PolicyCategory
            if category.value in self.policies_data["categories"]
        }
        
        print("--------------------------------")
        print("category_descriptions", category_descriptions)
        print("--------------------------------")
        
        response = await self.client.responses.parse(
            model="gpt-4o",
            input=text,
            instructions=get_category_selection_instructions(category_descriptions),
            text_format=PolicyCategoryScoreList
        )
        return response.output[0].content[0].parsed.categories

    async def _run_parallel_investigations(
        self, 
        text: str, 
        categories: List[PolicyCategoryScore]
    ) -> List[PolicyInvestigationResult]:
        """Run parallel investigations for policy categories."""
            
        # Create tasks for parallel execution
        # we only want to investigate the top 3 categories
        top_3_categories = sorted(categories, key=lambda x: x.confidence, reverse=True)[:MAX_PARALLEL_INVESTIGATIONS]
        #only investigate categories that are above the threshold
        categories_to_investigate = [category for category in top_3_categories if category.confidence > POLICY_INVESTIGATION_THRESHOLD]
        tasks = [
            self._investigate_category(text, category)
            for category in categories_to_investigate
        ]
        
        print("--------------------------------")
        print("categories_to_investigate", categories_to_investigate)
        print("--------------------------------")
        
        # Run investigations in parallel with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=LLM_INVESTIGATION_TIMEOUT
            )
            
            print("--------------------------------")
            print("results", results)
            print("--------------------------------")
            
            # Filter out any failed investigations
            successful_results = []
            failed_results = []
            
            for result in results:
                if isinstance(result, PolicyInvestigationResult):
                    successful_results.append(result)
                else:
                    failed_results.append(str(result))
            
            if failed_results:
                print(f"Failed investigations: {failed_results}")
            
            # If we have no successful results, return a failure result
            if not successful_results and results:
                return [PolicyInvestigationResult(
                    category=PolicyCategory.UNDEFINED,  # Default to Undefined category for error cases
                    confidence=0.0,
                    violations=[PolicyViolationContent(
                        policy_id="INVESTIGATION_FAILED",
                        policy_title="Investigation Failed",
                        violated_content=text,
                        justification=f"Policy investigations failed: {', '.join(failed_results)}",
                        confidence=0.0
                    )],
                    reasoning="Policy investigations failed to complete successfully"
                )]
            
            return successful_results
            
        except asyncio.TimeoutError:
            print("Investigation timeout exceeded")
            return [self._create_timeout_result(text, "All policy investigations exceeded the timeout limit")]
        except Exception as e:
            print(f"Unexpected error in parallel investigations: {str(e)}")
            return [PolicyInvestigationResult(
                category=PolicyCategory.UNDEFINED,  # Default to Undefined category for error cases
                confidence=0.0,
                violations=[PolicyViolationContent(
                    policy_id="INVESTIGATION_ERROR",
                    policy_title="Investigation Error",
                    violated_content=text,
                    justification=f"Unexpected error: {str(e)}",
                    confidence=0.0
                )],
                reasoning="Unexpected error during policy investigations"
            )]

    def _create_timeout_result(self, text: str, justification: str) -> PolicyInvestigationResult:
        """Create a timeout result with the given justification."""
        return PolicyInvestigationResult(
            category=PolicyCategory.UNDEFINED,  # Default to Undefined category for error cases
            confidence=0.0,
            violations=[PolicyViolationContent(
                policy_id="TIMEOUT",
                policy_title="Investigation Timeout",
                violated_content=text,
                justification=justification,
                confidence=0.0
            )],
            reasoning="Policy investigations timed out"
        )

    async def _investigate_category(
        self, 
        text: str, 
        category: PolicyCategoryScore
    ) -> PolicyInvestigationResult:
        """Investigate a specific policy category using structured output."""
        try:
            # Get relevant policies for this category
            category_data = self.policies_data["categories"][category.category.value]
            
            response = await self.client.responses.parse(
                model="gpt-4o",
                input=text,
                instructions=get_policy_investigation_instructions(category.category.value, category_data),
                text_format=PolicyInvestigationResult
            )
            
            result = response.output[0].content[0].parsed
            return result
        except Exception as e:
            print(f"Error investigating category {category.category.value}: {str(e)}")
            raise 