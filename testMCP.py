import asyncio
import json
import os
import random
import time
import uuid
from typing import Dict, Any, Optional

import httpx
from mcp import types

# Настройки подключения к MCP серверу
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = 8000
BASE_URL = f"http://{MCP_HOST}:{MCP_PORT}"

# Настройки авторизации (если требуется)
AUTH_MODE = os.getenv("MCP_AUTH_MODE", "none")
ACCESS_TOKEN = os.getenv("MCP_ACCESS_TOKEN", None)

class MCPClient:
    """MCP клиент для тестирования сервера через SSE транспорт."""

    def __init__(self, base_url: str, auth_token: Optional[str] = None):
        self.base_url = base_url
        self.auth_token = auth_token
        self.client = httpx.AsyncClient(timeout=30.0)
        self.session_id: str = str(uuid.uuid4())

    async def _make_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Отправка HTTP запроса к MCP серверу."""
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/jsonrpc+json", "Accept": "application/json", "User-Agent": "MCP-Client/1.0"}

        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        # Добавляем session_id в URL для SSE сообщений
        if endpoint == "/sse/messages/":
            url += f"?session_id={self.session_id}"

        try:
            response = await self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return {"error": str(e)}

    async def initialize_session(self) -> bool:
        """Инициализация MCP сессии."""
        try:
            # Проверяем доступность сервера через health endpoint
            response = await self.client.get(f"{self.base_url}/health", timeout=5.0, follow_redirects=True)
            if response.status_code == 200:
                data = response.json()
                return data.get("status") == "healthy"
            return False
        except:
            return False

    async def list_tools(self) -> types.ListToolsResult:
        """Получение списка инструментов через SSE."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
            "session_id": self.session_id,
            "protocolVersion": "2024-11-05"
        }
        response = await self._make_request("/mcp/", payload)

        if "error" in response:
            return types.ListToolsResult(tools=[])

        tools_data = response.get("result", {}).get("tools", [])
        tools = []
        for tool_data in tools_data:
            tools.append(types.Tool(
                name=tool_data["name"],
                description=tool_data.get("description", ""),
                inputSchema=tool_data.get("inputSchema", {})
            ))

        return types.ListToolsResult(tools=tools)

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> types.CallToolResult:
        """Вызов инструмента через SSE."""
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments
            },
            "session_id": self.session_id
        }
        response = await self._make_request("/mcp/", payload)

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
                content.append(types.TextContent(
                    type="text",
                    text=item.get("text", "")
                ))
            elif item.get("type") == "image":
                content.append(types.ImageContent(
                    type="image",
                    data=item.get("data", ""),
                    mimeType=item.get("mimeType", "")
                ))

        return types.CallToolResult(
            content=content,
            isError=result_data.get("isError", False)
        )

    async def list_resources(self) -> types.ListResourcesResult:
        """Получение списка ресурсов через SSE."""
        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "resources/list",
            "params": {},
            "session_id": self.session_id
        }
        response = await self._make_request("/mcp/", payload)

        if "error" in response:
            return types.ListResourcesResult(resources=[])

        resources_data = response.get("result", {}).get("resources", [])
        resources = []

        for res_data in resources_data:
            resources.append(types.Resource(
                uri=res_data["uri"],
                name=res_data.get("name", ""),
                description=res_data.get("description", ""),
                mimeType=res_data.get("mimeType")
            ))

        return types.ListResourcesResult(resources=resources)

    async def read_resource(self, uri: str) -> types.ReadResourceResult:
        """Чтение ресурса через SSE."""
        payload = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "resources/read",
            "params": {"uri": uri},
            "session_id": self.session_id
        }
        response = await self._make_request("/sse/messages/", payload)

        if "error" in response:
            return types.ReadResourceResult(
                contents=[types.TextResourceContents(
                    uri=uri,
                    text=f"Error: {response['error']}",
                    mimeType="text/plain"
                )]
            )

        contents_data = response.get("result", {}).get("contents", [])
        contents = []

        for item in contents_data:
            if item.get("type") == "text":
                contents.append(types.TextResourceContents(
                    uri=uri,
                    text=item.get("text", ""),
                    mimeType=item.get("mimeType", "text/plain")
                ))
            elif item.get("type") == "blob":
                contents.append(types.BlobResourceContents(
                    uri=uri,
                    blob=item.get("data", ""),
                    mimeType=item.get("mimeType", "application/octet-stream")
                ))

        return types.ReadResourceResult(contents=contents)

    async def list_prompts(self) -> types.ListPromptsResult:
        """Получение списка промптов через SSE."""
        payload = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "prompts/list",
            "params": {},
            "session_id": self.session_id
        }
        response = await self._make_request("/sse/messages/", payload)

        if "error" in response:
            return types.ListPromptsResult(prompts=[])

        prompts_data = response.get("result", {}).get("prompts", [])
        prompts = []

        for prompt_data in prompts_data:
            arguments = []
            for arg_data in prompt_data.get("arguments", []):
                arguments.append(types.PromptArgument(
                    name=arg_data["name"],
                    description=arg_data.get("description", ""),
                    required=arg_data.get("required", False)
                ))

            prompts.append(types.Prompt(
                name=prompt_data["name"],
                description=prompt_data.get("description", ""),
                arguments=arguments
            ))

        return types.ListPromptsResult(prompts=prompts)

    async def get_prompt(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> types.GetPromptResult:
        """Получение промпта через SSE."""
        payload = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "prompts/get",
            "params": {
                "name": name,
                "arguments": arguments or {}
            },
            "session_id": self.session_id
        }
        response = await self._make_request("/sse/messages/", payload)

        if "error" in response:
            return types.GetPromptResult(
                description="Error",
                messages=[types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"Error: {response['error']}"
                    )
                )]
            )

        result_data = response.get("result", {})
        messages_data = result_data.get("messages", [])
        messages = []

        for msg_data in messages_data:
            content_data = msg_data.get("content", {})
            if content_data.get("type") == "text":
                content = types.TextContent(
                    type="text",
                    text=content_data.get("text", "")
                )
            else:
                content = types.TextContent(type="text", text="")

            messages.append(types.PromptMessage(
                role=msg_data.get("role", "user"),
                content=content
            ))

        return types.GetPromptResult(
            description=result_data.get("description", ""),
            messages=messages
        )

    async def close(self):
        """Закрытие клиента."""
        await self.client.aclose()

