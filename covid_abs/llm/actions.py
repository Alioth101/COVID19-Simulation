"""
Predefined Action System for LLM-based Agent Behavior

This module defines all available actions that agents can take.
Each action is self-contained with execution logic and environment synchronization.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import numpy as np
from covid_abs.common import *


class Action(ABC):
    """
    Abstract base class for all agent actions.
    
    Each action defines:
    1. name: Unique identifier
    2. description: What this action does (for LLM prompt)
    3. parameters: What parameters it needs
    4. execute(): How to perform the action
    """
    
    def __init__(self):
        self.name = self.__class__.__name__
    
    @abstractmethod
    def get_description(self) -> str:
        """
        Get human-readable description for LLM prompt
        
        Returns:
            str: Description of what this action does
        """
        pass
    
    @abstractmethod
    def get_parameters(self) -> List[str]:
        """
        Get list of required parameters
        
        Returns:
            List[str]: Parameter names needed for this action
        """
        pass
    
    @abstractmethod
    def execute(self, agent, simulation, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute the action and synchronize with environment
        
        Args:
            agent: Agent performing the action
            simulation: Simulation environment
            params: Optional parameters for the action
            
        Returns:
            Dict with execution results (for logging/debugging)
        """
        pass
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        Validate that required parameters are provided
        
        Args:
            params: Parameters to validate
            
        Returns:
            bool: True if valid
        """
        required = self.get_parameters()
        if not required:
            return True
        return all(p in params for p in required)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert action to dictionary for JSON serialization
        
        Returns:
            Dict with action metadata
        """
        return {
            "name": self.name,
            "description": self.get_description(),
            "parameters": self.get_parameters()
        }


# ============================================================================
# Original ABS Actions (复现原系统的行为)
# ============================================================================

