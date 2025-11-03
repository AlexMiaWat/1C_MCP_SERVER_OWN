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
            print("Headers initialize:", dict(resp.headers))

            text = resp.text.strip()
            if text.startswith("event:"):
                data_lines = [line[5:].strip() for line in text.split("\n") if line.startswith("data:")]
                data_str = "\n".join(data_lines)  # Handle multi-line data if needed
                data = json.loads(data_str)
            else:
                data = resp.json()

            if "result" in data:
                result = data["result"]
                version = result.get("protocolVersion")
                server = result.get("serverInfo", {}).get("name")
                print(f"[OK] MCP initialized: protocol={version}, server={server}")

                # Capture session ID from header if present
                self.session_id = resp.headers.get("Mcp-Session-Id")
                if self.session_id:
                    print(f"Session ID assigned: {self.session_id}")
                else:
                    print("No Mcp-Session-Id header found; proceeding without session ID.")

                return True

            print("[WARN] Некорректный ответ initialize:", data)
            return False

        except Exception as e:
            print(f"[ERROR] Ошибка инициализации MCP: {e}")
            return False

    async def _make_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Отправляет JSON-RPC запрос через /mcp/request"""
        url = f"{self.base_url}/mcp/request"
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }

        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params  # No session_id in params; use header if available
        }

        try:
            response = await self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()

            text = response.text.strip()
            if text.startswith("event:"):
                data_lines = [line[5:].strip() for line in text.split("\n") if line.startswith("data:")]
                data_str = "\n".join(data_lines)
                return json.loads(data_str)
            else:
                return response.json()
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
        except json.JSONDecodeError as e:
            return {"error": f"JSON decode error: {str(e)} - Response: {response.text}"}
        except Exception as e:
            return {"error": str(e)}

    async def list_tools(self) -> types.ListToolsResult:
        """Получение списка инструментов"""
        response = await self._make_request("tools/list", {})
        if "error" in response:
            print("[ERROR] list_tools:", response["error"])
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

async def test_list_metadata_objects(client: MCPClient, meta_type: str, name_mask="", max_items=10):
    """Тестирование инструмента list_metadata_objects"""
    args = {"metaType": meta_type, "nameMask": name_mask, "maxItems": max_items}
    result = await client.call_tool("list_metadata_objects", args)
    if result.isError:
        return {"error": str(result.content[0])}
    text = result.content[0].text if result.content else ""
    try:
        return json.loads(text)
    except Exception:
        return {"result": text}


async def test_get_metadata_structure(client: MCPClient, meta_type: str, name: str):
    """Тестирование инструмента get_metadata_structure"""
    args = {"metaType": meta_type, "name": name}
    result = await client.call_tool("get_metadata_structure", args)
    if result.isError:
        return {"error": str(result.content[0])}
    text = result.content[0].text if result.content else ""
    try:
        return json.loads(text)
    except Exception:
        return {"result": text}


async def test_list_predefined_data(client: MCPClient, meta_type: str, name: str, predefined_mask="", max_items=10):
    """Тестирование инструмента list_predefined_data"""
    args = {"metaType": meta_type, "name": name, "predefinedMask": predefined_mask, "maxItems": max_items}
    result = await client.call_tool("list_predefined_data", args)
    if result.isError:
        return {"error": str(result.content[0])}
    text = result.content[0].text if result.content else ""
    try:
        return json.loads(text)
    except Exception:
        return {"result": text}


async def test_get_predefined_data(client: MCPClient, meta_type: str, name: str, predefined_name: str):
    """Тестирование инструмента get_predefined_data"""
    args = {"metaType": meta_type, "name": name, "predefinedName": predefined_name}
    result = await client.call_tool("get_predefined_data", args)
    if result.isError:
        return {"error": str(result.content[0])}
    text = result.content[0].text if result.content else ""
    try:
        return json.loads(text)
    except Exception:
        return {"result": text}


def log_test(test_number, api, params, result):
    """Запись результатов теста"""
    output = f"Тест #{test_number}\nAPI: {api}\nПараметры: {json.dumps(params, indent=2, ensure_ascii=False)}\nРезультат: {json.dumps(result, indent=2, ensure_ascii=False)}\n{'='*60}\n"
    print(output)
    with open("testMCP.md", "a", encoding="utf-8") as f:
        f.write(output)


# === Основной цикл тестов ===

async def run_tests_async():
    client = MCPClient(BASE_URL, ACCESS_TOKEN)

    if os.path.exists("testMCP.md"):
        os.remove("testMCP.md")

    if not await client.initialize_session():
        print("[ERROR] Не удалось подключиться к MCP серверу")
        return

    print("[INFO] Подключено к MCP серверу:", BASE_URL)

    # Типы метаданных, поддерживающие предопределенные данные
    predefined_supported_types = [
        "Catalogs", "ChartsOfCharacteristicTypes", "ChartsOfAccounts", "ChartsOfCalculationTypes"
    ]

    methods = ["list_metadata_objects", "get_metadata_structure", "list_predefined_data", "get_predefined_data"]
    method_stats = {method: {"total": 0, "success": 0, "errors": 0, "skipped": 0} for method in methods}
    error_keywords = ["ошибка", "исключение", "не найден", "error", "exception", "not found", "вызватьисключение"]

    for i in range(200):
        test_number = i + 1

        # Шаг 1: Выбрать случайный тип метаданных, приоритет на те, что поддерживают предопределенные данные
        all_types = [
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

        # 70% шанс выбрать тип с предопределенными данными, 30% - остальные
        if random.random() < 0.7:
            meta_type = random.choice(predefined_supported_types)
        else:
            meta_type = random.choice(all_types)

        # Шаг 2: Получить список объектов этого типа
        mask = random.choice(["", "Номенклатура", "Документ"])
        max_items = random.randint(5, 20)
        list_result = await test_list_metadata_objects(client, meta_type, mask, max_items)
        log_test(test_number, "list_metadata_objects", {"metaType": meta_type, "nameMask": mask, "maxItems": max_items}, list_result)

        method_stats["list_metadata_objects"]["total"] += 1
        # Проверяем на ошибки в результате list_metadata_objects
        if "error" in list_result:
            method_stats["list_metadata_objects"]["errors"] += 1
            continue
        elif isinstance(list_result, dict) and "result" in list_result and isinstance(list_result["result"], str) and any(keyword in list_result["result"].lower() for keyword in error_keywords):
            method_stats["list_metadata_objects"]["errors"] += 1
            continue
        elif (isinstance(list_result, list) and not list_result) or (isinstance(list_result, dict) and "result" in list_result and list_result["result"] == ""):
            method_stats["list_metadata_objects"]["skipped"] += 1
            continue
        else:
            method_stats["list_metadata_objects"]["success"] += 1

        # Шаг 3: Если есть объекты, выбрать случайный и получить его структуру
        objects = []
        if isinstance(list_result, list):
            objects = [{"name": obj.split('.')[-1] if '.' in obj else obj} for obj in list_result if obj]
        elif isinstance(list_result, dict) and "result" in list_result:
            result_text = list_result["result"]
            if isinstance(result_text, str):
                for line in result_text.split('\n'):
                    line = line.strip()
                    if line:
                        name = line.split('(')[0].strip() if '(' in line else line.strip()
                        if '.' in name:
                            name = name.split('.')[-1]
                        if name:
                            objects.append({"name": name})
            elif isinstance(result_text, list):
                objects = [{"name": obj.split('.')[-1] if '.' in obj else obj} for obj in result_text if obj]

        if objects:
            random_object = random.choice(objects)
            object_name = random_object.get("name", random_object.get("Name", "")) if isinstance(random_object, dict) else str(random_object)

            if object_name:
                # Шаг 3: Получить структуру метаданных
                structure_result = await test_get_metadata_structure(client, meta_type, object_name)
                log_test(test_number, "get_metadata_structure", {"metaType": meta_type, "name": object_name}, structure_result)

                method_stats["get_metadata_structure"]["total"] += 1
                # Проверяем на ошибки в результате
                if "error" in structure_result:
                    method_stats["get_metadata_structure"]["errors"] += 1
                elif isinstance(structure_result, dict) and "result" in structure_result and isinstance(structure_result["result"], str) and any(keyword in structure_result["result"].lower() for keyword in error_keywords):
                    method_stats["get_metadata_structure"]["errors"] += 1
                elif (isinstance(structure_result, list) and not structure_result) or (isinstance(structure_result, dict) and "result" in structure_result and structure_result["result"] == ""):
                    method_stats["get_metadata_structure"]["skipped"] += 1
                else:
                    method_stats["get_metadata_structure"]["success"] += 1

                # Шаг 4: Если тип поддерживает предопределенные данные, получить их список
                if meta_type in predefined_supported_types:
                    predefined_mask = random.choice(["", "Основной", "Дополнительный"])
                    predefined_list_result = await test_list_predefined_data(client, meta_type, object_name, predefined_mask, max_items)
                    log_test(test_number, "list_predefined_data", {"metaType": meta_type, "name": object_name, "predefinedMask": predefined_mask, "maxItems": max_items}, predefined_list_result)

                    method_stats["list_predefined_data"]["total"] += 1
                    # Проверяем на ошибки в результате
                    if "error" in predefined_list_result:
                        method_stats["list_predefined_data"]["errors"] += 1
                        continue
                    elif isinstance(predefined_list_result, dict) and "result" in predefined_list_result and isinstance(predefined_list_result["result"], str) and any(keyword in predefined_list_result["result"].lower() for keyword in error_keywords):
                        method_stats["list_predefined_data"]["errors"] += 1
                        continue
                    elif (isinstance(predefined_list_result, list) and not predefined_list_result) or (isinstance(predefined_list_result, dict) and "result" in predefined_list_result and predefined_list_result["result"] == ""):
                        method_stats["list_predefined_data"]["skipped"] += 1
                        continue
                    else:
                        method_stats["list_predefined_data"]["success"] += 1

                    # Шаг 5: Если есть предопределенные данные, выбрать несколько случайных и получить их детали
                    predefined_objects = []
                    if isinstance(predefined_list_result, list):
                        predefined_objects = [{"name": obj.split('.')[-1] if '.' in obj else obj} for obj in predefined_list_result if obj]
                    elif isinstance(predefined_list_result, dict) and "result" in predefined_list_result:
                        result_text = predefined_list_result["result"]
                        if isinstance(result_text, str):
                            for line in result_text.split('\n'):
                                line = line.strip()
                                if line and line.startswith("Имя: '"):
                                    start = len("Имя: '")
                                    name = line[start:].strip()
                                    if name:
                                        predefined_objects.append({"name": name})
                        elif isinstance(result_text, list):
                            predefined_objects = [{"name": obj.split('.')[-1] if '.' in obj else obj} for obj in result_text if obj]

                    if predefined_objects:
                        # Выбираем до 3 случайных предопределенных элементов для тестирования
                        num_to_test = min(len(predefined_objects), random.randint(1, 3))
                        selected_predefined = random.sample(predefined_objects, num_to_test)

                        for predefined_item in selected_predefined:
                            predefined_name = predefined_item.get("name", predefined_item.get("Name", "")) if isinstance(predefined_item, dict) else str(predefined_item)

                            if predefined_name:
                                predefined_data_result = await test_get_predefined_data(client, meta_type, object_name, predefined_name)
                                log_test(test_number, "get_predefined_data", {"metaType": meta_type, "name": object_name, "predefinedName": predefined_name}, predefined_data_result)

                                method_stats["get_predefined_data"]["total"] += 1
                                # Проверяем на ошибки в результате
                                if "error" in predefined_data_result:
                                    method_stats["get_predefined_data"]["errors"] += 1
                                elif isinstance(predefined_data_result, dict) and "result" in predefined_data_result and isinstance(predefined_data_result["result"], str) and any(keyword in predefined_data_result["result"].lower() for keyword in error_keywords):
                                    method_stats["get_predefined_data"]["errors"] += 1
                                elif (isinstance(predefined_data_result, list) and not predefined_data_result) or (isinstance(predefined_data_result, dict) and "result" in predefined_data_result and predefined_data_result["result"] == ""):
                                    method_stats["get_predefined_data"]["skipped"] += 1
                                else:
                                    method_stats["get_predefined_data"]["success"] += 1

    await client.close()

    # Вывод сводной статистики в MD таблице
    summary = "## Сводная статистика тестов\n\n"
    summary += "| Метод                  | Всего | Успешно | Ошибка | Пропущено | Процент успеха |\n"
    summary += "|------------------------|------:|--------:|-------:|----------:|---------------:|\n"

    total_all = 0
    total_success = 0
    total_errors = 0
    total_skipped = 0

    for method in methods:
        stats = method_stats[method]
        total = stats['total']
        success = stats['success']
        errors = stats['errors']
        skipped = stats['skipped']
        success_rate = (success / total * 100) if total > 0 else 0

        summary += f"| {method:<22} | {total:>5} | {success:>7} | {errors:>6} | {skipped:>9} | {success_rate:>13.1f}% |\n"

        total_all += total
        total_success += success
        total_errors += errors
        total_skipped += skipped

    overall_success_rate = (total_success / total_all * 100) if total_all > 0 else 0
    summary += f"| **Итого**              | **{total_all:>5}** | **{total_success:>7}** | **{total_errors:>6}** | **{total_skipped:>9}** | **{overall_success_rate:>13.1f}%** |\n\n"

    summary += "[INFO] Тестирование завершено.\n"
    print(summary)
    with open("testMCP.md", "a", encoding="utf-8") as f:
        f.write(summary)


def run_tests():
    asyncio.run(run_tests_async())


if __name__ == "__main__":
    run_tests()