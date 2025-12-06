"""
Main code for Agent Based Simulation
"""

from covid_abs.agents import Status, InfectionSeverity, Agent
from covid_abs.common import *
import numpy as np

def distance(a, b):
    return np.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


class Simulation(object):
    def __init__(self, **kwargs):
        self.population = []
        '''The population of agents'''
        self.population_size = kwargs.get("population_size", 20)
        '''The number of agents'''
        self.length = kwargs.get("length", 10)
        '''The length of the shared environment'''
        self.height = kwargs.get("height", 10)
        '''The height of the shared environment'''
        self.initial_infected_perc = kwargs.get("initial_infected_perc", 0.05)
        '''The initial percent of population which starts the simulation with the status Infected'''
        self.initial_immune_perc = kwargs.get("initial_immune_perc", 0.05)
        '''The initial percent of population which starts the simulation with the status Immune'''
        self.contagion_distance = kwargs.get("contagion_distance", 1.)
        '''The minimal distance considered as contact (or exposition)'''
        self.contagion_rate = kwargs.get("contagion_rate", 0.9)
        '''The probability of contagion given two agents were in contact'''
        self.critical_limit = kwargs.get("critical_limit", 0.6)
        '''The percent of population which the Health System can afford'''
        self.amplitudes = kwargs.get('amplitudes',
                                     {Status.Susceptible: 5,
                                      Status.Recovered_Immune: 5,
                                      Status.Infected: 5})
        '''A dictionary with the average mobility of agents inside the shared environment for each status'''
        self.minimum_income = kwargs.get("minimum_income", 1.0)
        '''The base (or minimum) daily income, related to the most poor wealth quintile'''
        self.minimum_expense = kwargs.get("minimum_expense", 1.0)
        '''The base (or minimum) daily expense, related to the most poor wealth quintile'''
        self.statistics = None
        '''A dictionary with the population statistics for the current iteration'''
        self.triggers_simulation = kwargs.get("triggers_simulation", [])
        "A dictionary with conditional changes in the Simulation attributes"
        self.triggers_population = kwargs.get("triggers_population", [])
        "A dictionary with conditional changes in the Agent attributes"

        self.total_wealth = kwargs.get("total_wealth", 10 ** 4)
        
        # LLM-related attributes
        self.backend = kwargs.get("backend", None)
        '''LLM backend for agent decision making (None = rule-based only)'''
        self.enable_llm_decision = kwargs.get("enable_llm_decision", False)
        '''Whether to enable LLM-based decision making'''
        self.max_concurrent_llm = kwargs.get("max_concurrent_llm", 3)
        '''Maximum number of concurrent LLM API calls (default: 3, set to 1 for sequential execution)'''
        self.iteration = kwargs.get("iteration", 0)
        '''Current iteration counter (24 iterations = 1 day)'''
        self.status_pool = None
        '''StatusPool instance (initialized in execute())'''
        self.llm_decision_logs = []
        '''LLM decision logs: list of dicts with {iteration, day, hour, agent_id, agent_status, action, reasoning, population_id, population_name}'''
        
        # Multi-population related attributes
        self.allow_population_transfer = kwargs.get("allow_population_transfer", False)
        '''Whether agents can transfer to other populations (for MultiPopulationSimulation)'''
        self.population_id = kwargs.get("population_id", None)
        '''ID of this population in MultiPopulationSimulation (None for standalone)'''
        self.population_name = kwargs.get("population_name", None)
        '''Human-readable name of this population'''

    def _xclip(self, x):
        return np.clip(int(x), 0, self.length)

    def _yclip(self, y):
        return np.clip(int(y), 0, self.height)

    def get_population(self):
        """
        Return the population in the current iteration

        :return: a list with the current agent instances
        """
        return self.population

    def set_population(self, pop):
        """
        Update the population in the current iteration
        """
        self.population = pop

    def set_amplitudes(self, amp):
        self.amplitudes = amp

    def append_trigger_simulation(self, condition, attribute, action):
        """
        Append a conditional change in the Simulation attributes

        :param condition: a lambda function that receives the current simulation instance and
        returns a boolean
        :param attribute: string, the attribute name of the Simulation which will be changed
        :param action: a lambda function that receives the current simulation instance and returns
        the new value of the attribute
        """
        self.triggers_simulation.append({'condition': condition, 'attribute': attribute, 'action': action})

    def append_trigger_population(self, condition, attribute, action):
        """
        Append a conditional change in the population attributes

        :param condition: a lambda function that receives the current agent instance and returns a boolean
        :param attribute: string, the attribute name of the agent which will be changed
        :param action: a lambda function that receives the current agent instance and returns the new
        value of the attribute
        """
        self.triggers_population.append({'condition': condition, 'attribute': attribute, 'action': action})

    def random_position(self):
        x = self._xclip(self.length / 2 + (np.random.randn(1) * (self.length / 3)))
        y = self._yclip(self.height / 2 + (np.random.randn(1) * (self.height / 3)))

        return x, y

    def create_agent(self, status):
        """
        Create a new agent with the given status

        :param status: a value of agents.Status enum
        :return: the newly created agent
        """
        x, y = self.random_position()

        age = int(np.random.beta(2, 4, 1) * 100)
        social_stratum = int(np.random.rand(1) * 100 // 20)
        self.population.append(Agent(x=x, y=y, age=age, status=status, social_stratum=social_stratum))

    def initialize(self):
        """
        Initializate the Simulation by creating its population of agents
        """

        # Initial infected population
        for i in np.arange(0, int(self.population_size * self.initial_infected_perc)):
            self.create_agent(Status.Infected)

        # Initial immune population
        for i in np.arange(0, int(self.population_size * self.initial_immune_perc)):
            self.create_agent(Status.Recovered_Immune)

        # Initial susceptible population
        for i in np.arange(0, self.population_size - len(self.population)):
            self.create_agent(Status.Susceptible)

        # Share the common wealth of 10^4 among the population, according each agent social stratum
        for quintile in [0, 1, 2, 3, 4]:
            total = lorenz_curve[quintile] * self.total_wealth
            qty = max(1.0, np.sum([1 for a in self.population if a.social_stratum == quintile and a.age >= 18]))
            ag_share = total / qty
            for agent in filter(lambda x: x.social_stratum == quintile and x.age >= 18, self.population):
                agent.wealth = ag_share
        
        # Initialize LLM-related attributes for all agents
        if self.enable_llm_decision and self.backend is not None:
            from covid_abs.llm.role_descriptions import get_agent_role_desc
            
            for agent in self.population:
                agent.backend = self.backend
                agent.role_desc = get_agent_role_desc(
                    age=agent.age,
                    status=agent.status,
                    social_stratum=agent.social_stratum
                )
                agent.last_decision_time = -999  # Ensure first decision happens
                # For basic simulation, all agents decide every 6 iterations (quarter day)
                agent.decision_interval = 6
        
        # LLM Precondition Check: Ensure all agents have LLM backend configured
        # This is critical for pure LLM-based simulation system
        if self.enable_llm_decision:
            if self.backend is None:
                raise ValueError(
                    "LLM decision is enabled but no backend is configured. "
                    "Please provide a valid LLM backend instance (e.g., OpenAI, Azure)."
                )
            
            # Verify each agent has backend
            agents_without_backend = [
                agent.id for agent in self.population 
                if not hasattr(agent, 'backend') or agent.backend is None
            ]
            
            if agents_without_backend:
                raise ValueError(
                    f"LLM decision is enabled but {len(agents_without_backend)} agents have no backend configured. "
                    f"Agent IDs: {agents_without_backend[:10]}{'...' if len(agents_without_backend) > 10 else ''}. "
                    f"This is a pure LLM-based system - all agents must have LLM backend."
                )

    def contact(self, agent1, agent2):
        """
        Performs the actions needed when two agents get in touch.

        :param agent1: an instance of agents.Agent
        :param agent2: an instance of agents.Agent
        """

        if agent1.status == Status.Susceptible and agent2.status == Status.Infected:
            contagion_test = np.random.random()
            agent1.infection_status = InfectionSeverity.Exposed
            if contagion_test <= self.contagion_rate:
                agent1.status = Status.Infected
                agent1.infection_status = InfectionSeverity.Asymptomatic

    def move(self, agent, triggers=[]):
        """
        Performs the actions related with the movement of the agents in the shared environment
        Now uses Action Registry for LLM-driven behavior

        :param agent: an instance of agents.Agent
        :param triggers: the list of population triggers related to the movement
        """

        if agent.status == Status.Death or (agent.status == Status.Infected
                                            and (agent.infected_status == InfectionSeverity.Hospitalization
                                                 or agent.infected_status == InfectionSeverity.Severe)):
            return

        # LLM-based movement (if enabled) - using Action Registry
        if self.enable_llm_decision and self.status_pool is not None:
            latest_decision = self.status_pool.get_latest_decision(agent.id)
            
            if latest_decision is not None:
                # Use Action Registry to execute the decision (auto-detect MultiPopulation mode)
                from covid_abs.llm.actions import get_action_registry
                
                # CRITICAL FIX: Use parent_simulation for multi-population scenarios
                # In multi-population simulations, TransferToPopulationAction needs
                # the MultiPopulationSimulation instance, not the sub-simulation
                target_simulation = getattr(self, 'parent_simulation', None) or self
                
                # Auto-detect mode based on simulation type
                from covid_abs.abs import MultiPopulationSimulation
                is_multipop = isinstance(target_simulation, MultiPopulationSimulation)
                mode = 'multipopulation' if is_multipop else 'basic'
                action_registry = get_action_registry(mode=mode)
                
                # Execute action through registry
                result = action_registry.execute_action(
                    action_name=latest_decision.action,
                    agent=agent,
                    simulation=target_simulation,
                    params=latest_decision.params
                )
                
                # Log execution result (optional, for debugging)
                if hasattr(self, '_action_log'):
                    self._action_log.append(result)
                
                return

    def update(self, agent):
        """
        Update the status of the agent

        :param agent: an instance of agents.Agent
        """

        if agent.status == Status.Death:
            return

        if agent.status == Status.Infected:
            agent.infected_time += 1

            indice = get_age_group_index(agent.age)

            teste_sub = np.random.random()

            if agent.infected_status == InfectionSeverity.Asymptomatic:
                if age_hospitalization_probs[indice] > teste_sub:
                    agent.infected_status = InfectionSeverity.Hospitalization
            elif agent.infected_status == InfectionSeverity.Hospitalization:
                if age_severe_probs[indice] > teste_sub:
                    agent.infected_status = InfectionSeverity.Severe
                    self.get_statistics()
                    if self.statistics['Severe'] + self.statistics['Hospitalization'] >= self.critical_limit:
                        agent.status = Status.Death
                        agent.infected_status = InfectionSeverity.Asymptomatic

            death_test = np.random.random()
            if age_death_probs[indice] > death_test:
                agent.status = Status.Death
                agent.infected_status = InfectionSeverity.Asymptomatic
                return

            if agent.infected_time > 20:
                agent.infected_time = 0
                agent.status = Status.Recovered_Immune
                agent.infected_status = InfectionSeverity.Asymptomatic

        agent.wealth -= self.minimum_expense * basic_income[agent.social_stratum]

    def execute(self):
        """
        Execute a complete iteration cycle of the Simulation
        
        In this LLM-based simulation system:
        1. Agents make decisions using LLM (no rule-based fallback)
        2. If any agent's LLM decision fails, the entire iteration is aborted
        3. Detailed error information is logged for debugging
        
        Raises:
            RuntimeError: If LLM decision fails for any agent or if not initialized
        """
        # CRITICAL: Validate that simulation has been initialized
        if len(self.population) == 0:
            raise RuntimeError(
                "Cannot execute Simulation with 0 agents. "
                "Did you forget to call sim.initialize()? "
                "This method creates the agent population."
            )
        
        # Initialize StatusPool and DecisionBuffer if LLM is enabled
        if self.enable_llm_decision and self.backend is not None:
            # Initialize StatusPool (persistent state)
            if self.status_pool is None:
                from covid_abs.llm.message import StatusPool
                self.status_pool = StatusPool(self)
            
            # Initialize DecisionBufferManager and ConcurrentExecutor (first time only)
            if not hasattr(self, 'decision_buffer'):
                from covid_abs.llm.decision_buffer import DecisionBufferManager, ConcurrentDecisionExecutor
                self.decision_buffer = DecisionBufferManager(self.status_pool)
                
                # Initialize concurrent executor
                # max_concurrent_llm: number of concurrent LLM calls
                self.decision_executor = ConcurrentDecisionExecutor(
                    max_workers=self.max_concurrent_llm
                )
                
                print(f"[LLM Concurrent Mode] Initialized with max_concurrent_llm={self.max_concurrent_llm}")
            
            # Update statistics in StatusPool (from PREVIOUS iteration)
            stats = self.get_statistics(kind='info')
            self.status_pool.update_statistics(stats)
            
            # ========================================
            # LLM Decision Phase (CONCURRENT)
            # ========================================
            
            # Phase 1: Start new iteration buffer
            self.decision_buffer.start_iteration(self.iteration)
            
            # Phase 2: Collect agents that need to decide
            deciding_agents = [
                agent for agent in self.population
                if agent.should_decide(self.iteration)
            ]
            
            if deciding_agents:
                # Phase 3: Execute concurrent LLM calls
                decision_results = self.decision_executor.execute_concurrent_decisions(
                    agents=deciding_agents,
                    status_pool=self.status_pool,  # Read-only!
                    iteration=self.iteration,
                    experiment_id=self.experiment_id if hasattr(self, 'experiment_id') else 1
                )
                
                # Phase 4: Process results and add to temp buffer
                from covid_abs.llm.message import Decision
                
                successful_decisions = 0
                failed_decisions = []
                
                for result in decision_results:
                    if result['success']:
                        # Create Decision record
                        decision = result['decision']
                        agent = next(a for a in deciding_agents if a.id == result['agent_id'])
                        
                        decision_record = Decision(
                            agent_id=agent.id,
                            iteration=self.iteration,
                            action=decision['action'],
                            params=decision.get('params', {}),
                            reasoning=decision.get('reasoning', '')
                        )
                        
                        # Add to TEMP BUFFER (not statuspool yet!)
                        self.decision_buffer.add_decision(decision_record)
                        
                        # Log the decision
                        self.log_llm_decision(agent, decision)
                        
                        # Update agent's last decision time
                        agent.last_decision_time = self.iteration
                        
                        successful_decisions += 1
                    
                    else:
                        # Record error
                        failed_decisions.append({
                            'agent_id': result['agent_id'],
                            'error': result['error'],
                            'error_type': result['error_type']
                        })
                
                # Phase 5: Handle errors (abort on any failure to ensure data quality)
                if failed_decisions:
                    # Print error summary
                    print(f"\n{'='*80}")
                    print(f"[SIMULATION ERROR] {len(failed_decisions)} LLM Decision(s) Failed")
                    print(f"{'='*80}")
                    for fail in failed_decisions:
                        print(f"  Agent {fail['agent_id']}: [{fail['error_type']}] {fail['error']}")
                        if fail.get('used_fallback'):
                            print(f"    (Fallback decision was generated but will not be used)")
                    print(f"{'='*80}\n")
                    
                    # ❌ 立即中止实验，避免使用fallback决策导致数据失真
                    raise RuntimeError(
                        f"{len(failed_decisions)} agent(s) failed to make decisions at iteration {self.iteration}. "
                        f"Aborting iteration to ensure data quality."
                    )
                
                # Phase 6: Flush temp buffer to statuspool
                # All decisions succeeded, now commit them atomically
                committed_count = self.decision_buffer.flush_to_statuspool()
                
                # Optional: print confirmation
                # print(f"[Iteration {self.iteration}] ✅ {committed_count} decisions committed")
            
            else:
                # No agents need to decide this iteration
                pass
        
        # Original simulation logic
        mov_triggers = [k for k in self.triggers_population if k['attribute'] == 'move']
        other_triggers = [k for k in self.triggers_population if k['attribute'] != 'move']

        for agent in self.population:
            self.move(agent, triggers=mov_triggers)
            self.update(agent)

            for trigger in other_triggers:
                if trigger['condition'](agent):
                    attr = trigger['attribute']
                    agent.__dict__[attr] = trigger['action'](agent.__dict__[attr])

        # 🔧 BUG FIX: Use actual population length instead of initial population_size
        # In multi-population simulations, agents can transfer between populations,
        # so len(self.population) may differ from self.population_size
        current_population_size = len(self.population)
        dist = np.zeros((current_population_size, current_population_size))

        contacts = []

        for i in np.arange(0, current_population_size):
            for j in np.arange(i + 1, current_population_size):
                ai = self.population[i]
                aj = self.population[j]

                if distance(ai, aj) <= self.contagion_distance:
                    contacts.append((i, j))

        for par in contacts:
            ai = self.population[par[0]]
            aj = self.population[par[1]]
            self.contact(ai, aj)
            self.contact(aj, ai)

        if len(self.triggers_simulation) > 0:
            for trigger in self.triggers_simulation:
                if trigger['condition'](self):
                    attr = trigger['attribute']
                    self.__dict__[attr] = trigger['action'](self.__dict__[attr])

        self.statistics = None
        
        # Increment iteration counter
        self.iteration += 1

    def get_positions(self):
        """Return the list of x,y positions for all agents"""
        return [[a.x, a.y] for a in self.population]

    def get_description(self, complete=False):
        """
        Return the list of Status and InfectionSeverity for all agents

        :param complete: a flag indicating if the list must contain the InfectionSeverity (complete=True)
        :return: a list of strings with the Status names
        """
        if complete:
            return [a.get_description() for a in self.population]
        else:
            return [a.status.name for a in self.population]

    def get_statistics(self, kind='info'):
        """
        Calculate and return the dictionary of the population statistics for the current iteration.

        :param kind: 'info' for health statiscs, 'ecom' for economic statistics and None for all statistics
        :return: a dictionary
        """
        if self.statistics is None:
            self.statistics = {}
            for status in Status:
                self.statistics[status.name] = np.sum(
                    [1 for a in self.population if a.status == status]) / self.population_size

            for infected_status in filter(lambda x: x != InfectionSeverity.Exposed, InfectionSeverity):
                self.statistics[infected_status.name] = np.sum([1 for a in self.population if
                                                                a.infected_status == infected_status and
                                                                a.status != Status.Death]) / self.population_size

            for quintile in [0, 1, 2, 3, 4]:
                # Convert wealth to float to avoid numpy array issues
                wealth_sum = sum(
                    [float(a.wealth) if hasattr(a.wealth, '__iter__') else a.wealth 
                     for a in self.population if a.social_stratum == quintile
                     and a.age >= 18 and a.status != Status.Death])
                # Normalize by total_wealth (fixed value) to match original ABS GraphSimulation
                self.statistics['Q{}'.format(quintile + 1)] = wealth_sum / self.total_wealth

        return self.filter_stats(kind)

    def filter_stats(self, kind):
        if kind == 'info':
            return {k: v for k, v in self.statistics.items() if not k.startswith('Q') and k not in ('Business','Government')}
        elif kind == 'ecom':
            return {k: v for k, v in self.statistics.items() if k.startswith('Q') or k in ('Business','Government')}
        else:
            return self.statistics
    
    def log_llm_decision(self, agent, decision):
        """
        Log an LLM decision for this agent
        
        Args:
            agent: Agent instance that made the decision
            decision: Decision dict with {action, params, reasoning}
        """
        log_entry = {
            'iteration': self.iteration,
            'day': self.iteration // 24,
            'hour': self.iteration % 24,
            'agent_id': agent.id,
            'agent_status': agent.status.name,
            'agent_health': agent.get_description(),
            'action': decision.get('action', 'Unknown'),
            'reasoning': decision.get('reasoning', ''),
            'parameters': decision.get('params', {}),
            'population_id': self.population_id,
            'population_name': self.population_name or f"Pop_{self.population_id}"
        }
        self.llm_decision_logs.append(log_entry)
    
    def save_llm_logs(self, filename):
        """
        Save all LLM decision logs to a JSON file
        
        Args:
            filename: Output file path (e.g., "output/llm_decisions.json")
        """
        import json
        import os
        
        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)
        
        output = {
            'metadata': {
                'simulation_type': self.__class__.__name__,
                'population_id': self.population_id,
                'population_name': self.population_name,
                'total_iterations': self.iteration,
                'total_days': self.iteration // 24,
                'enable_llm': self.enable_llm_decision,
                'total_decisions': len(self.llm_decision_logs)
            },
            'decisions': self.llm_decision_logs
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        return filename
    
    def get_llm_logs(self):
        """
        Get all LLM decision logs
        
        Returns:
            list: List of decision log entries
        """
        return self.llm_decision_logs

    def __str__(self):
        return str(self.get_description())


class MultiPopulationSimulation(Simulation):
    def __init__(self, **kwargs):
        super(MultiPopulationSimulation, self).__init__(**kwargs)
        
        # Support both ways of creating multi-population simulation:
        # 1. Pass pre-created simulations: simulations=[sim1, sim2, ...]
        # 2. Pass simulation params: simulations_params=[{params1}, {params2}, ...]
        simulations_params = kwargs.get('simulations_params', None)
        
        if simulations_params is not None:
            # Create simulations from parameters
            self.simulations = []
            for params in simulations_params:
                sim = Simulation(**params)
                self.simulations.append(sim)
        else:
            # Use pre-created simulations
            self.simulations = kwargs.get('simulations', [])
        
        self.positions = kwargs.get('positions', [])
        self.total_population = kwargs.get('total_population', 0)

    def get_population(self):
        population = []
        for simulation in self.simulations:
            population.extend(simulation.get_population())
        return population

    def append(self, simulation, position):
        self.simulations.append(simulation)
        self.positions.append(position)
        self.total_population += simulation.population_size

    def initialize(self):
        """
        Initialize all sub-populations
        For LLM-based simulation, pass backend to each sub-population
        """
        # CRITICAL FIX: Calculate total population across all sub-simulations
        self.total_population = 0
        
        for pop_id, simulation in enumerate(self.simulations):
            # Set population ID for tracking
            simulation.population_id = pop_id
            
            # Pass LLM configuration to sub-populations
            if self.enable_llm_decision and self.backend is not None:
                simulation.backend = self.backend
                simulation.enable_llm_decision = True
            
            # Initialize the sub-population
            simulation.initialize()
            
            # Mark each agent with their population_id
            for agent in simulation.population:
                agent.population_id = pop_id
            
            # Accumulate total population
            self.total_population += len(simulation.population)

    def execute(self, **kwargs):
        """
        Execute one iteration for multi-population simulation
        
        Key design changes:
        1. Use MultiPopulationStatusPool for cross-population awareness
        2. No cross-population contact detection (agents don't infect across populations)
        3. Infection spreads across populations only through agent transfer
        4. Each population executes independently
        """
        # CRITICAL: Validate that simulation has been initialized
        if self.total_population == 0:
            raise RuntimeError(
                "Cannot execute MultiPopulationSimulation with 0 agents. "
                "Did you forget to call multi_sim.initialize()? "
                "This method creates agents in all sub-populations."
            )
        
        # Initialize MultiPopulationStatusPool if LLM is enabled
        if self.enable_llm_decision and self.backend is not None:
            if self.status_pool is None:
                from covid_abs.llm.multipopulation_message import MultiPopulationStatusPool
                self.status_pool = MultiPopulationStatusPool(self)
            
            # Update population policies
            self.status_pool.update_population_policies()
        
        # Execute each population independently
        for simulation in self.simulations:
            # Share the multi-population status pool with sub-simulations
            if self.status_pool is not None:
                simulation.status_pool = self.status_pool
            
            # CRITICAL FIX: Set parent reference for action execution
            # Sub-simulations need to know their parent MultiPopulationSimulation
            # so that TransferToPopulationAction can work correctly
            simulation.parent_simulation = self
            
            simulation.execute()
        
        # Note: NO cross-population contact checking!
        # Cross-population infection only happens when infected agents transfer
        # This is by design according to requirements
        
        self.statistics = None
        
        # Increment iteration counter (if not already incremented by sub-simulations)
        if hasattr(self, 'iteration'):
            self.iteration += 1

    def get_positions(self):
        positions = []
        for ct, simulation in enumerate(self.simulations):
            for a in simulation.get_population():
                positions.append([a.x + self.positions[ct][0], a.y + self.positions[ct][1]])
        return positions

    def get_description(self, complete=False):
        situacoes = []
        for simulation in self.simulations:
            for a in simulation.get_population():
                if complete:
                    situacoes.append(a.get_description())
                else:
                    situacoes.append(a.status.name)

        return situacoes

    def get_statistics(self, kind='info'):
        if self.statistics is None:

            self.statistics = {}
            # CRITICAL FIX: Initialize counters first, then accumulate across all simulations
            for status in Status:
                self.statistics[status.name] = 0
                for simulation in self.simulations:
                    self.statistics[status.name] += np.sum(
                        [1 for a in filter(lambda x: x.status == status, simulation.get_population())])
                # Avoid division by zero warning
                if self.total_population > 0:
                    self.statistics[status.name] /= self.total_population
                else:
                    self.statistics[status.name] = 0.0

            for infected_status in InfectionSeverity:
                self.statistics[infected_status.name] = 0
                for simulation in self.simulations:
                    self.statistics[infected_status.name] += np.sum(
                        [1 for a in filter(lambda x: x.infected_status == infected_status and x.status != Status.Death,
                                           simulation.get_population())])
                # Avoid division by zero warning
                if self.total_population > 0:
                    self.statistics[infected_status.name] /= self.total_population
                else:
                    self.statistics[infected_status.name] = 0.0

            # CRITICAL FIX: Accumulate wealth across all simulations instead of overwriting
            # Calculate combined total_wealth from all sub-simulations
            combined_total_wealth = sum(sim.total_wealth for sim in self.simulations)
            
            for quintil in [0, 1, 2, 3, 4]:
                key = 'Q{}'.format(quintil + 1)
                self.statistics[key] = 0
                for simulation in self.simulations:
                    self.statistics[key] += np.sum([a.wealth for a in simulation.get_population()
                                                   if a.social_stratum == quintil and a.age >= 18
                                                   and a.status != Status.Death])
                # Normalize by combined total_wealth to match original ABS GraphSimulation logic
                if combined_total_wealth > 0:
                    self.statistics[key] /= combined_total_wealth

        return self.filter_stats(kind)
    
    def get_llm_logs(self):
        """
        Aggregate LLM decision logs from all sub-populations
        
        Returns:
            list: Combined list of decision logs from all populations
        """
        all_logs = []
        for simulation in self.simulations:
            all_logs.extend(simulation.llm_decision_logs)
        # Sort by iteration for chronological order
        all_logs.sort(key=lambda x: (x['iteration'], x['population_id'], x['agent_id']))
        return all_logs
    
    def save_llm_logs(self, filename):
        """
        Save aggregated LLM decision logs from all populations to a JSON file
        
        Args:
            filename: Output file path (e.g., "output/multipop_llm_decisions.json")
        """
        import json
        import os
        
        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)
        
        all_logs = self.get_llm_logs()
        
        output = {
            'metadata': {
                'simulation_type': 'MultiPopulationSimulation',
                'num_populations': len(self.simulations),
                'population_names': [sim.population_name or f"Pop_{i}" for i, sim in enumerate(self.simulations)],
                'total_iterations': self.iteration,
                'total_days': self.iteration // 24,
                'enable_llm': self.enable_llm_decision,
                'total_decisions': len(all_logs),
                'decisions_per_population': {
                    sim.population_name or f"Pop_{i}": len(sim.llm_decision_logs)
                    for i, sim in enumerate(self.simulations)
                }
            },
            'decisions': all_logs
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        return filename

    def __str__(self):
        return str(self.get_description())
