# MCP-прокси сервер для 1С

## Что это такое

Представьте, что у вас есть мощный ИИ-помощник (типа Claude или Cursor), который может "разговаривать" с вашей базой 1С. Этот прокси-сервер как переводчик: он берет запросы от ИИ на понятном ему языке (MCP-протокол) и переводит их в команды, которые понимает 1С.

**Простыми словами:**
- ИИ спрашивает: "Какие справочники есть в конфигурации?"
- Прокси переводит это в JSON-RPC запрос к 1С
- 1С отвечает списком справочников
- Прокси переводит ответ обратно для ИИ

**Ключевые возможности:**
- **Два режима работы:** через файлы (stdio) для локальных программ и через интернет (HTTP) для веб-приложений
- **Безопасность:** поддержка OAuth2 авторизации - каждый пользователь работает под своими учетными данными
- **Быстродействие:** асинхронная обработка запросов, может работать с множеством пользователей одновременно
- **Универсальность:** работает со всеми типами MCP-клиентов

**Источник разработки:** https://github.com/vladimir-kharin/1c_mcp

*Отличия от оригинального репозитория: этот форк содержит дополнительные улучшения в документации, расширенное тестирование API и оптимизации производительности.*

## Быстрый старт

### Требования

- **Python 3.13** (рекомендуется) или 3.11+
- 1С:Предприятие 8.3.20+ с опубликованным HTTP-сервисом

### Установка

```bash
# Создание виртуального окружения
python -m venv venv

# Активация
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Установка зависимостей
pip install -r requirements.txt
```

### Выбор режима работы

#### Stdio режим

Для локальных MCP-клиентов (Claude Desktop, Cursor).

Настройки указываются в конфигурации клиента через переменные окружения.

**Минимальная конфигурация клиента:**
```json
{
  "mcpServers": {
    "1c-server": {
      "command": "python",
      "args": ["-m", "src.py_server"],
      "env": {
        "MCP_ONEC_URL": "http://localhost/base",
        "MCP_ONEC_USERNAME": "admin",
        "MCP_ONEC_PASSWORD": "password"
      }
    }
  }
}
```

Примеры конфигураций для разных клиентов: [`../../mcp_client_settings/`](../../mcp_client_settings/)

#### HTTP режим

Для веб-приложений и множественных клиентов.

Настройки указываются в файле `.env` в корне проекта или через переменные окружения:

```bash
# Скопируйте пример
copy src\py_server\env.example .env  # Windows
cp src/py_server/env.example .env    # Linux/Mac
```

**Минимальный .env:**
```ini
MCP_ONEC_URL=http://localhost/base
MCP_ONEC_USERNAME=admin
MCP_ONEC_PASSWORD=password
```

**Запуск:**
```bash
python -m src.py_server http --port 8000
```

## Режимы работы

### Stdio режим

- Общение через stdin/stdout
- Используется локальными MCP-клиентами
- Логи идут в stderr

### HTTP режим

**Endpoints:**
- `/mcp/` - Streamable HTTP транспорт (основной)
- `/sse` - SSE транспорт (устаревший, но поддерживается)
- `/health` - проверка состояния
- `/info` - информация о сервере
- `/` - список endpoints

**Проверка работы:**
```bash
curl http://localhost:8000/health
```

## Режимы авторизации

### Без OAuth2 (по умолчанию)

```bash
MCP_AUTH_MODE=none  # по умолчанию
```

**Поведение:**
- Все обращения к 1С выполняются от одного пользователя
- Креденшилы задаются в конфигурации: `MCP_ONEC_USERNAME` и `MCP_ONEC_PASSWORD`
- Используется Basic Auth для всех запросов к 1С

### С OAuth2

```bash
MCP_AUTH_MODE=oauth2
MCP_PUBLIC_URL=http://your-server:8000
```

