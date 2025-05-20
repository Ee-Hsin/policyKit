"""Script to seed the database with comprehensive policies and categories."""

import asyncio
from sqlalchemy import select
from app.core.database import async_session_factory
from app.models.policy import Policy, PolicyCategory

# Define new categories and policies
CATEGORIES = [
    {
        "name": "Discrimination",
        "description": "Policies related to discrimination based on race and gender."
    },
    {
        "name": "Legal Compliance",
        "description": "Policies related to legal compliance and prohibited activities."
    },
    {
        "name": "Workplace Standards",
        "description": "Policies related to workplace standards and professional conduct."
    },
    {
        "name": "Compensation",
        "description": "Policies related to compensation, benefits, and working conditions."
    },
    {
        "name": "Privacy and Security",
        "description": "Policies related to privacy, data protection, and security requirements."
    }
]

POLICIES = [
    # Discrimination Category
    {
        "category": "Discrimination",
        "title": "No Race Discrimination",
        "description": "Job postings must not discriminate based on race, ethnicity, or national origin.",
    },
    {
        "category": "Discrimination",
        "title": "No Gender Discrimination",
        "description": "Job postings must not discriminate based on gender, including requirements for specific gender.",
    },
    {
        "category": "Discrimination",
        "title": "No Age Discrimination",
        "description": "Job postings must not specify age requirements or preferences.",
    },
    {
        "category": "Discrimination",
        "title": "No Disability Discrimination",
        "description": "Job postings must not discriminate based on disability status.",
    },
    {
        "category": "Discrimination",
        "title": "No Appearance Discrimination",
        "description": "Job postings must not specify appearance requirements or preferences.",
    },
    
    # Legal Compliance Category
    {
        "category": "Legal Compliance",
        "title": "No Illegal Activities",
        "description": "Job postings must not solicit or promote illegal activities or operations.",
    },
    {
        "category": "Legal Compliance",
        "title": "No Copyright Infringement",
        "description": "Job postings must not solicit or promote copyright infringement.",
    },
    {
        "category": "Legal Compliance",
        "title": "No Pornographic Content",
        "description": "Job postings must not solicit or promote pornographic content.",
    },
    {
        "category": "Legal Compliance",
        "title": "No Under-the-Table Work",
        "description": "Job postings must not promote off-the-books or under-the-table employment.",
    },
    {
        "category": "Legal Compliance",
        "title": "No Fraudulent Services",
        "description": "Job postings must not promote or offer fraudulent services or activities.",
    },
    {
        "category": "Legal Compliance",
        "title": "No Trademark Infringement",
        "description": "Job postings must not violate trademark rights or third-party terms of service.",
    },
    {
        "category": "Legal Compliance",
        "title": "No Regulated Goods Reselling",
        "description": "Job postings must not offer reselling of regulated or controlled goods.",
    },
    {
        "category": "Legal Compliance",
        "title": "No Academic Misconduct",
        "description": "Job postings must not offer to prepare academic works on behalf of others.",
    },
    
    # Workplace Standards Category
    {
        "category": "Workplace Standards",
        "title": "No Harassment",
        "description": "Job postings must not promote or enable workplace harassment.",
    },
    {
        "category": "Workplace Standards",
        "title": "No Exploitation",
        "description": "Job postings must not promote exploitative working conditions, such as more than 80 hours per week or extremely dangerous working conditions.",
    },
    {
        "category": "Workplace Standards",
        "title": "No Spam Content",
        "description": "Job postings must not contain spam, nonsense, or violent content.",
    },
    
    # Compensation Category
    {
        "category": "Compensation",
        "title": "Fair Compensation",
        "description": "If Job posting mentions compensation, it must offer compensation over the minimum wage of $7.25 per hour.",
    },
    {
        "category": "Compensation",
        "title": "No Unpaid Work",
        "description": "Job postings must not mention requiring unpaid work or training periods.",
    },
    # Privacy and Security Category
    {
        "category": "Privacy and Security",
        "title": "Data Protection",
        "description": "Job postings cannot ask for personal information such as social security numbers, driver's license numbers, or credit card numbers.",
    }
]

async def seed_database():
    """Seed the database with categories and policies."""
    async with async_session_factory() as session:
        # Create categories
        category_map = {}
        for category_data in CATEGORIES:
            # Check if category exists
            stmt = select(PolicyCategory).where(PolicyCategory.name == category_data["name"])
            result = await session.execute(stmt)
            category = result.scalar_one_or_none()
            
            if not category:
                category = PolicyCategory(**category_data)
                session.add(category)
                await session.flush()
                print(f"Added new category: {category_data['name']}")
            else:
                print(f"Category already exists: {category_data['name']}")
            
            category_map[category_data["name"]] = category
        
        # Create policies
        for policy_data in POLICIES:
            category = category_map[policy_data["category"]]
            
            # Check if policy exists
            stmt = select(Policy).where(
                Policy.title == policy_data["title"],
                Policy.category_id == category.id
            )
            result = await session.execute(stmt)
            policy = result.scalar_one_or_none()
            
            if not policy:
                policy = Policy(
                    category_id=category.id,
                    title=policy_data["title"],
                    description=policy_data["description"],
                )
                session.add(policy)
                print(f"Added new policy: {policy_data['title']}")
            else:
                print(f"Policy already exists: {policy_data['title']}")
        
        await session.commit()

if __name__ == "__main__":
    asyncio.run(seed_database()) 