# Глобальный клиент
client: Optional[MCPClient] = None

# Функции-обёртки для обратной совместимости с существующим кодом тестирования
async def test_list_metadata_objects(meta_type, name_mask=None, max_items=10):
    """Тестирование list_metadata_objects через MCP tools."""
    if not client:
        return {"error": "MCP client not initialized"}

    try:
        result = await client.call_tool("list_metadata_objects", {
            "metaType": meta_type,
            "nameMask": name_mask,
            "maxItems": max_items
        })

        # Преобразование MCP результата в старый формат для совместимости
        if result.isError:
            return {"error": result.content[0].text if result.content else "Unknown error"}

        # Извлечение JSON из текстового контента
        content_text = result.content[0].text if result.content else "{}"
        try:
            return json.loads(content_text)
        except:
            return {"result": content_text}

    except Exception as e:
        return {"error": str(e)}

async def test_get_metadata_structure(meta_type, name):
    """Тестирование get_metadata_structure через MCP tools."""
    if not client:
        return {"error": "MCP client not initialized"}

    try:
        result = await client.call_tool("get_metadata_structure", {
            "metaType": meta_type,
            "name": name
        })

        if result.isError:
            return {"error": result.content[0].text if result.content else "Unknown error"}

        content_text = result.content[0].text if result.content else "{}"
        try:
            return json.loads(content_text)
        except:
            return {"result": content_text}

    except Exception as e:
        return {"error": str(e)}

async def test_list_predefined_data(meta_type, name, predefined_mask=None, max_items=10):
    """Тестирование list_predefined_data через MCP tools."""
    if not client:
        return {"error": "MCP client not initialized"}

    try:
        args = {
            "metaType": meta_type,
            "name": name,
            "maxItems": max_items
        }
        if predefined_mask:
            args["predefinedMask"] = predefined_mask

        result = await client.call_tool("list_predefined_data", args)

        if result.isError:
            return {"error": result.content[0].text if result.content else "Unknown error"}

        content_text = result.content[0].text if result.content else "{}"
        try:
            return json.loads(content_text)
        except:
            return {"result": content_text}

    except Exception as e:
        return {"error": str(e)}