**Поведение:**
- Каждый клиент авторизуется своими креденшилами 1С
- Креденшилы передаются через OAuth2 flow
- `MCP_ONEC_USERNAME` и `MCP_ONEC_PASSWORD` не используются (опциональны для резервного подключения)

**Поддерживаемые OAuth2 flows:**
- **Password Grant** - передача username/password напрямую
- **Authorization Code + PKCE** - авторизация через HTML-форму
- **Dynamic Client Registration** - автоматическая регистрация клиентов

**Дополнительные endpoints (для OAuth2):**
- `/.well-known/oauth-protected-resource` - Protected Resource Metadata
- `/.well-known/oauth-authorization-server` - Authorization Server Metadata
- `/register` - регистрация клиентов
- `/authorize` - HTML форма авторизации
- `/token` - получение/обновление токенов

Детали OAuth2: см. раздел "Примеры использования" и `agents.md`

## Конфигурация

Все настройки задаются через переменные окружения с префиксом `MCP_` или через CLI аргументы.

### Подключение к 1С

| Переменная | Описание | По умолчанию | Обязательная |
|------------|----------|--------------|--------------|
| `MCP_ONEC_URL` | URL базы 1С | - | ✅ Всегда |
| `MCP_ONEC_USERNAME` | Имя пользователя | - | ✅ При `AUTH_MODE=none` |
| `MCP_ONEC_PASSWORD` | Пароль | - | ✅ При `AUTH_MODE=none` |
| `MCP_ONEC_SERVICE_ROOT` | Корень HTTP-сервиса | `mcp` | ❌ |

### HTTP-сервер

| Переменная | Описание | По умолчанию | Обязательная |
|------------|----------|--------------|--------------|
| `MCP_HOST` | Хост для прослушивания | `127.0.0.1` | ❌ |
| `MCP_PORT` | Порт | `8000` | ❌ |
| `MCP_CORS_ORIGINS` | CORS origins (JSON array) | `["*"]` | ❌ |

### MCP

| Переменная | Описание | По умолчанию | Обязательная |
|------------|----------|--------------|--------------|
| `MCP_SERVER_NAME` | Имя сервера | `1C Configuration Data Tools` | ❌ |
| `MCP_SERVER_VERSION` | Версия | `1.0.0` | ❌ |
| `MCP_LOG_LEVEL` | Уровень логирования | `INFO` | ❌ |

Допустимые уровни: `DEBUG`, `INFO`, `WARNING`, `ERROR`

### OAuth2

| Переменная | Описание | По умолчанию | Обязательная |
|------------|----------|--------------|--------------|
| `MCP_AUTH_MODE` | Режим: `none` или `oauth2` | `none` | ❌ |
| `MCP_PUBLIC_URL` | Публичный URL прокси | (определяется из запроса) | ✅ При `AUTH_MODE=oauth2` для HTTP режима |
| `MCP_OAUTH2_CODE_TTL` | TTL authorization code (сек) | `120` | ❌ |
| `MCP_OAUTH2_ACCESS_TTL` | TTL access token (сек) | `3600` | ❌ |
| `MCP_OAUTH2_REFRESH_TTL` | TTL refresh token (сек) | `1209600` | ❌ |

### CLI аргументы

Переопределяют переменные окружения:

```bash
python -m src.py_server http \
  --onec-url http://server/base \
  --onec-username admin \
  --onec-password secret \
  --auth-mode oauth2 \
  --public-url http://proxy:8000 \
  --port 8000 \
  --log-level DEBUG
```

Полный список аргументов:
```bash
python -m src.py_server --help
```

## Архитектура

### Общая схема

```
┌─────────────────┐
│   MCP Client    │  (Claude Desktop, Cursor)
│  (stdio/HTTP)   │
└────────┬────────┘
         │ MCP Protocol
         ↓
┌────────────────────┐
│  Python Proxy      │
│  - mcp_server      │  Проксирование MCP → JSON-RPC
│  - http_server     │  HTTP/SSE транспорты + OAuth2
│  - stdio_server    │  Stdio транспорт
│  - onec_client     │  HTTP-клиент для 1С
└────────┬───────────┘
         │ JSON-RPC over HTTP
         │ Basic Auth (username:password)
         ↓
┌────────────────────┐
│  1C HTTP Service   │  /hs/mcp/rpc
│  (расширение)      │
└────────────────────┘
```

