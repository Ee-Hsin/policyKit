"""Policy checker for job postings using OpenAI's API."""

from typing import List, Optional, Any, Type, Dict
from openai import AsyncOpenAI
from app.core.config import settings
from app.schemas.policy import (
    SecurityCheck,
    JobPostingVerification,
    SafetyKitViolation,
    StandardViolation,
    FinalOutput,
    CategoryInvestigation,
    create_policy_category_score_list_model,
)
from app.core.prompts import (
    get_job_posting_instructions,
    get_category_selection_instructions,
    get_investigate_category_instructions
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.policy import PolicyCategory, Policy
from pydantic import BaseModel
import asyncio

class PolicyChecker:
    def __init__(self, db: AsyncSession, api_key: Optional[str] = None):
        self.db = db
        self.client = AsyncOpenAI(api_key=api_key)
    
    async def get_categories(self):
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
                violations=[SafetyKitViolation(
                    category="PROMPT_INJECTION",
                    confidence=1.0,
                    reasoning="Detected potential prompt injection patterns"
                )]
            )

        # Step 2: Verify if it's a job posting
        verification = await self._verify_job_posting(job_description)
        
        #Has to be EXTREMELY confident that it is NOT a job posting to return an invalid violation here
        if not verification.is_job_posting and verification.confidence > settings.JOB_POSTING_CONFIDENCE_THRESHOLD:
            return FinalOutput(
                has_violations=True,
                violations=[SafetyKitViolation(
                    category="NOT_A_JOB_POSTING",
                    confidence=verification.confidence,
                    reasoning=verification.reasoning
                )]
            )
            
        #Retrieve categories
        categories = await self.get_categories()
        # Create the dynamic model for validation        
        #Let's get the category name and database id
        category_names = set()
        category_ids = set()
        for cat in categories:
            category_names.add(cat.name)
            category_ids.add(cat.id)
            
        print("--------------------------------")
        print("category_names", category_names)
        print("--------------------------------")
        print("category_ids", category_ids)
        print("--------------------------------")
        
        DynamicPolicyCategoryScoreList = create_policy_category_score_list_model(category_names, category_ids)

        print("--------------------------------")
        print("DynamicPolicyCategoryScoreList", DynamicPolicyCategoryScoreList)
        print("--------------------------------")

        # Step 3: Orchestrate policy investigations and returns a DynamicPolicyCategoryScoreList
        categories_to_investigate = await self._orchestrate_investigations(
            job_description, 
            categories, 
            DynamicPolicyCategoryScoreList
        )
                
        #Now we have a list of categories to investigate as well as the confidence scores and reasoning for each category
        # first only investigate the top 3 categories that all must have a confidence score above the threshold
        categories_to_investigate = [cat for cat in categories_to_investigate if cat.confidence > settings.POLICY_INVESTIGATION_CONFIDENCE_THRESHOLD][:3]
        
        print("--------------------------------")
        print("categories to investigate", categories_to_investigate)
        print("--------------------------------")
        
        #Now we get the policies for each category
        #query the db for the policies
        list_of_categories_with_policies = []
        for cat in categories_to_investigate:
            policies = await self.db.execute(
                select(Policy).where(Policy.category_id == cat.category_id)
            )
            list_of_categories_with_policies.append({
                "category": cat.category,
                "category_id": cat.category_id,
                "policies": policies.scalars().all()
            })
            
        #Now we have a list of policies to investigate
        print("--------------------------------")
        print("list_of_categories_with_policies", list_of_categories_with_policies)
        print("--------------------------------")
        
        investigation_results = await self._investigate_categories(job_description,list_of_categories_with_policies)
        
        # Now we have a list of investigation results. More specifically,
        # a list of CategoryInvestigation
        
        # Let's filter by confidence score
        investigation_results = [result for result in investigation_results if result.confidence > settings.FINAL_OUTPUT_CONFIDENCE_THRESHOLD]
        
        # Let's now make a list of violations in which there are violation objects
        # I want every violation to have:
        # 1. Category of Violation (in it's name, so we'll have to query db using result.category_id)
        # 2. Name of Policies in that Category violated (in it's name, so we'll have to query db using result.policies_violated_id)
        # 3. The reasoning of the violation (just result.reasoning)
        # 4. The content that violated (just result.content)
        
        violations = []
        for result in investigation_results:
            category_result = await self.db.execute(
                select(PolicyCategory).where(PolicyCategory.id == result.category_id)
            )
            category = category_result.scalar_one()
            
            policy_titles = []
            for policy_id in result.policies_violated_ids:
                policy_result = await self.db.execute(
                    select(Policy).where(Policy.id == policy_id)
                )
                policy = policy_result.scalar_one()
                policy_titles.append(policy.title)
                
            violations.append(StandardViolation(
                category=category.name,
                policy=policy_titles,
                reasoning=result.reasoning,
                content=result.content
            ))
            
        return FinalOutput(
            has_violations=len(violations) > 0,
            violations=violations
        )
        

    async def _check_security(self, text: str) -> SecurityCheck:
        """Check for security issues including prompt injections."""
        # First check for known injection patterns
        injection_issues = []
        text_lower = text.lower()
        
        # TODOWe can change this to an LLM call to check for injection patterns
        # with a list of patterns and a confidence score
        for pattern in settings.INJECTION_PATTERNS:
            if pattern["pattern"] in text_lower:
                injection_issues.append(pattern["pattern"])
        
        # If we found injection patterns, return immediately
        if injection_issues:
            return SecurityCheck(
                is_safe=False,
                confidence=1.0,
                reasoning="Detected potential prompt injection patterns"
            )
        else:
            # If no injection patterns, return safe
            return SecurityCheck(
                is_safe=True,
                confidence=1.0,
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
    async def _orchestrate_investigations(
        self, 
        text: str, 
        categories: List[PolicyCategory], 
        DynamicPolicyCategoryScoreList: Type[BaseModel]
    ) -> List[Any]:
        # Fetch categories and their descriptions from the DB
        category_descriptions = [
            {
                "category_name": cat.name,
                "category_id": cat.id,
                "category_description": cat.description
            }
            for cat in categories
        ]
                
        response = await self.client.responses.parse(
            model="gpt-4o-2024-08-06",
            input=[
                {"role": "system", "content": get_category_selection_instructions(category_descriptions)},
                {"role": "user", "content": text}
            ],
            text_format=DynamicPolicyCategoryScoreList
        )
                
        return response.output_parsed.categories
    
    
    # Make a call to the LLM to investigate each category (every item in the list) and return a list of violations
    async def _investigate_categories(self, job_description: str, categories_with_policies: List[Dict[str, Any]]) -> List[CategoryInvestigation]:
        """Investigate each category and return a list of violations."""
        
        # Here we need to queue a bunch of _investigate_individual_category function calls
        # into an array and then use asyncio to run them at the same time
        tasks = []
        for cat in categories_with_policies:
            tasks.append(self._investigate_individual_category(job_description, cat))
        
        #TODO: Handle failures here
        results = await asyncio.gather(*tasks)
        
        return results
        
    async def _investigate_individual_category(self, job_description: str, category_with_policies: Dict[str, Any]) -> CategoryInvestigation:
        """Investigate an individual category and return a list of violations."""
          
        
        # Make a call to the LLM to investigate the category
        response = await self.client.responses.parse(
            model="gpt-4o-2024-08-06",
            input=[
                {"role": "system", "content": get_investigate_category_instructions(category_with_policies)},
                {"role": "user", "content": job_description}
            ],
            text_format=CategoryInvestigation
        )
        
        return response.output_parsed
        
        
        
        
        
        