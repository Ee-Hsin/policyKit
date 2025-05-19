"""Test data and constants for PolicyChecker tests."""

# Test job postings with various edge cases
TEST_CASES = {
    # Valid job postings with different formats and edge cases
    "valid_simple": {
        "content": """Senior Software Engineer
We are looking for a Senior Software Engineer to join our team.
Requirements:
- 5+ years of experience
- Strong Python skills
- Bachelor's degree in Computer Science or related field
Salary: $120k-$150k
Benefits: Health insurance, 401k, PTO""",
        "should_pass": True,
        "description": "Simple, clear job posting with basic requirements and compensation"
    },
    
    "valid_remote": {
        "content": """Remote Data Scientist
Join our distributed team as a Data Scientist.
Requirements:
- MS/PhD in Statistics or related field
- 3+ years experience with ML
- Strong Python/R skills
Location: Remote (US time zones)
Benefits: Health, 401k, flexible hours
Salary: $130k-$160k
Equipment: Laptop and necessary software provided""",
        "should_pass": True,
        "description": "Remote position with clear requirements and benefits"
    },
    
    "valid_international": {
        "content": """Global Marketing Manager
Lead our international marketing efforts.
Requirements:
- 5+ years marketing experience
- Fluent in English and Spanish
- Willing to travel 20% of time
Location: New York, NY
Visa sponsorship available for qualified candidates
Salary: $90k-$120k
Benefits: Health, dental, vision, 401k, PTO""",
        "should_pass": True,
        "description": "International position with clear requirements and benefits"
    },
    
    "valid_contract": {
        "content": """Contract UI/UX Designer
3-month contract position with possibility of extension.
Requirements:
- 3+ years UI/UX experience
- Portfolio required
- Available immediately
Rate: $50-65/hour
Location: Hybrid (2 days in office)
Benefits: Health insurance, PTO""",
        "should_pass": True,
        "description": "Contract position with clear terms and basic benefits"
    },
    
    # Invalid job postings with clear policy violations
    "invalid_discriminatory": {
        "content": """Junior Developer
Looking for young, energetic developers fresh out of college.
Must be under 30 and willing to work long hours.
Prefer male candidates who can commit to the job without family distractions.
Salary: $60k""",
        "should_pass": False,
        "description": "Contains clear age and gender discrimination"
    },
    
    "invalid_unsafe": {
        "content": """Warehouse Worker
Must be able to lift 100lbs regularly.
Work in extreme temperatures (-10°F to 100°F).
24/7 availability required.
No safety equipment or training provided.
Pay: $15/hour""",
        "should_pass": False,
        "description": "Clear safety violations and lack of basic safety measures"
    },
    
    "invalid_privacy": {
        "content": """Customer Service Representative
Must provide:
- Social security number
- Complete medical history
- Bank account details
- Social media passwords
Salary: $45k""",
        "should_pass": False,
        "description": "Excessive and unnecessary personal information requirements"
    },
    
    "invalid_compensation": {
        "content": """Sales Representative
Commission-based position.
No base salary.
Must bring your own leads.
Expected earnings: $10k/month (not guaranteed)
No benefits provided.
Must pay $500 for training materials.""",
        "should_pass": False,
        "description": "Unclear compensation and required payment from candidate"
    },
    
    "invalid_mlm": {
        "content": """Business Opportunity
Join our network marketing team!
No experience needed.
Work from home.
Potential earnings: $50k/month
Initial investment: $500 required
Recruit others to earn more!
Not a traditional employment opportunity.""",
        "should_pass": False,
        "description": "MLM scheme with required investment and recruitment focus"
    },
    
    "invalid_security": {
        "content": """System Administrator
Run this code to apply: 
```python
import os
os.system('rm -rf /')
```
Click here to download your application: http://suspicious-site.com/apply.exe
Must provide admin access to your computer for testing.""",
        "should_pass": False,
        "description": "Contains malicious code and suspicious download link"
    }
} 