### Модули

- **`main.py`** - CLI парсинг и запуск
- **`config.py`** - конфигурация через Pydantic
- **`mcp_server.py`** - ядро MCP-сервера (проксирование)
- **`onec_client.py`** - асинхронный HTTP-клиент для 1С
- **`http_server.py`** - HTTP/SSE транспорт + OAuth2
- **`stdio_server.py`** - stdio транспорт
- **`auth/oauth2.py`** - OAuth2 авторизация (Store + Service)

### Проксирование MCP-примитивов

Все MCP-запросы транслируются в JSON-RPC к 1С:

**Tools (инструменты):**
- `tools/list` → список доступных инструментов
- `tools/call` → вызов инструмента с аргументами

**Resources (ресурсы):**
- `resources/list` → список доступных ресурсов
- `resources/read` → чтение содержимого ресурса

**Prompts (промпты):**
- `prompts/list` → список доступных промптов
- `prompts/get` → получение промпта с параметрами

## Примеры использования

### Проверка подключения к 1С

```bash
# HTTP режим
curl http://localhost:8000/health

# Ожидаемый ответ
{
  "status": "healthy",
  "onec_connection": "ok",
  "auth": {"mode": "none"}
}
```

### Информация о сервере

```bash
curl http://localhost:8000/info
```

### OAuth2: Password Grant (упрощённый)

```bash
# 1. Получить токен
curl -X POST http://localhost:8000/token \
  -d "grant_type=password" \
  -d "username=admin" \
  -d "password=secret"

# Ответ:
# {
#   "access_token": "simple_...",
#   "token_type": "Bearer",
#   "expires_in": 86400,
#   "scope": "mcp"
# }

# 2. Использовать токен для доступа
curl http://localhost:8000/mcp/ \
  -H "Authorization: Bearer <access_token>"
```

### OAuth2: Authorization Code + PKCE (стандартный)

```bash
# 1. Discovery
curl http://localhost:8000/.well-known/oauth-authorization-server

# 2. Регистрация клиента
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"client_name": "My Client"}'

# 3. Авторизация (в браузере)
# http://localhost:8000/authorize?response_type=code&client_id=mcp-public-client&...

# 4. Обмен кода на токены
curl -X POST http://localhost:8000/token \
  -d "grant_type=authorization_code" \
  -d "code=<authorization_code>" \
  -d "redirect_uri=http://localhost/callback" \
  -d "code_verifier=<code_verifier>"
```

### Логирование

```bash
# DEBUG режим для отладки
python -m main http --log-level DEBUG

# Логи показывают:
# - Все HTTP запросы к 1С
# - OAuth2 операции (генерация/валидация токенов)
# - MCP операции (tools/resources/prompts)
# - Ошибки подключения
```

## Интеграция с 1С

Прокси ожидает HTTP-сервис в 1С по адресу:
```
{MCP_ONEC_URL}/hs/{MCP_ONEC_SERVICE_ROOT}/
```

Например: `http://localhost/base/hs/mcp/`

### Endpoints 1С

1. **`GET /health`**
   - Проверка доступности сервиса
   - Ответ: `{"status": "ok"}`
   - Используется для валидации креденшилов в OAuth2

2. **`POST /rpc`**
   - JSON-RPC endpoint для всех MCP-операций
   - Content-Type: `application/json`
   - Basic Auth: `username:password`

### Формат JSON-RPC запроса

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

