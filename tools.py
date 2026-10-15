# tools.py
def get_company_policy(category: str) -> str:
    """Returns the spending limits and rules for a given expense category."""
    policies = {
        "meal": "Max allowance is $75.00 per meal. Alcohol is strictly forbidden.",
        "flight": "All flights must be Coach/Economy unless transatlantic.",
        "software_saas": "Individual software subscriptions require pre-approval if over $50/month."
    }
    return policies.get(category.lower(), "Standard Rule: Requires manager sign-off for any amount over $100.00.")
