"""
Multi-population status pool for LLM-based decisions
Extends StatusPool with multi-population awareness and transfer policies
"""

from covid_abs.llm.message import StatusPool, Decision
from typing import Dict, List, Any
import numpy as np


class MultiPopulationStatusPool(StatusPool):
    """
    Status pool for MultiPopulationSimulation
    
    Key features:
    1. Agents only see other agents in their own population
    2. Agents can see transfer policies of all populations
    3. No cross-population visibility of individual agents
    4. Supports dynamic action registry based on transfer policies
    """
    
    def __init__(self, simulation):
        """
        Initialize multi-population status pool
        
        Args:
            simulation: MultiPopulationSimulation instance
        """
        super().__init__(simulation)
        self._population_policies = {}
    
    def update_population_policies(self):
        """
        Update population transfer policies
        Called at each iteration to track policy changes
        """
        from covid_abs.abs import MultiPopulationSimulation
        
        if not isinstance(self.simulation, MultiPopulationSimulation):
            return
        
        self._population_policies = {}
        for pop_id, sim in enumerate(self.simulation.simulations):
            self._population_policies[pop_id] = {
                'id': pop_id,
                'name': sim.population_name or f'Population_{pop_id}',
                'allow_transfer': sim.allow_population_transfer,
                'population_size': sim.population_size,
                'position': self.simulation.positions[pop_id] if pop_id < len(self.simulation.positions) else (0, 0)
            }
    
    def get_visible_info(self, agent) -> Dict[str, Any]:
        """
        Get REALISTIC information visible to agent in multi-population context
        
        Key design:
        1. Agent only sees nearby agents IN THE SAME POPULATION
        2. Agent can see transfer policies of all populations
        3. No cross-population individual agent visibility
        
        Args:
            agent: Agent instance
            
        Returns:
            Dictionary with visible information
        """
        from covid_abs.abs import MultiPopulationSimulation
        
        # Get agent's population ID
        pop_id = agent.population_id
        if pop_id is None:
            # Fallback to single-population behavior
            return super().get_visible_info(agent)
        
        # Get agent's simulation instance
        if not isinstance(self.simulation, MultiPopulationSimulation):
            return super().get_visible_info(agent)
        
        if pop_id >= len(self.simulation.simulations):
            raise ValueError(f"Agent {agent.id} has invalid population_id: {pop_id}")
        
        agent_simulation = self.simulation.simulations[pop_id]
        
        # Get current simulation statistics FOR THIS POPULATION ONLY
        stats = agent_simulation.get_statistics(kind='info')
        iteration = getattr(self.simulation, 'iteration', 0)
        
        # Get nearby agents IN THE SAME POPULATION ONLY
        nearby_agents = self._get_nearby_agents_same_population(agent, agent_simulation)
        
        # Get agent's own recent decisions
        recent_decisions = self.get_agent_decisions(agent.id, last_n=3)
        
        # === REALISTIC: Public information (news reports) for OWN POPULATION ===
        public_info = self._get_public_epidemic_info(stats, iteration)
        
        visible_info = {
            "iteration": iteration,
            "day": iteration // 24,
            "hour": iteration % 24,
            
            # === Population context ===
            "population_info": {
                "current_population_id": pop_id,
                "current_population_name": agent_simulation.population_name or f'Population_{pop_id}',
                "can_transfer_out": agent_simulation.allow_population_transfer
            },
            
            # === All populations' transfer policies (PUBLIC INFORMATION) ===
            "population_policies": self._get_population_policies_info(),
            
            # === REALISTIC: Public epidemic information (from news/government) ===
            "public_epidemic_info": public_info,
            
            # === REALISTIC: Agent's own status (fully aware) ===
            "own_status": {
                "health": agent.status.name,
                "infected_days": agent.infected_time if agent.status == agent.status.Infected else 0,
                "has_symptoms": self._has_visible_symptoms(agent),
                "position": {"x": agent.x, "y": agent.y},
                "age": agent.age,
                "wealth": agent.wealth,
                "social_stratum": agent.social_stratum
            },
            
            # === REALISTIC: Nearby people (only in SAME POPULATION, only symptomatic visible) ===
            "nearby_agents": nearby_agents,
            
            # Recent decisions for context
            "recent_decisions": [
                {"action": d.action, "reasoning": d.reasoning}
                for d in recent_decisions
            ]
        }
        
        return visible_info
    
    def _get_nearby_agents_same_population(self, agent, agent_simulation, distance_threshold: float = 10.0) -> List[Dict]:
        """
        Get information about nearby agents IN THE SAME POPULATION ONLY
        
        Key: No cross-population visibility!
        
        Args:
            agent: Reference agent
            agent_simulation: Simulation instance of agent's population
            distance_threshold: Maximum distance to consider "nearby"
            
        Returns:
            List of dicts with nearby agent info (SAME POPULATION ONLY)
        """
        from covid_abs.abs import distance
        
        nearby = []
        
        # Only check agents in THE SAME POPULATION
        for other in agent_simulation.population:
            if other.id == agent.id:
                continue
            
            # Calculate distance
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
    
    def _get_population_policies_info(self) -> List[Dict]:
        """
        Get information about all populations' transfer policies
        
        This is PUBLIC INFORMATION - everyone knows which regions allow transfers
        
        Returns:
            List of population policy info
        """
        policies = []
        for pop_id, policy in self._population_policies.items():
            policies.append({
                'id': pop_id,  # Fixed: Changed from 'population_id' to 'id' to match agents.py expectations
                'name': policy['name'],
                'allow_transfer': policy['allow_transfer'],
                'policy_description': 'Open for transfer' if policy['allow_transfer'] else 'Transfer restricted (lockdown)'
            })
        
        return policies
    
    def get_available_actions_for_agent(self, agent) -> List[str]:
        """
        Get list of available action names for agent based on current policies
        
        Key logic:
        - transfer_to_population only available if agent's current population allows transfer
        - Other actions always available
        
        Args:
            agent: Agent instance
            
        Returns:
            List of available action names
        """
        from covid_abs.abs import MultiPopulationSimulation
        from covid_abs.llm.actions import get_action_registry
        
        # Use 'multipopulation' mode to include TransferToPopulationAction
        registry = get_action_registry(mode='multipopulation')
        all_actions = registry.get_action_names()
        
        # Check if in multi-population context
        if not isinstance(self.simulation, MultiPopulationSimulation):
            # Single population: remove transfer action (shouldn't happen, but safety check)
            return [a for a in all_actions if a != 'TransferToPopulationAction']
        
        pop_id = agent.population_id
        if pop_id is None or pop_id >= len(self.simulation.simulations):
            # No valid population: remove transfer action
            return [a for a in all_actions if a != 'TransferToPopulationAction']
        
        agent_sim = self.simulation.simulations[pop_id]
        
        # If agent's population doesn't allow transfer, remove transfer action
        if not agent_sim.allow_population_transfer:
            return [a for a in all_actions if a != 'TransferToPopulationAction']
        
        # All actions available (including transfer)
        return all_actions
    
    def get_transferable_populations(self, agent) -> List[int]:
        """
        Get list of population IDs that agent can transfer to
        
        Conditions:
        1. Agent's current population allows transfer
        2. Target population allows transfer
        3. Target is not current population
        
        Args:
            agent: Agent instance
            
        Returns:
            List of transferable population IDs
        """
        from covid_abs.abs import MultiPopulationSimulation
        
        if not isinstance(self.simulation, MultiPopulationSimulation):
            return []
        
        pop_id = agent.population_id
        if pop_id is None:
            return []
        
        if pop_id >= len(self.simulation.simulations):
            return []
        
        agent_sim = self.simulation.simulations[pop_id]
        
        # Agent's population must allow transfer
        if not agent_sim.allow_population_transfer:
            return []
        
        # Find all populations that allow transfer (excluding current)
        transferable = []
        for target_id, target_sim in enumerate(self.simulation.simulations):
            if target_id == pop_id:
                continue  # Can't transfer to self
            
            if target_sim.allow_population_transfer:
                transferable.append(target_id)
        
        return transferable