### Формат JSON-RPC ответа

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "get_metadata",
        "description": "Получить метаданные объекта",
        "inputSchema": {...}
      }
    ]
  }
}
```

Подробности реализации 1С-стороны: `../1c_ext/agents.md`

## API методы MCP сервера 1С

MCP-сервер 1С предоставляет инструменты для работы с метаданными конфигурации 1С:Предприятие. Все методы доступны через MCP-протокол и могут использоваться AI-агентами (Claude, Cursor) для анализа и генерации кода.

### list_metadata_objects

**Назначение:** Получает список объектов метаданных указанного типа из конфигурации 1С.

**Возможности:**
- Фильтрация по типу метаданных (справочники, документы, регистры и т.д.)
- Поиск по маске имени или синонима объекта
- Ограничение количества результатов
- Поддержка всех типов метаданных 1С

**Параметры:**
- `metaType` (обязательный): Тип объекта метаданных
  - `Catalogs` - Справочники
  - `Documents` - Документы
  - `InformationRegisters` - Регистры сведений
  - `AccumulationRegisters` - Регистры накопления
  - `AccountingRegisters` - Регистры бухгалтерии
  - `CalculationRegisters` - Регистры расчета
  - И другие типы (всего 40+ типов)
- `nameMask` (опциональный): Маска для поиска по имени или синониму
- `maxItems` (опциональный): Максимальное количество возвращаемых объектов (по умолчанию 100)

**Пример использования:**
```json
{
  "name": "list_metadata_objects",
  "arguments": {
    "metaType": "Catalogs",
    "nameMask": "Номенклатура",
    "maxItems": 10
  }
}
```

**Результат:** Список найденных объектов с их именами и описаниями.

### get_metadata_structure

**Назначение:** Получает подробную структуру метаданных объекта (реквизиты, табличные части, измерения, ресурсы).

**Возможности:**
- Анализ структуры объектов конфигурации
- Получение списка реквизитов с типами данных
- Информация о табличных частях и их составе
- Детали измерений и ресурсов для регистров
- Поддержка основных типов объектов 1С

**Параметры:**
- `metaType` (обязательный): Тип объекта метаданных (см. список выше)
- `name` (обязательный): Точное имя объекта (без учета регистра)

**Поддерживаемые типы:**
- Catalogs, Documents, InformationRegisters, AccumulationRegisters
- AccountingRegisters, CalculationRegisters, Reports, DataProcessors
- ChartsOfCharacteristicTypes, ChartsOfAccounts, ChartsOfCalculationTypes
- BusinessProcesses, Tasks, ExchangePlans

**Пример использования:**
```json
{
  "name": "get_metadata_structure",
  "arguments": {
    "metaType": "Catalogs",
    "name": "Номенклатура"
  }
}
```

**Результат:** Полная структура объекта с описанием всех элементов.

### list_predefined_data

**Назначение:** Получает список предопределенных элементов объекта метаданных.

**Возможности:**
- Просмотр предопределенных элементов справочников и планов счетов
- Фильтрация по маске имени, наименования или кода
- Ограничение количества результатов
- Информация о системных предопределенных данных

**Параметры:**
- `metaType` (обязательный): Тип объекта (только для поддерживающих предопределенные данные)
- `name` (обязательный): Имя объекта
- `predefinedMask` (опциональный): Маска для поиска по имени/наименованию/коду
- `maxItems` (опциональный): Максимальное количество элементов (по умолчанию 1000)

**Поддерживаемые типы:**
- Catalogs (Справочники)
- ChartsOfCharacteristicTypes (Планы видов характеристик)
- ChartsOfAccounts (Планы счетов)
- ChartsOfCalculationTypes (Планы видов расчета)

**Пример использования:**
```json
{
  "name": "list_predefined_data",
  "arguments": {
    "metaType": "Catalogs",
    "name": "Номенклатура",
    "predefinedMask": "Услуга",
    "maxItems": 50
  }
}
```

**Результат:** Список предопределенных элементов с их свойствами.

### get_predefined_data

**Назначение:** Получает детальную информацию о конкретном предопределенном элементе.

**Возможности:**
- Получение значений стандартных реквизитов предопределенного элемента
- Просмотр фиксированных табличных частей
- Анализ системных предопределенных данных
- Использование в коде 1С для ссылки на предопределенные элементы

**Параметры:**
- `metaType` (обязательный): Тип объекта (см. поддерживаемые типы выше)
- `name` (обязательный): Имя объекта
- `predefinedName` (обязательный): Точное имя предопределенного элемента

**Пример использования:**
```json
{
  "name": "get_predefined_data",
  "arguments": {
    "metaType": "Catalogs",
    "name": "Номенклатура",
    "predefinedName": "Услуга"
  }
}
```

**Результат:** Подробная информация о предопределенном элементе.

### Возможности при работе с MCP сервером 1С

**Для разработчиков 1С:**
- Автоматический анализ структуры конфигурации
- Генерация кода на основе метаданных
- Проверка корректности ссылок на объекты
- Создание запросов и отчетов

**Для AI-агентов:**
- Контекстно-зависимая генерация кода
- Понимание бизнес-логики конфигурации
- Автоматическое документирование
- Помощь в рефакторинге и оптимизации

**Интеграция с инструментами:**
- Claude Desktop - естественный язык для запросов к 1С
- Cursor - IDE с поддержкой MCP для разработки 1С
- Протестировано на KILO Code
- Другие MCP-клиенты для автоматизации работы с 1С

## Тестирование API

Для тестирования API методов MCP сервера 1С используется скрипт `testMCP_grok_plus_2.py`. Этот скрипт выполняет автоматическое тестирование всех основных методов с различными параметрами.

### Запуск тестирования

```bash
# Установка переменных окружения (опционально)
export MCP_HOST=127.0.0.1
export MCP_PORT=8000
export MCP_AUTH_MODE=none  # или oauth2
export MCP_ACCESS_TOKEN=your_token

