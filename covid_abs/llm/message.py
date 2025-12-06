"""
Message and StatusPool classes for managing agent decisions and environment state
"""

from typing import List, Dict, Any
from threading import Lock
from covid_abs.agents import Agent, Status


class Decision:
    """Records a single agent's decision"""
    
    def __init__(
        self,
        agent_id: int,
        iteration: int,
        action: str,
        params: Dict[str, Any] = None,
        reasoning: str = "",
        is_fallback: bool = False,
        fallback_reason: str = ""
    ):
        """
        Args:
            agent_id: Unique identifier of the agent
            iteration: Simulation iteration when decision was made
            action: Action type (e.g., "move_random", "stay", "move_to_location")
            params: Action parameters (e.g., {"target_x": 10, "target_y": 20})
            reasoning: LLM's explanation for the decision
            is_fallback: Whether this is a fallback decision (LLM failed)
            fallback_reason: Reason for fallback (if is_fallback=True)
        """
        self.agent_id = agent_id
        self.iteration = iteration
        self.day = iteration // 24  # Assuming 24 iterations = 1 day
        self.hour = iteration % 24
        self.action = action
        self.params = params or {}
        self.reasoning = reasoning
        self.is_fallback = is_fallback
        self.fallback_reason = fallback_reason
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        result = {
            "agent_id": self.agent_id,
            "iteration": self.iteration,
            "day": self.day,
            "hour": self.hour,
            "action": self.action,
            "params": self.params,
            "reasoning": self.reasoning
        }
        
        # Include fallback info if applicable
        if self.is_fallback:
            result["is_fallback"] = True
            result["fallback_reason"] = self.fallback_reason
        
        return result
    
    def __repr__(self):
        fallback_str = " [FALLBACK]" if self.is_fallback else ""
        return f"Decision(agent={self.agent_id}, iter={self.iteration}, action={self.action}{fallback_str})"


