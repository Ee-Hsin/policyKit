"""Policy checker for job postings using OpenAI's API."""

import asyncio
from typing import List, Optional, Any
import re
from openai import AsyncOpenAI
from app.core.config import settings
from app.schemas.policy import (
    SecurityCheck,
    SecurityIssue,
    JobPostingVerification,
    PolicyCategoryScore,
    PolicyViolationContent,
    PolicyInvestigationResult,
    FinalOutput,
    create_policy_category_score_list_model,
)
from app.core.prompts import (
    get_job_posting_instructions,
    get_category_selection_instructions,
    get_policy_investigation_instructions
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.policy import PolicyCategory, Policy

class PolicyChecker:
    def __init__(self, db: AsyncSession, api_key: Optional[str] = None):
        self.db = db
        self.client = AsyncOpenAI(api_key=api_key)
    
    async def get_policy_categories(self):
        result = await self.db.execute(
            select(PolicyCategory).options(selectinload(PolicyCategory.policies))
        )
        return result.scalars().all()

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

        # Step 2: Verify if it's a job posting
        verification = await self._verify_job_posting(job_description)
        
        
        #Has to be EXTREMELY confident that it is NOT a job posting to return an invalid violation here
        if not verification.is_job_posting and verification.confidence > settings.JOB_POSTING_CONFIDENCE_THRESHOLD:
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

        # Step 3: Orchestrate policy investigations
        categories_to_investigate = await self._orchestrate_investigations(job_description)
        
        

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
        
        # Step 6: Create final output with validation
        return FinalOutput(
            has_violations=len(all_violations) > 0,
            violations=all_violations,
            metadata={
                "total_categories_checked": len(categories_to_investigate),
                "categories_investigated": [r.category for r in investigation_results]
            }
        )

    async def _check_security(self, text: str) -> SecurityCheck:
        """Check for security issues including prompt injections."""
        # First check for known injection patterns
        injection_issues = []
        text_lower = text.lower()
        
        
        # TODOWe can change this to an LLM call to check for injection patterns
        # with a list of patterns
        # and a confidence score
        for pattern in settings.INJECTION_PATTERNS:
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

    async def _verify_job_posting(self, text: str) -> JobPostingVerification:
        response = await self.client.responses.parse(
            model="gpt-4o-2024-08-06",
            input=[
                {"role": "system", "content": get_job_posting_instructions()},
                {"role": "user", "content": text}
            ],
            text_format=JobPostingVerification,
        )
        return response.output_parsed

    #ORchestrator LLM that takes in every category and their brief descriptions, then
    #decides which categories to investigate
    async def _orchestrate_investigations(self, text: str) -> List[Any]:
        # Fetch categories and their descriptions from the DB
        categories = await self.get_policy_categories()
        category_names = {cat.name for cat in categories}
        category_descriptions = [
            {
                "category_name": cat.name,
                "category_description": cat.description
            }
            for cat in categories
        ]
        
        # Create the dynamic model for validation
        DynamicPolicyCategoryScoreList = create_policy_category_score_list_model(category_names)
        
        print("--------------------------------")
        print("category_descriptions", category_descriptions)
        print("--------------------------------")
        
        response = await self.client.responses.parse(
            model="gpt-4o-2024-08-06",
            input=[
                {"role": "system", "content": get_category_selection_instructions(category_descriptions)},
                {"role": "user", "content": text}
            ],
            text_format=DynamicPolicyCategoryScoreList
        )
        
        print("--------------------------------")
        print("categories to investigate", response.output_parsed.categories)
        print("--------------------------------")
        
        return response.output_parsed.categories

    async def _run_parallel_investigations(
        self, 
        text: str, 
        categories: List[PolicyCategoryScore]
    ) -> List[PolicyInvestigationResult]:
        """Run parallel investigations for policy categories."""
        # Create tasks for parallel execution
        # we only want to investigate the top 3 categories
        top_3_categories = sorted(categories, key=lambda x: x.confidence, reverse=True)[:settings.MAX_PARALLEL_INVESTIGATIONS]
        #only investigate categories that are above the threshold
        categories_to_investigate = [category for category in top_3_categories if category.confidence > settings.POLICY_INVESTIGATION_THRESHOLD]
        
        print("--------------------------------")
        print("categories_to_investigate", categories_to_investigate)
        print("--------------------------------")
        
        tasks = [
            self._investigate_category(text, category)
            for category in categories_to_investigate
        ]
        
        # Run investigations in parallel with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=settings.LLM_INVESTIGATION_TIMEOUT
            )
            
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
                    category="undefined",
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
                category="undefined",
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
            category="undefined",
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
        # Fetch category and its policies from the DB
        db_category = await self.db.execute(
            select(PolicyCategory).options(selectinload(PolicyCategory.policies)).where(PolicyCategory.name == category.category)
        )
        db_category = db_category.scalars().first()
        if not db_category:
            raise ValueError(f"Category {category.category} not found in DB")
        category_data = {
            "description": db_category.description,
            "policies": [
                {"title": p.title, "description": p.description, "extra_metadata": p.extra_metadata}
                for p in db_category.policies
            ]
        }
        response = await self.client.responses.parse(
            model="gpt-4o-2024-08-06",
            input=[
                {"role": "system", "content": get_policy_investigation_instructions(category.category, category_data)},
                {"role": "user", "content": text}
            ],
            text_format=PolicyInvestigationResult
        )
        return response.output_parsed 