async def test_get_predefined_data(meta_type, name, predefined_name):
    """Тестирование get_predefined_data через MCP tools."""
    if not client:
        return {"error": "MCP client not initialized"}

    try:
        result = await client.call_tool("get_predefined_data", {
            "metaType": meta_type,
            "name": name,
            "predefinedName": predefined_name
        })

        if result.isError:
            return {"error": result.content[0].text if result.content else "Unknown error"}

        content_text = result.content[0].text if result.content else "{}"
        try:
            return json.loads(content_text)
        except:
            return {"result": content_text}

    except Exception as e:
        return {"error": str(e)}

async def test_access_mcp_resource(uri):
    """Тестирование чтения MCP ресурса."""
    if not client:
        return {"error": "MCP client not initialized"}

    try:
        result = await client.read_resource(uri)

        # Преобразование в старый формат
        if not result.contents:
            return {"error": "No content"}

        content = result.contents[0]
        if hasattr(content, 'text'):
            try:
                return json.loads(content.text)
            except:
                return {"result": content.text}
        else:
            return {"result": "Binary content"}

    except Exception as e:
        return {"error": str(e)}

# Список типов метаданных для тестирования (без изменений)
meta_types = [
    "Catalogs", "Documents", "InformationRegisters", "AccumulationRegisters",
    "AccountingRegisters", "CalculationRegisters", "ChartsOfCharacteristicTypes",
    "ChartsOfAccounts", "ChartsOfCalculationTypes", "BusinessProcesses", "Tasks",
    "ExchangePlans", "FilterCriteria", "Reports", "DataProcessors", "Enums",
    "CommonModules", "SessionParameters", "CommonTemplates", "CommonPictures",
    "XDTOPackages", "WebServices", "HTTPServices", "WSReferences", "Styles",
    "Languages", "FunctionalOptions", "FunctionalOptionsParameters", "DefinedTypes",
    "CommonAttributes", "CommonCommands", "CommandGroups", "Constants",
    "CommonForms", "Roles", "Subsystems", "EventSubscriptions", "ScheduledJobs",
    "SettingsStorages", "Sequences", "DocumentJournals", "ExternalDataSources",
    "Interfaces"
]

# Типы для predefined (без изменений)
predefined_types = ["Catalogs", "ChartsOfCharacteristicTypes", "ChartsOfAccounts", "ChartsOfCalculationTypes"]

# Функция для логирования (без изменений)
def log_test(api, params, result):
    output = f"API: {api}\nПараметры: {json.dumps(params, indent=2)}\nРезультат: {json.dumps(result, indent=2)}\n{'='*50}\n"
    print(output)
    with open("testMCP.md", "a", encoding="utf-8") as f:
        f.write(output)