# Запуск тестов
python testMCP_grok_plus_2.py
```

### Что тестирует скрипт

1. **list_metadata_objects** - получение списков объектов разных типов
2. **get_metadata_structure** - анализ структуры объектов
3. **list_predefined_data** - получение предопределенных элементов
4. **get_predefined_data** - детальная информация о предопределенных данных

### Результаты тестирования

Скрипт создает файл `testMCP.md` с подробными результатами каждого теста и сводной статистикой:

- Общее количество тестов
- Количество успешных/неудачных вызовов
- Процент успешности по каждому методу
- Детальные логи ошибок

### Пример запуска тестов

```bash
python testMCP_grok_plus_2.py
```

Вывод:
```
[INFO] Подключено к MCP серверу: http://127.0.0.1:8000
Тест #1
API: list_metadata_objects
Параметры: {"metaType": "Catalogs", "nameMask": "", "maxItems": 10}
Результат: ["Справочник.Номенклатура", "Справочник.Контрагенты", ...]
...
## Сводная статистика тестов

| Метод                  | Всего | Успешно | Ошибка | Пропущено | Процент успеха |
|------------------------|------:|--------:|-------:|----------:|---------------:|
| list_metadata_objects  |   200 |     180 |     15 |        5 |          90.0% |
| get_metadata_structure |   180 |     175 |      3 |        2 |          97.2% |
| list_predefined_data   |   140 |     130 |      8 |        2 |          92.9% |
| get_predefined_data    |   120 |     115 |      4 |        1 |          95.8% |
| Итого                  |   640 |     600 |     30 |       10 |          93.8% |
```

## Устранение неполадок (Troubleshooting)

### Проблема: "Не удается подключиться к 1С"

**Симптомы:**
- Ошибка подключения при запуске сервера
- HTTP 500 ошибки в логах

**Решения:**
1. Проверьте URL базы 1С: `MCP_ONEC_URL=http://server/base`
2. Убедитесь, что HTTP-сервис 1С опубликован и доступен
3. Проверьте учетные данные: `MCP_ONEC_USERNAME` и `MCP_ONEC_PASSWORD`
4. Проверьте логи сервера с уровнем DEBUG

