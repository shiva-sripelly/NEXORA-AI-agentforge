from app.mcp.permissions import require_executable
from app.repositories.mcp_repository import MCPRepository


class ToolRegistry:
    def __init__(self, db):
        self.repo = MCPRepository(db)

    async def available(self, user_id):
        return await self.repo.tools(user_id, enabled_only=True)

    async def llm_tools(self, user_id):
        tools, names = [], set()
        for tool in await self.available(user_id):
            if tool.external_name in names:
                continue
            names.add(tool.external_name)
            tools.append({"type": "function", "function": {
                "name": tool.external_name, "description": tool.description or tool.display_name,
                "parameters": tool.input_schema,
            }})
        return tools

    async def by_external_name(self, user_id, name):
        for tool in await self.available(user_id):
            if tool.external_name == name:
                require_executable(tool)
                return tool
        return None
