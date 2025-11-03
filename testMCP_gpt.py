import asyncio
import json
import os
import random
import uuid
from typing import Dict, Any, Optional

import httpx
from mcp import types

# === Настройки подключения к MCP серверу ===
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", 8000))
BASE_URL = f"http://{MCP_HOST}:{MCP_PORT}"

AUTH_MODE = os.getenv("MCP_AUTH_MODE", "none")
ACCESS_TOKEN = os.getenv("MCP_ACCESS_TOKEN", None)


class MCPClient:
    """Минимальный клиент для работы с MCP сервером 1С через JSON-RPC"""

    def __init__(self, base_url: str, auth_token: Optional[str] = None):
        self.base_url = base_url
        self.auth_token = auth_token
        self.client = httpx.AsyncClient(timeout=30.0)
        self.session_id: Optional[str] = None

    async def initialize_session(self) -> bool:
        """Создаёт MCP сессию через /mcp/initialize"""
        url = f"{self.base_url}/mcp/initialize"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {
                    "name": "TestMCP",
                    "version": "1.0.0"
                },
                "capabilities": {}
            }
        }

        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        try:
            resp = await self.client.post(url, json=payload, headers=headers)
            print("Ответ initialize:", resp.text)

            text = resp.text.strip()
            if text.startswith("event:"):
                text = text.split("data:", 1)[1].strip()

            data = json.loads(text)
            if "result" in data:
                result = data["result"]
                version = result.get("protocolVersion")
                server = result.get("serverInfo", {}).get("name")
                print(f"✅ MCP initialized: protocol={version}, server={server}")
                return True

            print("⚠️ Некорректный ответ initialize:", data)
            return False

        except Exception as e:
            print(f"Ошибка инициализации MCP: {e}")
            return False


    async def _make_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Отправляет JSON-RPC запрос через /mcp/request"""
        if not self.session_id:
            return {"error": "Session not initialized"}

        url = f"{self.base_url}/mcp/request"
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }

        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": {"session_id": self.session_id, **params}
        }

        try:
            response = await self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
        except Exception as e:
            return {"error": str(e)}

    async def list_tools(self) -> types.ListToolsResult:
        """Получение списка инструментов"""
        response = await self._make_request("tools/list", {})
        if "error" in response:
            print("Ошибка list_tools:", response["error"])
            return types.ListToolsResult(tools=[])

        tools_data = response.get("result", {}).get("tools", [])
        tools = [
            types.Tool(
                name=t["name"],
                description=t.get("description", ""),
                inputSchema=t.get("inputSchema", {})
            )
            for t in tools_data
        ]
        return types.ListToolsResult(tools=tools)

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> types.CallToolResult:
        """Вызов MCP-инструмента"""
        response = await self._make_request("tools/call", {"name": name, "arguments": arguments})
        if "error" in response:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"Error: {response['error']}")],
                isError=True
            )

        result_data = response.get("result", {})
        content_data = result_data.get("content", [])
        content = []
        for item in content_data:
            if item.get("type") == "text":
                content.append(types.TextContent(type="text", text=item.get("text", "")))
        return types.CallToolResult(content=content, isError=False)

    async def close(self):
        await self.client.aclose()


# === Тестовые функции ===

async def test_list_metadata_objects(client: MCPClient, meta_type: str, name_mask=None, max_items=10):
    """Тестирование инструмента list_metadata_objects"""
    args = {"metaType": meta_type, "nameMask": name_mask, "maxItems": max_items}
    result = await client.call_tool("list_metadata_objects", args)
    if result.isError:
        return {"error": result.content[0].text}
    text = result.content[0].text if result.content else "{}"
    try:
        return json.loads(text)
    except Exception:
        return {"result": text}


def log_test(api, params, result):
    """Запись результатов теста"""
    output = f"API: {api}\nПараметры: {json.dumps(params, indent=2, ensure_ascii=False)}\nРезультат: {json.dumps(result, indent=2, ensure_ascii=False)}\n{'='*60}\n"
    print(output)
    with open("testMCP.md", "a", encoding="utf-8") as f:
        f.write(output)


# === Основной цикл тестов ===

async def run_tests_async():
    client = MCPClient(BASE_URL, ACCESS_TOKEN)

    if os.path.exists("testMCP.md"):
        os.remove("testMCP.md")

    if not await client.initialize_session():
        print("❌ Не удалось подключиться к MCP серверу")
        return

    print("✅ Подключено к MCP серверу:", BASE_URL)

    # Список типов метаданных
    meta_types = [
        "Catalogs", "Documents", "InformationRegisters",
        "AccumulationRegisters", "AccountingRegisters"
    ]

    for i in range(10):
        meta_type = random.choice(meta_types)
        mask = random.choice(["Номенклатура", "Документ", None])
        max_items = random.randint(1, 30)
        result = await test_list_metadata_objects(client, meta_type, mask, max_items)
        log_test("list_metadata_objects", {"metaType": meta_type, "mask": mask, "maxItems": max_items}, result)

    await client.close()
    print("✅ Тестирование завершено.")


def run_tests():
    asyncio.run(run_tests_async())


if __name__ == "__main__":
    run_tests()
