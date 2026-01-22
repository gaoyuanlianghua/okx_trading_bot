from loguru import logger

class AgentRegistry:
    """智能体注册表，用于管理所有智能体"""
    
    def __init__(self):
        self.agents = {}  # 智能体注册表
        logger.info("智能体注册表初始化完成")
    
    def register_agent(self, agent):
        """注册智能体
        
        Args:
            agent (BaseAgent): 智能体实例
        """
        if agent.agent_id not in self.agents:
            self.agents[agent.agent_id] = agent
            logger.info(f"智能体注册成功: {agent.agent_id}")
            return True
        else:
            logger.warning(f"智能体已存在: {agent.agent_id}")
            return False
    
    def unregister_agent(self, agent_id):
        """注销智能体
        
        Args:
            agent_id (str): 智能体ID
        """
        if agent_id in self.agents:
            agent = self.agents.pop(agent_id)
            agent.stop()
            logger.info(f"智能体注销成功: {agent_id}")
            return True
        else:
            logger.warning(f"智能体不存在: {agent_id}")
            return False
    
    def get_agent(self, agent_id):
        """获取智能体实例
        
        Args:
            agent_id (str): 智能体ID
            
        Returns:
            BaseAgent: 智能体实例
        """
        return self.agents.get(agent_id)
    
    def get_all_agents(self):
        """获取所有智能体实例
        
        Returns:
            list: 智能体实例列表
        """
        return list(self.agents.values())
    
    def get_agent_status(self):
        """获取所有智能体状态
        
        Returns:
            dict: 智能体状态字典
        """
        status = {}
        for agent_id, agent in self.agents.items():
            status[agent_id] = {
                "status": agent.status,
                "agent_type": agent.__class__.__name__
            }
        return status
    
    def start_all_agents(self):
        """启动所有智能体"""
        for agent in self.agents.values():
            agent.start()
        logger.info(f"启动所有智能体完成，共 {len(self.agents)} 个智能体")
    
    def stop_all_agents(self):
        """停止所有智能体"""
        for agent in self.agents.values():
            agent.stop()
        logger.info(f"停止所有智能体完成，共 {len(self.agents)} 个智能体")

# 创建全局智能体注册表实例
global_agent_registry = AgentRegistry()