class StayAction(Action):
    """
    Agent stays in current position (self-isolation)
    
    This action represents:
    - Staying at home
    - Self-quarantine
    - Avoiding social contact
    
    Economic effect: No income gain, minimal expense
    """
    
    def get_description(self) -> str:
        return "Stay in current position (self-isolation, no movement)"
    
    def get_parameters(self) -> List[str]:
        return []  # No parameters needed
    
    def execute(self, agent, simulation, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Stay in place - position unchanged
        
        Economic effect: Generates minimal baseline income (e.g., remote work, savings interest)
        to prevent wealth from continuously decreasing when staying home
        """
        old_x, old_y = agent.x, agent.y
        
        # Position remains the same (no movement)
        
        # ✅ 删除废弃的"居家收入"逻辑
        # 原代码凭空创造财富（BasicSimulation遗留），与LLM-based决策模型不符
        # LLM驱动的系统中，收入应该只来自月度工资（Business.accounting）
        
        return {
            "action": "stay",
            "position_before": (old_x, old_y),
            "position_after": (agent.x, agent.y),
            "distance_moved": 0.0,
            "wealth_change": 0.0
        }


class MoveRandomAction(Action):
    """
    Agent moves randomly within environment bounds
    
    This action represents:
    - Normal daily activities
    - Going to work/shopping
    - Social interactions
    
    Economic effect: Movement distance generates income
    """
    
    def get_description(self) -> str:
        return "Move randomly within the environment (normal daily activity, can earn income)"
    
    def get_parameters(self) -> List[str]:
        return []  # No parameters needed
    
    def execute(self, agent, simulation, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Random movement based on agent's status amplitude
        """
        old_x, old_y = agent.x, agent.y
        
        # Get movement amplitude based on health status
        amplitude = simulation.amplitudes.get(agent.status, 5)
        
        # Calculate random movement
        ix = int(np.random.randn(1)[0] * amplitude)
        iy = int(np.random.randn(1)[0] * amplitude)
        
        # Update position with boundary checking
        if (agent.x + ix) <= 0 or (agent.x + ix) >= simulation.length:
            agent.x -= ix
        else:
            agent.x += ix
        
        if (agent.y + iy) <= 0 or (agent.y + iy) >= simulation.height:
            agent.y -= iy
        else:
            agent.y += iy
        
        # Calculate distance for statistics
        dist = np.sqrt(ix ** 2 + iy ** 2)
        
        # ✅ 删除废弃的"移动收入"逻辑
        # 原代码凭空创造财富（BasicSimulation遗留），与LLM-based决策模型不符
        # LLM驱动的系统中，收入应该只来自月度工资（Business.accounting）
        
        return {
            "action": "move_random",
            "position_before": (old_x, old_y),
            "position_after": (agent.x, agent.y),
            "distance_moved": float(dist),
            "wealth_change": 0.0
        }


class MoveToLocationAction(Action):
    """
    Agent moves to a specific target location
    
    This action represents:
    - Targeted movement (e.g., to healthcare, business)
    - Strategic positioning
    - Avoiding high-risk areas
    
    Economic effect: Distance-based income, similar to random movement
    """
    
    def get_description(self) -> str:
        return "Move to a specific location (requires target_x, target_y)"
    
    def get_parameters(self) -> List[str]:
        return ["target_x", "target_y"]
    
    def execute(self, agent, simulation, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Move towards target location
        """
        if not params or not self.validate_params(params):
            # Fallback: stay in place
            return StayAction().execute(agent, simulation)
        
        old_x, old_y = agent.x, agent.y
        target_x = params.get("target_x", agent.x)
        target_y = params.get("target_y", agent.y)
        
        # Ensure target is within bounds
        target_x = np.clip(target_x, 0, simulation.length)
        target_y = np.clip(target_y, 0, simulation.height)
        
        # Calculate distance and direction
        dx = target_x - agent.x
        dy = target_y - agent.y
        dist_to_target = np.sqrt(dx ** 2 + dy ** 2)
        
        # Get movement amplitude based on status
        amplitude = simulation.amplitudes.get(agent.status, 5)
        
        # Move towards target (limited by amplitude)
        if dist_to_target > 0:
            # Normalize direction and scale by amplitude
            move_dist = min(amplitude, dist_to_target)
            agent.x += (dx / dist_to_target) * move_dist
            agent.y += (dy / dist_to_target) * move_dist
        
        # Ensure within bounds
        agent.x = np.clip(agent.x, 0, simulation.length)
        agent.y = np.clip(agent.y, 0, simulation.height)
        
        # Calculate actual distance moved
        actual_dist = np.sqrt((agent.x - old_x) ** 2 + (agent.y - old_y) ** 2)
        
        # ✅ 删除废弃的"移动收入"逻辑
        # 原代码凭空创造财富（BasicSimulation遗留），与LLM-based决策模型不符
        # LLM驱动的系统中，收入应该只来自月度工资（Business.accounting）
        
        return {
            "action": "move_to_location",
            "position_before": (old_x, old_y),
            "position_after": (float(agent.x), float(agent.y)),
            "target": (target_x, target_y),
            "distance_moved": float(actual_dist),
            "wealth_change": 0.0
        }


class TransferToPopulationAction(Action):
    """
    Transfer agent to another population (for MultiPopulationSimulation)
    
    This action allows agents to move between populations (e.g., traveling to another city).
    Only available when:
    1. Agent's current population allows transfer (allow_population_transfer=True)
    2. Target population allows transfer
    
    Key design:
    - Agent is removed from source population
    - Agent is added to target population
    - Agent's position is reset to random location in target
    - Cross-population infection only happens through this mechanism
    """
    
    name = "transfer_to_population"
    
    def get_description(self):
        return (
            "Transfer to another city/region. "
            "Use this when you need to relocate for work, safety, or other reasons. "
            "Only available if both your current region and target region allow population movement."
        )
    
    def get_parameters(self):
        return ["target_population_id"]
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        return 'target_population_id' in params
    
    def execute(self, agent, simulation, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute population transfer
        
        Args:
            agent: Agent to transfer
            simulation: Must be MultiPopulationSimulation
            params: Must contain 'target_population_id'
        
        Returns:
            Dict with transfer result
        """
        from covid_abs.abs import MultiPopulationSimulation
        
        # Validation 1: Must be MultiPopulationSimulation
        if not isinstance(simulation, MultiPopulationSimulation):
            raise ValueError(
                "TransferToPopulationAction only works with MultiPopulationSimulation"
            )
        
        target_id = params.get('target_population_id')
        
        # CRITICAL FIX: Support both city names (e.g., "City_B") and numeric IDs (e.g., "1" or 1)
        # LLM may return city names, string numbers, or integers
        if isinstance(target_id, str):
            # Try to convert to int first
            try:
                target_id = int(target_id)
            except ValueError:
                # If conversion fails, it might be a city name - try to find matching population
                target_id_found = None
                for pop_id, sim in enumerate(simulation.simulations):
                    if sim.population_name == target_id:
                        target_id_found = pop_id
                        break
                
                if target_id_found is not None:
                    target_id = target_id_found
                else:
                    # Couldn't find by name, provide helpful error
                    available_names = [
                        f"'{sim.population_name}' (ID: {i})" 
                        for i, sim in enumerate(simulation.simulations)
                    ]
                    raise ValueError(
                        f"Invalid target_population_id: '{target_id}'. "
                        f"Available populations: {', '.join(available_names)}"
                    )
        
        # Validation 2: Target population must exist
        if target_id >= len(simulation.simulations):
            raise ValueError(
                f"Invalid target population ID: {target_id}. "
                f"Only {len(simulation.simulations)} populations available."
            )
        
        # Find agent's current population
        source_id = agent.population_id
        if source_id is None:
            raise ValueError(f"Agent {agent.id} has no population_id assigned")
        
        # Validation 3: Can't transfer to same population
        if source_id == target_id:
            return {
                "action": "transfer_to_population",
                "success": False,
                "reason": "Already in target population"
            }
        
        source_sim = simulation.simulations[source_id]
        target_sim = simulation.simulations[target_id]
        
        # Validation 4: Source population must allow transfer
        if not source_sim.allow_population_transfer:
            return {
                "action": "transfer_to_population",
                "success": False,
                "reason": f"Source population {source_id} does not allow transfers (lockdown policy)"
            }
        
        # Validation 5: Target population must allow transfer
        if not target_sim.allow_population_transfer:
            return {
                "action": "transfer_to_population",
                "success": False,
                "reason": f"Target population {target_id} does not allow transfers (lockdown policy)"
            }
        
        # Execute transfer
        try:
            # Remove from source
            if agent not in source_sim.population:
                raise ValueError(f"Agent {agent.id} not found in source population {source_id}")
            
            source_sim.population.remove(agent)
            source_sim.population_size -= 1
            
            # Add to target
            target_sim.population.append(agent)
            target_sim.population_size += 1
            
            # Update agent attributes
            old_x, old_y = agent.x, agent.y
            agent.population_id = target_id
            agent.x, agent.y = target_sim.random_position()
            
            # 🔧 ECONOMIC FIX: Calculate cross-population transfer distance and generate income
            # Transfer between populations represents long-distance travel (e.g., moving cities)
            # Use population positions from simulation.positions to calculate distance
            if hasattr(simulation, 'positions') and len(simulation.positions) > max(source_id, target_id):
                # Calculate distance between population centers
                source_pos = simulation.positions[source_id]
                target_pos = simulation.positions[target_id]
                cross_pop_distance = np.sqrt((target_pos[0] - source_pos[0]) ** 2 + 
                                            (target_pos[1] - source_pos[1]) ** 2)
            else:
                # Fallback: Use a default large distance for cross-population transfer
                # Typical cross-city distance (much larger than within-city movement)
                cross_pop_distance = 50.0
            
            # ✅ 删除废弃的"跨人口转移收入"逻辑
            # 原代码凭空创造财富（BasicSimulation遗留），与LLM-based决策模型不符
            # LLM驱动的系统中，收入应该只来自月度工资（Business.accounting）
            
            # Update total population count
            simulation.total_population = sum(s.population_size for s in simulation.simulations)
            
            return {
                "action": "transfer_to_population",
                "success": True,
                "source_population": source_id,
                "target_population": target_id,
                "old_position": (old_x, old_y),
                "new_position": (agent.x, agent.y),
                "distance_moved": float(cross_pop_distance),
                "wealth_change": 0.0,
                "reason": f"Successfully transferred from population {source_id} to {target_id}"
            }
            
        except Exception as e:
            # Rollback if any error occurs
            return {
                "action": "transfer_to_population",
                "success": False,
                "reason": f"Transfer failed: {str(e)}"
            }


# ============================================================================
# Action Registry
# ============================================================================

class ActionRegistry:
    """
    Central registry for all available actions.
    
    Provides:
    1. Action lookup by name
    2. Action list for LLM prompt
    3. Action validation
    4. Easy extension with new actions
    """
    
    def __init__(self, mode: str = 'basic'):
        """
        Initialize ActionRegistry
        
        Args:
            mode: 'basic' (Stay/MoveRandom only) or 'multipopulation' (adds Transfer)
        """
        self._actions = {}
        self._register_default_actions(mode)
    
    def _register_default_actions(self, mode: str):
        """
        Register default actions based on simulation mode
        
        Args:
            mode: 'basic' or 'multipopulation'
        """
        # Core actions for ALL simulations
        self.register(StayAction())
        self.register(MoveRandomAction())
        self.register(MoveToLocationAction())
        
        # MultiPopulation-specific action
        if mode == 'multipopulation':
            self.register(TransferToPopulationAction())
    
    def register(self, action: Action):
        """
        Register a new action
        
        Args:
            action: Action instance to register
        """
        self._actions[action.name] = action
    
    def get(self, name: str) -> Action:
        """
        Get action by name with fuzzy matching for robustness
        
        支持以下容错策略:
        1. 精确匹配（最优先）
        2. 大小写不敏感匹配
        3. 常见拼写错误修正
        4. 部分匹配（去除Action后缀）
        
        Args:
            name: Action name
            
        Returns:
            Action instance or None
        """
        if not name:
            return None
        
        # 策略1: 精确匹配（最快路径）
        if name in self._actions:
            return self._actions[name]
        
        # 策略2: 常见拼写错误映射
        common_mistakes = {
            'GotoWorkAction': 'GoToWorkAction',
            'GotoWork': 'GoToWorkAction',
            'gotowork': 'GoToWorkAction',
            'WorkFromHome': 'WorkFromHomeAction',
            'StayHome': 'StayHomeAction',
            'MoveFree': 'MoveFreelyAction',
            'MoveFreely': 'MoveFreelyAction',
            'Shopping': 'ShoppingAction',
            'SeekJob': 'SeekJobAction',
            'SeekMedical': 'SeekMedicalAction',
            'HireEmployee': 'HireEmployeeAction',
            'FireEmployee': 'FireEmployeeAction',
            'CloseBusiness': 'CloseBusinessAction',
            'ReopenBusiness': 'ReopenBusinessAction',
            'AdjustPrice': 'AdjustPriceAction',
            'MaintainOperation': 'MaintainOperationAction',
            'Stay': 'StayAction',
            'MoveRandom': 'MoveRandomAction',
            'MoveToLocation': 'MoveToLocationAction',
        }
        
        if name in common_mistakes:
            corrected_name = common_mistakes[name]
            if corrected_name in self._actions:
                return self._actions[corrected_name]
        
        # 策略3: 大小写不敏感匹配
        name_lower = name.lower()
        for action_name, action in self._actions.items():
            if action_name.lower() == name_lower:
                return action
        
        # 策略4: 部分匹配（处理缺少或多余"Action"后缀的情况）
        # 例如: "GoToWork" 匹配 "GoToWorkAction"
        if not name.endswith('Action'):
            # 尝试添加Action后缀
            name_with_action = name + 'Action'
            if name_with_action in self._actions:
                return self._actions[name_with_action]
            # 大小写不敏感版本
            for action_name, action in self._actions.items():
                if action_name.lower() == name_with_action.lower():
                    return action
        
        # 策略5: 去除Action后缀后匹配
        if name.endswith('Action'):
            name_without_action = name[:-6]  # 去掉"Action"
            for action_name, action in self._actions.items():
                if action_name.startswith(name_without_action):
                    return action
        
        # 所有策略都失败，返回None
        return None
    
    def get_all(self) -> List[Action]:
        """
        Get all registered actions
        
        Returns:
            List of Action instances
        """
        return list(self._actions.values())
    
    def get_action_list_for_prompt(self, filter_actions: List[str] = None) -> str:
        """
        Generate formatted action list for LLM prompt
        
        Args:
            filter_actions: Optional list of action names to include (None = all actions)
        
        Returns:
            str: Formatted action descriptions
        """
        # Filter actions if specified
        if filter_actions is not None:
            actions_to_show = [
                action for name, action in self._actions.items()
                if name in filter_actions
            ]
        else:
            actions_to_show = list(self._actions.values())
        
        lines = []
        for i, action in enumerate(actions_to_show, 1):
            lines.append(f"{i}. **{action.name}**: {action.get_description()}")
            params = action.get_parameters()
            if params:
                # 处理两种参数格式:
                # 1. 字符串列表 (旧格式): ["param1", "param2"]
                # 2. 字典列表 (新格式): [{"name": "param1", "type": "string", ...}, ...]
                if params and isinstance(params[0], dict):
                    # 新格式: 提取name字段
                    param_names = [p['name'] for p in params if 'name' in p]
                    if param_names:
                        lines.append(f"   - Parameters: {', '.join(param_names)}")
                else:
                    # 旧格式: 直接join
                    lines.append(f"   - Parameters: {', '.join(params)}")
        return "\n".join(lines)
    
    def get_action_names(self) -> List[str]:
        """
        Get list of all action names
        
        Returns:
            List[str]: Action names
        """
        return list(self._actions.keys())
    
    def execute_action(self, action_name: str, agent, simulation, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute an action by name
        
        Args:
            action_name: Name of the action to execute
            agent: Agent performing the action
            simulation: Simulation environment
            params: Optional parameters
            
        Returns:
            Dict with execution results
        """
        action = self.get(action_name)
        if action is None:
            # Fallback to stay if action not found
            action = self.get("StayAction")
        
        return action.execute(agent, simulation, params)


# Global action registry instance
_global_registry = None
_global_registry_mode = None

def reset_action_registry():
    """
    Reset the global action registry (for testing/debugging)
    
    WARNING: Only use this if you need to completely reinitialize the registry!
    """
    global _global_registry, _global_registry_mode
    _global_registry = None
    _global_registry_mode = None

def get_action_registry(register_graph_actions: bool = False, mode: str = 'basic') -> ActionRegistry:
    """
    Get the global action registry (singleton pattern)
    
    Args:
        register_graph_actions: If True, register GraphSimulation-specific actions.
                               Should ONLY be True for GraphSimulation.
                               Default False to avoid polluting Basic/MultiPopulation simulations.
        mode: Simulation mode - 'basic' (Stay/MoveRandom/MoveToLocation) or 
              'multipopulation' (adds TransferToPopulationAction).
              Ignored if register_graph_actions=True.
    
    Returns:
        ActionRegistry: Global registry instance
    """
    global _global_registry, _global_registry_mode
    
    # Check if mode changed
    if _global_registry is not None and _global_registry_mode != (register_graph_actions, mode):
        old_graph, old_mode = _global_registry_mode
        
        # Allow upgrade from 'basic' to 'multipopulation' (add Transfer action)
        if old_graph == False and old_mode == 'basic' and register_graph_actions == False and mode == 'multipopulation':
            # Upgrade: add TransferToPopulationAction
            _global_registry.register(TransferToPopulationAction())
            _global_registry_mode = (register_graph_actions, mode)
            print("[ActionRegistry] Upgraded from Basic to MultiPopulation mode (added TransferToPopulationAction)")
            return _global_registry
        
        # Warn about incompatible mode changes
        print(f"[ActionRegistry] Warning: Incompatible mode change from {_global_registry_mode} to ({register_graph_actions}, '{mode}')")
        print(f"[ActionRegistry] Keeping existing registry. Call reset_action_registry() to reinitialize if needed.")
    
    if _global_registry is None:
        _global_registry = ActionRegistry(mode=mode)
        _global_registry_mode = (register_graph_actions, mode)
        
        # ONLY register Graph actions if explicitly requested
        if register_graph_actions:
            _register_graph_actions(_global_registry)
        else:
            if mode == 'basic':
                print("[ActionRegistry] Initialized with Basic actions (Stay, MoveRandom, MoveToLocation)")
            elif mode == 'multipopulation':
                print("[ActionRegistry] Initialized with MultiPopulation actions (Stay, MoveRandom, MoveToLocation, Transfer)")
    
    return _global_registry


def _register_graph_actions(registry: ActionRegistry):
    """
    Register GraphSimulation-specific actions
    
    WARNING: This should ONLY be called for GraphSimulation!
    Do NOT call this for Basic or MultiPopulation simulations!
    """
    try:
        from covid_abs.llm.graph_actions import (
            # Person Actions
            GoToWorkAction,
            StayHomeAction,
            WorkFromHomeAction,
            SeekMedicalAction,
            SeekJobAction,
            ShoppingAction,
            MoveFreelyAction,
            # Business Actions
            HireEmployeeAction,
            FireEmployeeAction,
            AdjustPriceAction,
            MaintainOperationAction,
            CloseBusinessAction,
            ReopenBusinessAction,
            # Government Actions
            AdjustTaxRateAction,
            ProvideStimulusAction,
            PublicProcurementAction,  # ✅ Enabled
            IncreaseMedicalBudgetAction,
            IssueStayHomeOrderAction,
            IssueMandatoryStayHomeOrderAction,  # ✅ Added for Scenario B
            LiftStayHomeOrderAction,
            CloseBordersAction,
            MaintainPolicyAction,
            EmergencyLockdownAction,  # ✅ Health Priority场景紧急封锁
            # 🎬 扩展的丰富政策Actions（暂时注释，不导入）
            # IssueBusinessSubsidyAction,
            # ImplementContactTracingAction,
            # LaunchVaccinationCampaignAction,
            # IssuePartialLockdownAction,
            # LiftPartialLockdownAction,
            # AdjustBusinessRegulationAction,
            # LiftBusinessRegulationAction
        )
        
        # Register Person actions
        person_actions = [
            GoToWorkAction(),
            StayHomeAction(),
            WorkFromHomeAction(),
            SeekMedicalAction(),
            SeekJobAction(),
            ShoppingAction(),
            MoveFreelyAction(),
        ]
        
        # Register Business actions
        from covid_abs.llm.graph_actions import ForeignTradeAction
        business_actions = [
            HireEmployeeAction(),
            FireEmployeeAction(),
            AdjustPriceAction(),
            MaintainOperationAction(),
            CloseBusinessAction(),
            ReopenBusinessAction(),
            ForeignTradeAction(),  # 🔧 新增：对外贸易Action
        ]
        
        # Register Government actions
        government_actions = [
            AdjustTaxRateAction(),
            ProvideStimulusAction(),
            PublicProcurementAction(),  # ✅ Enabled
            IncreaseMedicalBudgetAction(),
            IssueStayHomeOrderAction(),
            IssueMandatoryStayHomeOrderAction(),  # ✅ Added for Scenario B
            LiftStayHomeOrderAction(),
            CloseBordersAction(),
            MaintainPolicyAction(),
            EmergencyLockdownAction(),  # ✅ Health Priority场景紧急封锁
            # 🎬 扩展的丰富政策Actions（已在graph_message中对LLM可见，但暂时注释不注册，用于实验控制）
            # IssueBusinessSubsidyAction(),
            # ImplementContactTracingAction(),
            # LaunchVaccinationCampaignAction(),
            # IssuePartialLockdownAction(),
            # LiftPartialLockdownAction(),
            # AdjustBusinessRegulationAction(),
            # LiftBusinessRegulationAction(),
        ]
        
        # Register all actions
        for action in person_actions:
            registry.register(action)
        for action in business_actions:
            registry.register(action)
        for action in government_actions:
            registry.register(action)
        
        # ✅ 动态计算并显示实际注册的Action数量
        print(f"[ActionRegistry] Graph actions registered successfully "
              f"({len(person_actions)} Person + {len(business_actions)} Business + {len(government_actions)} Government)")
    except ImportError as e:
        print(f"[ActionRegistry] Warning: Failed to import graph actions: {e}")
        # Graph actions are optional, continue without them
