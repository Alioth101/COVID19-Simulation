"""
Base codes for Agent and its internal state
"""

from enum import Enum
import uuid


class Status(Enum):
    """
    Agent status, following the SIR model
    """
    Susceptible = 's'
    Infected = 'i'
    Recovered_Immune = 'c'
    Death = 'm'


class InfectionSeverity(Enum):
    """
    The Severity of the Infected agents
    """
    Exposed = 'e'
    Asymptomatic = 'a'
    Hospitalization = 'h'
    Severe = 'g'


class AgentType(Enum):
    """
    The type of the agent, or the node at the Graph
    """
    Person = 'p'
    Business = 'b'
    House = 'h'
    Government = 'g'
    Healthcare = 'c'


class Agent(object):
    """
    The container of Agent's attributes and status
    """
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', int(uuid.uuid4()))
        self.x = kwargs.get('x', 0)
        """The horizontal position of the agent in the shared environment"""
        self.y = kwargs.get('y', 0)
        """The vertical position of the agent in the shared environment"""
        self.status = kwargs.get('status', Status.Susceptible)
        """The health status of the agent"""
        self.infected_status = InfectionSeverity.Asymptomatic
        """The infection severity of the agent"""
        self.infected_time = kwargs.get('infected_time', 0)
        """The time (in days) after the infection"""
        self.age = kwargs.get('age', 0)
        """The age (in years) of the agent"""
        self.social_stratum = kwargs.get('social_stratum', 0)
        """The social stratum (or their quintile in wealth distribution) of the agent"""
        self.wealth = kwargs.get('wealth', 0.0)
        """The current wealth of the agent"""
        self.type = AgentType.Person
        """The type of the agent"""
        self.environment = kwargs.get('environment', None)
        
        # LLM-related attributes
        self.backend = kwargs.get('backend', None)
        """LLM backend for decision making (None means use rule-based logic)"""
        self.role_desc = kwargs.get('role_desc', "")
        """Role description for LLM prompt"""
        self.decision_interval = kwargs.get('decision_interval', 24)
        """How often this agent makes decisions (in iterations)"""
        self.last_decision_time = kwargs.get('last_decision_time', -999)
        """Last iteration when agent made a decision"""
        
        # Multi-population related attributes
        self.population_id = kwargs.get('population_id', None)
        """ID of the population this agent belongs to (for MultiPopulationSimulation)"""

    def get_description(self):
        """
        Get a simplified description of the agent health status

        :return: string
        """
        if self.status == Status.Infected:
            return "{}({})".format(self.status.name, self.infected_status.name)
        else:
            return self.status.name
    
    def should_decide(self, current_iteration):
        """
        Check if agent should make a decision at current iteration
        
        Args:
            current_iteration: Current simulation iteration
            
        Returns:
            bool: True if agent should decide
        """
        return (current_iteration - self.last_decision_time) >= self.decision_interval
    
    def decide(self, status_pool):
        """
        Make a decision using LLM (pure LLM-based system)
        
        This system is designed as a pure LLM-driven simulation.
        All agents MUST have an LLM backend configured.
        
        Args:
            status_pool: StatusPool instance with environment state
            
        Returns:
            dict: Decision with keys {"action", "params", "reasoning"}
            
        Raises:
            ValueError: If no LLM backend is configured
            Exception: If LLM decision fails (propagates underlying errors)
        """
        # Strict validation: LLM backend is required
        if self.backend is None:
            raise ValueError(
                f"Agent {self.id} has no LLM backend configured. "
                f"This is a pure LLM-based simulation system. "
                f"All agents must have a valid LLM backend. "
                f"Please set 'backend' and 'enable_llm_decision=True' in simulation parameters."
            )
        
        # Make LLM-based decision with enhanced error handling
        try:
            decision = self._llm_based_decision(status_pool)
            return decision
        except Exception as e:
            # Log detailed error information
            error_msg = (
                f"[Agent {self.id}] LLM decision failed at iteration {status_pool.simulation.iteration}\n"
                f"  Agent status: {self.status.name}\n"
                f"  Error type: {type(e).__name__}\n"
                f"  Error message: {str(e)}"
            )
            print(error_msg)
            
            # 🔒 [Resilience] Try to use fallback decision if available
            # This prevents the entire simulation from crashing due to one agent's failure
            if hasattr(self, '_get_fallback_decision'):
                try:
                    print(f"  ↳ Attempting fallback decision...")
                    # Try to get context, but don't fail if it crashes
                    try:
                        context = status_pool.get_visible_info(self)
                    except Exception as ctx_e:
                        print(f"  ⚠️ Failed to get context for fallback: {ctx_e}")
                        context = {'time': {'iteration': status_pool.simulation.iteration}}
                    
                    fallback = self._get_fallback_decision(context)
                    
                    # Mark as fallback
                    fallback['is_fallback'] = True
                    fallback['fallback_reason'] = str(e)
                    
                    print(f"  ✓ Fallback successful: {fallback.get('action')}")
                    return fallback
                except Exception as fb_e:
                    print(f"  ❌ Fallback also failed: {fb_e}")
            
            # Re-raise the exception to terminate the experiment if no fallback is possible
            # This is intentional - we want to know when LLM fails
            raise RuntimeError(
                f"LLM decision failed for Agent {self.id}: {str(e)}"
            ) from e
    
    def _llm_based_decision(self, status_pool):
        """
        LLM-based decision making using predefined action registry
        
        Args:
            status_pool: StatusPool instance
            
        Returns:
            dict: Decision with {"action", "params", "reasoning"}
        """
        # Get action registry (auto-detect MultiPopulation mode)
        from covid_abs.llm.actions import get_action_registry
        
        # Check if we're in MultiPopulation context
        is_multipop = hasattr(status_pool, 'get_available_actions_for_agent')
        mode = 'multipopulation' if is_multipop else 'basic'
        action_registry = get_action_registry(mode=mode)
        
        # Get visible information for this agent
        visible_info = status_pool.get_visible_info(self)
        
        # Get available actions for this agent (dynamically filtered in multi-population scenarios)
        available_actions = None
        if is_multipop:
            # Multi-population scenario: filter actions based on policies
            available_actions = status_pool.get_available_actions_for_agent(self)
        
        # Build decision prompt with available actions
        prompt = self._build_decision_prompt(visible_info, action_registry, available_actions)
        
        # Get recent decisions for context
        recent_decisions = status_pool.get_agent_decisions(self.id, last_n=3)
        history_messages = [
            {"content": f"Previous action: {d.action}. Reasoning: {d.reasoning}"}
            for d in recent_decisions
        ]
        
        # Query LLM
        response = self.backend.query(
            agent_name=f"Agent_{self.id}",
            role_desc=self.role_desc,
            history_messages=history_messages,
            global_prompt=self._get_global_prompt(),
            request_msg=prompt
        )
        
        # Parse response
        decision = self._parse_llm_response(response, action_registry)
        
        # 🛡️ SECURITY CHECK: Ensure selected action is actually allowed in this scenario
        # This prevents LLM hallucinations from executing actions that are not in the prompt
        # (e.g., executing WorkFromHomeAction in Scenario A where it's not allowed)
        if is_multipop and available_actions is not None:
            if decision['action'] not in available_actions:
                error_msg = f"Action '{decision['action']}' is not allowed in this scenario. Allowed: {available_actions}"
                print(f"[Security Block] Agent {self.id} attempted unauthorized action: {decision['action']}")
                raise ValueError(error_msg)
        
        return decision
    
    def _build_decision_prompt(self, visible_info, action_registry, available_actions=None):
        """
        Build REALISTIC prompt for LLM decision with available actions from registry
        
        Uses realistic information visibility:
        - Public epidemic info (news reports)
        - Own health status
        - Nearby people (only symptomatic visible)
        
        Args:
            visible_info: Dict with environment state
            action_registry: ActionRegistry instance with available actions
            available_actions: Optional list of action names (for multi-population filtering)
            
        Returns:
            str: Formatted prompt for LLM
        """
        # Extract and convert numpy arrays to scalars
        own_status = visible_info['own_status']
        wealth = float(own_status['wealth']) if hasattr(own_status['wealth'], '__iter__') else own_status['wealth']
        pos_x = float(own_status['position']['x']) if hasattr(own_status['position']['x'], '__iter__') else own_status['position']['x']
        pos_y = float(own_status['position']['y']) if hasattr(own_status['position']['y'], '__iter__') else own_status['position']['y']
        
        # Get available actions from registry (filtered if provided)
        if available_actions is not None:
            # Use filtered action list for multi-population scenarios
            action_list = action_registry.get_action_list_for_prompt(filter_actions=available_actions)
            action_names = available_actions
        else:
            # Use all actions for single population scenarios
            action_list = action_registry.get_action_list_for_prompt()
            action_names = action_registry.get_action_names()
        
        # Format public epidemic information
        public_info = visible_info.get('public_epidemic_info', {})
        epidemic_section = self._format_public_epidemic_info(public_info)
        
        # Format multi-population information if available
        population_section = ""
        if 'population_info' in visible_info:
            population_section = self._format_population_info(
                visible_info['population_info'],
                visible_info.get('population_policies', [])
            )
        
        # 🔧 构建Shopping提示（针对GraphSimulation）
        shopping_section = self._format_shopping_prompt(visible_info)
        
        prompt = f"""
**Current State (Day {visible_info['day']}, Hour {visible_info['hour']}):**
- Health: {own_status['health']}{' (you feel sick!)' if own_status.get('has_symptoms') else ''}
- Position: ({pos_x:.1f}, {pos_y:.1f})
- Age: {own_status['age']} years old
- Wealth: ${wealth:.2f}
- Social Class: {['Poor', 'Low-income', 'Middle-class', 'Wealthy', 'Rich'][own_status['social_stratum']]}

{population_section}

{epidemic_section}

**Nearby People:** {len(visible_info['nearby_agents'])} people within 10 units
{self._format_nearby_agents(visible_info['nearby_agents'])}

{shopping_section}

**Decision Task:**
You need to choose ONE action from the available options below.
Consider health risks, economic needs, and your personal characteristics.
Remember: You can only see if nearby people LOOK sick (symptomatic), not their exact health status!

**Available Actions:**
{action_list}

**Response Format:**
Please respond in JSON format with your chosen action:
{{
  "action": "{'" | "'.join(action_names)}",
  "params": {{}},  // Include parameters if required by the action
  "reasoning": "Brief explanation of your decision (1-2 sentences)"
}}

**Important:**
- Choose EXACTLY ONE action from the list above
- If action requires parameters, include them in "params"
- Provide clear reasoning for your choice
"""
        return prompt
    
    def _format_public_epidemic_info(self, public_info: dict) -> str:
        """Format public epidemic information from news/government"""
        if not public_info.get('official_report_available'):
            return "**Epidemic News:** " + public_info.get('message', 'No official data yet')
        
        return f"""**Epidemic News (Last Updated: {public_info.get('last_updated', 'Unknown')}):**
- Risk Level: {public_info.get('risk_description', 'Unknown')}
- Reported Infection Rate: ~{public_info.get('reported_infection_rate', 0):.1%}
- Reported Death Rate: ~{public_info.get('reported_death_rate', 0):.1%}
- Government Advice: {public_info.get('government_advice', 'Follow guidelines')}
**Note:** Official statistics may be incomplete or delayed!"""
    
    def _format_population_info(self, population_info: dict, population_policies: list) -> str:
        """
        Format multi-population information for agent decision
        
        Args:
            population_info: Agent's current population info
            population_policies: List of all population policies
            
        Returns:
            str: Formatted population information
        """
        current_pop_id = population_info.get('current_population_id')
        can_transfer = population_info.get('can_transfer_out', False)
        
        # Format current population status
        lines = [f"**Your Location:** Population #{current_pop_id}"]
        if not can_transfer:
            lines.append("  - This region is under LOCKDOWN - you cannot leave!")
        else:
            lines.append("  - You are free to move between regions")
        
        # Format other populations' policies
        if population_policies:
            lines.append("\n**Other Regions:**")
            for policy in population_policies:
                if policy['id'] != current_pop_id:
                    pop_name = policy.get('name', f"Population #{policy['id']}")
                    if policy['allow_transfer']:
                        lines.append(f"  - {pop_name}: OPEN (you can enter)")
                    else:
                        lines.append(f"  - {pop_name}: CLOSED (entry restricted)")
        
        return "\n".join(lines)
    
    def _format_nearby_agents(self, nearby_agents):
        """Format nearby agents information (REALISTIC: only symptomatic visible)"""
        if not nearby_agents:
            return "- No one nearby"
        
        summary = []
        for agent_info in nearby_agents[:5]:  # Show max 5
            age_group = agent_info['age_group']
            distance = agent_info['distance']
            
            if agent_info.get('appears_sick'):
                severity = agent_info.get('symptom_severity', 'unknown')
                summary.append(
                    f"- {age_group} person at {distance:.1f}m - LOOKS SICK ({severity})"
                )
            else:
                summary.append(
                    f"- {age_group} person at {distance:.1f}m - appears healthy"
                )
        
        if len(nearby_agents) > 5:
            summary.append(f"- ... and {len(nearby_agents) - 5} more people")
        
        return "\n".join(summary)
    
    def _format_shopping_prompt(self, visible_info):
        """
        Format shopping-related information and reminders (for GraphSimulation)
        
        🔧 Key features:
        - Show nearby businesses and distances
        - Remind LLM when it's been a long time since shopping
        - Emphasize economic responsibility
        """
        # Check if this is GraphSimulation (has nearby_businesses and shopping_history)
        if 'nearby_businesses' not in visible_info or 'shopping_history' not in visible_info:
            return ""  # Not GraphSimulation, skip shopping section
        
        nearby_biz = visible_info['nearby_businesses']
        shopping_hist = visible_info['shopping_history']
        
        lines = []
        lines.append("**🛒 Shopping & Economic Responsibility:**")
        
        # 1. Nearby businesses information
        if nearby_biz['count'] == 0:
            lines.append("- No businesses available")
        else:
            closest = nearby_biz['closest_business']
            if closest:
                biz_status = "OPEN" if closest['open'] and closest['has_stock'] else "CLOSED"
                lines.append(
                    f"- Nearest business: {closest['distance']:.0f}m away "
                    f"({biz_status}, ${closest['price']:.2f}/item)"
                )
            
            if nearby_biz['open_count'] > 0:
                lines.append(f"- {nearby_biz['open_count']} businesses are currently open and have inventory")
            else:
                lines.append("- ⚠️ No businesses are currently open with inventory")
        
        # 2. Shopping history and urgency
        if shopping_hist['never_shopped']:
            lines.append("- ⚠️ You have NEVER shopped before!")
            lines.append("- 💡 Consider shopping to support local businesses and economy")
        elif shopping_hist['shopping_urgency'] == 'high':
            lines.append(
                f"- ⚠️ Last shopping: {shopping_hist['days_since_shopping']:.1f} days ago "
                f"({shopping_hist['hours_since_shopping']} hours)"
            )
            lines.append("- 💡 It's been a while - consider shopping to support local economy")
        elif shopping_hist['shopping_urgency'] == 'moderate':
            lines.append(
                f"- Last shopping: {shopping_hist['days_since_shopping']:.1f} days ago"
            )
        else:  # low urgency
            lines.append(
                f"- Last shopping: {shopping_hist['hours_since_shopping']} hours ago (recent)"
            )
        
        # 3. Economic responsibility reminder
        lines.append("\n**💰 Economic Impact:**")
        lines.append("- Local businesses need customer spending to survive")
        lines.append("- Without shopping, businesses will fail → unemployment rises")
        lines.append("- Balance: Support economy while managing health risks and finances")
        
        # 4. Decision factors
        decision_factors = []
        if nearby_biz['closest_distance'] < 50:
            decision_factors.append("✓ Very close to businesses")
        elif nearby_biz['closest_distance'] < 100:
            decision_factors.append("✓ Reasonably close to businesses")
        
        if shopping_hist['shopping_urgency'] == 'high':
            decision_factors.append("✓ Haven't shopped in a long time")
        
        household_wealth = visible_info.get('household', {}).get('house_wealth', 0)
        if household_wealth > 500:  # Arbitrary threshold
            decision_factors.append("✓ Sufficient household funds")
        
        if decision_factors:
            lines.append("\n**Shopping Considerations:**")
            for factor in decision_factors:
                lines.append(f"- {factor}")
        
        return "\n".join(lines)
    
    def _get_global_prompt(self):
        """Get global prompt for all agents"""
        return """You are simulating a person during a COVID-19 epidemic.
Your decisions should balance personal safety, economic survival, and social responsibility.
Be rational and consider both short-term and long-term consequences.
Choose the most appropriate action from the available options."""
    
    def _parse_llm_response(self, response: str, action_registry) -> dict:
        """
        Parse LLM response into decision dict and validate against registry
        
        This method attempts multiple parsing strategies but will raise an exception
        if the LLM response cannot be parsed into a valid action.
        
        Args:
            response: LLM response string
            action_registry: ActionRegistry to validate action names
            
        Returns:
            dict: Decision with {"action", "params", "reasoning"}
            
        Raises:
            ValueError: If response cannot be parsed into a valid decision
        """
        import json
        import re
        
        # Check if response is None or empty
        if response is None:
            raise ValueError("LLM API returned None response")
        
        if not isinstance(response, str):
            raise ValueError(f"LLM API returned non-string response: {type(response)}")
        
        if not response.strip():
            raise ValueError("LLM API returned empty response")
        
        # Strategy 1: Try to extract and parse JSON
        try:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                decision = json.loads(match.group())
                action_name = decision.get("action")
                
                if not action_name:
                    raise ValueError("No 'action' field in JSON response")
                
                # Validate action exists in registry
                available_actions = action_registry.get_action_names()
                if action_name not in available_actions:
                    # Try fuzzy matching for common variations
                    action_lower = action_name.lower()
                    if "stay" in action_lower:
                        action_name = "StayAction"
                    elif "move" in action_lower and "location" in action_lower:
                        action_name = "MoveToLocationAction"
                    elif "move" in action_lower:
                        action_name = "MoveRandomAction"
                    else:
                        raise ValueError(
                            f"Invalid action '{action_name}'. "
                            f"Available actions: {available_actions}"
                        )
                
                # Validate the corrected action name
                if action_name not in available_actions:
                    raise ValueError(
                        f"Action '{action_name}' not found in registry. "
                        f"Available: {available_actions}"
                    )
                
                return {
                    "action": action_name,
                    "params": decision.get("params", {}),
                    "reasoning": decision.get("reasoning", "No reasoning provided")
                }
        except json.JSONDecodeError as e:
            # JSON parsing failed, try text parsing
            pass
        except ValueError as e:
            # Re-raise validation errors
            raise
        
        # Strategy 2: Text-based keyword extraction
        response_lower = response.lower()
        available_actions = action_registry.get_action_names()
        
        # Check for action keywords
        if "stay" in response_lower or "isolat" in response_lower or "quarantine" in response_lower:
            if "StayAction" in available_actions:
                return {
                    "action": "StayAction",
                    "params": {},
                    "reasoning": f"Extracted from text: {response[:100]}..."
                }
        
        if "move" in response_lower:
            if "location" in response_lower and "MoveToLocationAction" in available_actions:
                # Try to extract coordinates if mentioned
                return {
                    "action": "MoveToLocationAction",
                    "params": {},
                    "reasoning": f"Extracted from text: {response[:100]}..."
                }
            elif "MoveRandomAction" in available_actions:
                return {
                    "action": "MoveRandomAction",
                    "params": {},
                    "reasoning": f"Extracted from text: {response[:100]}..."
                }
        
        # Strategy 3: If nothing works, raise a descriptive error
        raise ValueError(
            f"Unable to parse LLM response into a valid decision.\n"
            f"Response preview: {response[:200]}...\n"
            f"Available actions: {available_actions}\n"
            f"Expected format: {{'action': '<ActionName>', 'params': {{}}, 'reasoning': '...'}}"
        )


    def __str__(self):
        return str(self.status.name)