class StatusPool:
    """
    Manages shared environment state and agent decision history
    Similar to MessagePool in AgentReview project
    """
    
    def __init__(self, simulation):
        """
        Args:
            simulation: Reference to the Simulation instance
        """
        self.simulation = simulation
        self._decisions = []  # All agent decisions
        self._statistics_cache = {}  # Cached statistics
        self._lock = Lock()  # 🔒 线程锁：保护_decisions并发访问
    
    def append_decision(self, decision: Decision):
        """Add a new decision to the pool (thread-safe)"""
        with self._lock:  # 🔒 保护并发写入
            self._decisions.append(decision)
    
    def get_agent_decisions(self, agent_id: int, last_n: int = 5) -> List[Decision]:
        """
        Get recent decisions for a specific agent
        
        Args:
            agent_id: Agent ID
            last_n: Number of recent decisions to retrieve
            
        Returns:
            List of Decision objects
        """
        agent_decisions = [d for d in self._decisions if d.agent_id == agent_id]
        return agent_decisions[-last_n:]
    
    def get_latest_decision(self, agent_id: int) -> Decision:
        """Get the most recent decision for an agent"""
        decisions = self.get_agent_decisions(agent_id, last_n=1)
        return decisions[0] if decisions else None
    
    def update_statistics(self, stats: Dict):
        """Update cached statistics"""
        self._statistics_cache = stats.copy()
    
    def get_visible_info(self, agent: Agent) -> Dict[str, Any]:
        """
        Get REALISTIC information visible to a specific agent.
        
        Design Principles (Realistic):
        1. Own status: Fully aware (knows if sick)
        2. Others' status: Only visible if SYMPTOMATIC
        3. Global stats: Delayed, incomplete news reports (not real-time)
        4. Spatial: Only nearby people visible
        
        Args:
            agent: Agent instance
            
        Returns:
            Dictionary with visible information
        """
        # Get current simulation statistics
        stats = self.simulation.get_statistics(kind='info')
        iteration = getattr(self.simulation, 'iteration', 0)
        
        # Get nearby agents (within visual range)
        nearby_agents = self._get_nearby_agents(agent, distance_threshold=10.0)
        
        # Get agent's own recent decisions
        recent_decisions = self.get_agent_decisions(agent.id, last_n=3)
        
        # === REALISTIC: Public information (news reports) ===
        # Not real-time! Delayed by ~1 day, rounded, incomplete
        public_info = self._get_public_epidemic_info(stats, iteration)
        
        visible_info = {
            "iteration": iteration,
            "day": iteration // 24,
            "hour": iteration % 24,
            
            # === REALISTIC: Public epidemic information (from news/government) ===
            "public_epidemic_info": public_info,
            
            # === REALISTIC: Agent's own status (fully aware) ===
            "own_status": {
                "health": agent.status.name,
                "infected_days": agent.infected_time if agent.status == Status.Infected else 0,
                "has_symptoms": self._has_visible_symptoms(agent),
                "position": {"x": agent.x, "y": agent.y},
                "age": agent.age,
                "wealth": agent.wealth,
                "social_stratum": agent.social_stratum
            },
            
            # === REALISTIC: Nearby people (only symptomatic visible) ===
            "nearby_agents": nearby_agents,
            
            # Recent decisions for context
            "recent_decisions": [
                {"action": d.action, "reasoning": d.reasoning}
                for d in recent_decisions
            ]
        }
        
        return visible_info
    
    def _get_public_epidemic_info(self, stats: Dict, iteration: int) -> Dict[str, Any]:
        """
        Get REALISTIC public epidemic information
        
        Simulates what a person would know from:
        - News reports (updated daily, not real-time)
        - Government announcements
        - Social media rumors
        
        Returns:
            Realistic public information
        """
        import random
        
        day = iteration // 24
        
        # News is updated once per day (at midnight)
        # People only see YESTERDAY's statistics
        reported_infection_rate = stats.get('Infected', 0)
        reported_death_rate = stats.get('Death', 0)
        
        # Add realism: 
        # 1. Delayed reporting (yesterday's data)
        # 2. Rounded to nearest 5%
        # 3. Underreporting (not all cases detected)
        
        if day == 0:
            # Day 0: No official data yet
            return {
                "official_report_available": False,
                "message": "Epidemic just started, official data not yet released",
                "risk_level": "unknown"
            }
        
        # Underreporting: Only ~70% of cases are detected
        detection_rate = 0.7
        reported_infection_rate *= detection_rate
        
        # Round to nearest 5% (governments don't report exact numbers daily)
        reported_infection_rate = round(reported_infection_rate * 20) / 20  # Round to 0.05
        
        # Determine public risk level based on infection rate
        if reported_infection_rate < 0.01:
            risk_level = "low"
            risk_description = "Low-risk area"
        elif reported_infection_rate < 0.05:
            risk_level = "medium"
            risk_description = "Medium-risk area"
        else:
            risk_level = "high"
            risk_description = "High-risk area"
        
        return {
            "official_report_available": True,
            "last_updated": f"Day {day - 1}",  # Yesterday's data
            "reported_infection_rate": reported_infection_rate,
            "reported_death_rate": reported_death_rate,
            "risk_level": risk_level,
            "risk_description": risk_description,
            "government_advice": self._get_government_advice(risk_level)
        }
    
    def _get_government_advice(self, risk_level: str) -> str:
        """Get realistic government advice based on risk level"""
        advice = {
            "low": "Stay vigilant, practice good hygiene, avoid crowded places",
            "medium": "Reduce outings, wear masks, maintain social distance",
            "high": "Strongly advised to stay home, go out only when necessary, wear masks at all times"
        }
        return advice.get(risk_level, "Follow epidemic prevention guidelines")
    
    def _has_visible_symptoms(self, agent: Agent) -> bool:
        """
        Check if agent has VISIBLE symptoms
        
        Realistic rules:
        - Asymptomatic: No visible symptoms (looks healthy!)
        - Hospitalization/Severe: Obvious symptoms
        - Infected < 2 days: No symptoms yet (incubation period)
        """
        from covid_abs.agents import Status, InfectionSeverity
        
        if agent.status != Status.Infected:
            return False
        
        # Incubation period: first 2 days no symptoms
        if agent.infected_time < 2:
            return False
        
        # Asymptomatic cases: never show symptoms
        if agent.infected_status == InfectionSeverity.Asymptomatic:
            return False
        
        # Hospitalization/Severe: obvious symptoms
        if agent.infected_status in [InfectionSeverity.Hospitalization, InfectionSeverity.Severe]:
            return True
        
        # Exposed: mild symptoms after 2 days
        return agent.infected_time >= 2
    
    def _get_nearby_agents(self, agent: Agent, distance_threshold: float = 10.0) -> List[Dict]:
        """
        Get REALISTIC information about nearby agents
        
        Realism rules:
        - Can see physical attributes (age, distance)
        - CANNOT see health status directly
        - Can only infer illness if person has VISIBLE symptoms
        
        Args:
            agent: Reference agent
            distance_threshold: Maximum distance to consider "nearby"
            
        Returns:
            List of dicts with nearby agent info (NO health status unless symptomatic!)
        """
        nearby = []
        
        for other in self.simulation.population:
            if other.id == agent.id:
                continue
            
            # Calculate distance
            from covid_abs.abs import distance
            dist = distance(agent, other)
            
            if dist <= distance_threshold:
                agent_info = {
                    "distance": round(dist, 2),
                    "age_group": "young" if other.age < 30 else "middle" if other.age < 60 else "elderly",
                }
                
                # === REALISTIC: Only visible if symptomatic! ===
                if self._has_visible_symptoms(other):
                    agent_info["appears_sick"] = True  # Not exact status, just "looks sick"
                    agent_info["symptom_severity"] = self._get_symptom_description(other)
                else:
                    agent_info["appears_sick"] = False  # Looks healthy (even if infected!)
                
                nearby.append(agent_info)
        
        return nearby
    
    def _get_symptom_description(self, agent: Agent) -> str:
        """Get realistic symptom description visible to others"""
        from covid_abs.agents import InfectionSeverity
        
        if agent.infected_status == InfectionSeverity.Severe:
            return "severe_symptoms"  # coughing, very weak
        elif agent.infected_status == InfectionSeverity.Hospitalization:
            return "moderate_symptoms"  # coughing, fever
        else:
            return "mild_symptoms"  # slight cough
    
    def get_all_decisions(self) -> List[Decision]:
        """Get all decisions in the pool"""
        return self._decisions.copy()
    
    def clear(self):
        """Clear all decisions (useful for reset)"""
        self._decisions = []
        self._statistics_cache = {}