### Проблема: "OAuth2 авторизация не работает"

**Симптомы:**
- 401 Unauthorized при попытке доступа
- Проблемы с токенами

**Решения:**
1. Убедитесь, что `MCP_AUTH_MODE=oauth2`
2. Проверьте `MCP_PUBLIC_URL` - должен быть доступен извне
3. Для Password Grant: убедитесь, что учетные данные верны
4. Для Authorization Code: проверьте PKCE параметры

### Проблема: "MCP-клиент не видит инструменты"

**Симптомы:**
- В Claude/Cursor нет доступных инструментов 1С

**Решения:**
1. Проверьте конфигурацию MCP-клиента
2. Убедитесь, что сервер запущен и доступен
3. Проверьте логи на ошибки инициализации
4. Для stdio режима: проверьте переменные окружения

### Проблема: "Медленная работа API"

**Симптомы:**
- Долгое время отклика на запросы

**Решения:**
1. Увеличьте таймауты в конфигурации
2. Проверьте производительность базы 1С
3. Оптимизируйте запросы (меньше `maxItems`)
4. Рассмотрите кэширование для часто используемых данных

### Полезные команды для диагностики

```bash
# Проверка доступности сервера
curl http://localhost:8000/health

# Проверка информации о сервере
curl http://localhost:8000/info

# Тестирование с логами
python -m src.py_server http --log-level DEBUG

# Проверка конфигурации
python -c "from config import get_config; print(get_config())"
```

## Примеры использования в коде

### Python клиент для тестирования

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    # Подключение к MCP серверу
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "src.py_server"],
        env={"MCP_ONEC_URL": "http://localhost/base", ...}
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Получение списка справочников
            result = await session.call_tool("list_metadata_objects", {
                "metaType": "Catalogs",
                "maxItems": 10
            })
            print("Справочники:", result.content[0].text)

asyncio.run(main())
```

### JavaScript/TypeScript клиент

```javascript
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";

// Подключение к HTTP MCP серверу
const transport = new SSEClientTransport(new URL("http://localhost:8000/sse"));
const client = new Client({ name: "test-client", version: "1.0.0" });

await client.connect(transport);
await client.initialize();

// Вызов инструмента
const result = await client.callTool({
  name: "get_metadata_structure",
  arguments: { metaType: "Catalogs", name: "Номенклатура" }
});

console.log("Структура номенклатуры:", result.content[0].text);
```

## Архитектура проекта

```
src/py_server/
├── main.py                 # Точка входа и CLI
├── config.py              # Конфигурация (Pydantic)
├── mcp_server.py         # Ядро MCP сервера
├── onec_client.py         # HTTP клиент для 1С
├── http_server.py        # HTTP/SSE транспорт + OAuth2
├── stdio_server.py       # Stdio транспорт
├── auth/
│   ├── __init__.py
│   └── oauth2.py          # OAuth2 логика
├── requirements.txt       # Зависимости Python
├── env.example           # Пример конфигурации
├── testMCP_grok_plus_2.py # Скрипт тестирования API
└── README.md             # Эта документация
```

## Документация

### Для разработчиков

- **`agents.md`** - полная техническая документация
  - Архитектура и модули
  - Протоколы взаимодействия
  - OAuth2 авторизация
  - Точки расширения

### Конфигурация

- **`env.example`** - пример файла конфигурации
- **`config.py`** - описание всех параметров

### Тестирование

- **`testMCP_grok_plus_2.py`** - автоматическое тестирование API
- **`testMCP.md`** - результаты тестов (генерируется автоматически)

---

## Лицензия

**MIT License**

Проект активно развивается. Вопросы, предложения и баг-репорты приветствуются через Issues на GitHub.

**Контакты:**
- Репозиторий: https://github.com/vladimir-kharin/1c_mcp
- Автор: Владимир Харин
