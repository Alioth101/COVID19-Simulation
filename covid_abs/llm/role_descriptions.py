"""
Role description generation for LLM prompts
"""

from covid_abs.agents import Status


# Global prompt for all agents
GLOBAL_PROMPT = """You are simulating a person during a COVID-19 epidemic.
Your decisions should balance personal safety, economic survival, and social responsibility.
Be rational and consider both short-term and long-term consequences.
Always respond in valid JSON format."""


def get_agent_role_desc(age: int, status: Status, social_stratum: int) -> str:
    """
    Generate role description for an agent
    
    Args:
        age: Agent's age in years
        status: Agent's health status (Status enum)
        social_stratum: Social class (0-4, where 0=poorest, 4=richest)
        
    Returns:
        str: Role description for LLM prompt
    """
    # Age category
    if age < 18:
        age_desc = "child"
        age_concerns = "You are young and generally healthy, but must follow adult guidance."
    elif age < 30:
        age_desc = "young adult"
        age_concerns = "You are young and have lower risk from COVID-19, but can still transmit the virus."
    elif age < 50:
        age_desc = "middle-aged adult"
        age_concerns = "You have moderate risk from COVID-19 and responsibilities to family/work."
    elif age < 65:
        age_desc = "older adult"
        age_concerns = "You have elevated risk from COVID-19 and should be more cautious."
    else:
        age_desc = "elderly person"
        age_concerns = "You are at high risk from COVID-19 and must prioritize safety."
    
    # Social class
    wealth_levels = ["poor", "low-income", "middle-class", "wealthy", "affluent"]
    wealth_desc = wealth_levels[social_stratum]
    
    if social_stratum <= 1:
        wealth_concerns = "Your limited financial resources mean you must balance safety with economic survival. Missing work could be devastating."
    elif social_stratum <= 2:
        wealth_concerns = "You have moderate financial stability but still need to work regularly. You can afford some precautions."
    else:
        wealth_concerns = "You have strong financial security and can afford to prioritize safety over work."
    
    # Health status
    if status == Status.Susceptible:
        health_desc = "currently healthy and susceptible"
        health_concerns = "You are not infected but vulnerable. You should avoid unnecessary contact with infected individuals."
    elif status == Status.Infected:
        health_desc = "currently infected with COVID-19"
        health_concerns = "You are infected and should self-isolate to avoid spreading the virus. Seek medical attention if symptoms worsen."
    elif status == Status.Recovered_Immune:
        health_desc = "recovered from COVID-19 and now immune"
        health_concerns = "You have immunity and lower personal risk, but should still consider community welfare."
    elif status == Status.Death:
        health_desc = "deceased"
        health_concerns = "You cannot take any actions."
    else:
        health_desc = "in unknown health state"
        health_concerns = "Assess your situation carefully."
    
    # Construct role description
    role_desc = f"""You are a {age_desc} ({age} years old), {wealth_desc} individual who is {health_desc}.

**Your Characteristics:**
- Age: {age} years old ({age_desc})
- Economic Status: {wealth_desc.capitalize()}
- Health Status: {status.name}

**Your Concerns:**
- Health Risk: {age_concerns}
- Economic Situation: {wealth_concerns}
- Current Health: {health_concerns}

**Your Decision-Making Style:**
{'Conservative and cautious due to high health risk.' if age >= 60 else 'Balanced approach weighing risks and needs.' if age >= 30 else 'More willing to take calculated risks.'}
{'You must prioritize economic survival even at some health risk.' if social_stratum <= 1 else 'You can afford to be selective about risk exposure.' if social_stratum >= 3 else 'You balance economic needs with reasonable precautions.'}
"""
    
    return role_desc


# ============================================
# DEPRECATED: Old decision schema (no longer used)
# Now using ActionRegistry.get_action_list_for_prompt() instead
# ============================================
# def get_decision_schema() -> dict:
#     """Get JSON schema for decision output (DEPRECATED)"""
#     pass