# Асинхронная основная функция тестирования
async def run_tests_async():
    global client

    # Очистка файла
    if os.path.exists("testMCP.md"):
        os.remove("testMCP.md")

    # Инициализация MCP клиента
    auth_token = ACCESS_TOKEN if AUTH_MODE == "oauth2" else None
    client = MCPClient(BASE_URL, auth_token)

    # Проверка подключения
    if not await client.initialize_session():
        print("Не удалось подключиться к MCP серверу")
        return

    print(f"Подключено к MCP серверу: {BASE_URL}")

    # Для streamable HTTP транспорта нужно сначала сделать initialize
    try:
        initialize_payload = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            },
            "session_id": client.session_id,
            "protocolVersion": "2024-11-05"
        }
        initialize_response = await client._make_request("/sse/messages/", initialize_payload)
        print(f"Initialize response: {initialize_response}")
    except Exception as e:
        print(f"Ошибка initialize запроса: {e}")

    test_count = 0

    # Статические тесты для list_metadata_objects (20 тестов)
    print("Запуск тестов list_metadata_objects...")
    for i in range(20):
        meta_type = random.choice(meta_types)
        name_mask = random.choice([None, "Test", "Номенклатура", "Документ"])
        max_items = random.randint(1, 50)
        result = await test_list_metadata_objects(meta_type, name_mask, max_items)
        log_test("list_metadata_objects", {"metaType": meta_type, "nameMask": name_mask, "maxItems": max_items}, result)
        test_count += 1

    # Получить списки метаданных для динамических тестов
    catalogs = await test_list_metadata_objects("Catalogs", max_items=50)
    documents = await test_list_metadata_objects("Documents", max_items=50)
    registers = await test_list_metadata_objects("AccumulationRegisters", max_items=50)

    # Динамические тесты для get_metadata_structure (20 тестов)
    print("Запуск тестов get_metadata_structure...")
    for i in range(20):
        if catalogs.get("result") and isinstance(catalogs["result"], list) and catalogs["result"]:
            obj = random.choice(catalogs["result"])
            name = obj.get("name") if isinstance(obj, dict) else str(obj)
            result = await test_get_metadata_structure("Catalogs", name)
            log_test("get_metadata_structure", {"metaType": "Catalogs", "name": name}, result)
        elif documents.get("result") and isinstance(documents["result"], list) and documents["result"]:
            obj = random.choice(documents["result"])
            name = obj.get("name") if isinstance(obj, dict) else str(obj)
            result = await test_get_metadata_structure("Documents", name)
            log_test("get_metadata_structure", {"metaType": "Documents", "name": name}, result)
        else:
            # Fallback
            result = await test_get_metadata_structure("Catalogs", "Номенклатура")
            log_test("get_metadata_structure", {"metaType": "Catalogs", "name": "Номенклатура"}, result)
        test_count += 1

    # Тесты для list_predefined_data (20 тестов)
    print("Запуск тестов list_predefined_data...")
    for i in range(20):
        meta_type = random.choice(predefined_types)
        # Получить список объектов для типа
        objs = await test_list_metadata_objects(meta_type, max_items=20)
        if objs.get("result") and isinstance(objs["result"], list) and objs["result"]:
            obj = random.choice(objs["result"])
            name = obj.get("name") if isinstance(obj, dict) else str(obj)
            predefined_mask = random.choice([None, "Основной", "Test"])
            result = await test_list_predefined_data(meta_type, name, predefined_mask, max_items=10)
            log_test("list_predefined_data", {"metaType": meta_type, "name": name, "predefinedMask": predefined_mask, "maxItems": 10}, result)
        else:
            result = await test_list_predefined_data("Catalogs", "Номенклатура", None, 10)
            log_test("list_predefined_data", {"metaType": "Catalogs", "name": "Номенклатура", "maxItems": 10}, result)
        test_count += 1

    # Тесты для get_predefined_data (20 тестов)
    print("Запуск тестов get_predefined_data...")
    for i in range(20):
        meta_type = random.choice(predefined_types)
        objs = await test_list_metadata_objects(meta_type, max_items=10)
        if objs.get("result") and isinstance(objs["result"], list) and objs["result"]:
            obj = random.choice(objs["result"])
            name = obj.get("name") if isinstance(obj, dict) else str(obj)
            predefined_list = await test_list_predefined_data(meta_type, name, max_items=10)
            if predefined_list.get("result") and isinstance(predefined_list["result"], list) and predefined_list["result"]:
                predefined = random.choice(predefined_list["result"])
                predefined_name = predefined.get("name") if isinstance(predefined, dict) else str(predefined)
                result = await test_get_predefined_data(meta_type, name, predefined_name)
                log_test("get_predefined_data", {"metaType": meta_type, "name": name, "predefinedName": predefined_name}, result)
            else:
                result = await test_get_predefined_data("Catalogs", "Номенклатура", "ОсновнаяЕдиницаИзмерения")
                log_test("get_predefined_data", {"metaType": "Catalogs", "name": "Номенклатура", "predefinedName": "ОсновнаяЕдиницаИзмерения"}, result)
        else:
            result = await test_get_predefined_data("Catalogs", "Номенклатура", "ОсновнаяЕдиницаИзмерения")
            log_test("get_predefined_data", {"metaType": "Catalogs", "name": "Номенклатура", "predefinedName": "ОсновнаяЕдиницаИзмерения"}, result)
        test_count += 1

    # Тесты для access_mcp_resource (20 тестов)
    print("Запуск тестов access_mcp_resource...")
    for i in range(20):
        uri = "file://resource/syntax_1c.txt"  # Единственный известный ресурс
        result = await test_access_mcp_resource(uri)
        log_test("access_mcp_resource", {"uri": uri}, result)
        test_count += 1

    # Закрытие клиента
    await client.close()

    print(f"Всего выполнено тестов: {test_count}")

# Синхронная обёртка для обратной совместимости
def run_tests():
    """Синхронная обёртка для запуска асинхронных тестов."""
    asyncio.run(run_tests_async())

if __name__ == "__main__":
    run_tests()