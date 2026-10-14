# TÀI LIỆU KIẾN TRÚC & HƯỚNG DẪN HỌC TẬP CHUYÊN SÂU
# PHÂN BIỆT FUNCTION CALLING VÀ MODEL CONTEXT PROTOCOL (MCP)

> Tài liệu này ghi lại toàn bộ kiến trúc, lý thuyết cốt lõi, phương pháp giải quyết và **nhật ký thực nghiệm chi tiết (Terminal Logs & Execution Traces)** từ các lần chạy thực tế trong repository — giúp bạn nắm bắt trọn vẹn từ bản chất đến ứng dụng Production của AI Agent.

---

## 1. Bức tranh tổng thể: Bài toán tích hợp công cụ cho AI

### 1.1. Giới hạn tự nhiên của Mô hình Ngôn ngữ Lớn (LLM)
Mô hình ngôn ngữ (như GPT-4, Gemini 2.5 Flash, Claude 3.5 Sonnet) bản chất là một **mạng nơ-ron dự đoán từ tiếp theo**. Chúng có khả năng lập luận, suy diễn ngôn ngữ vượt trội nhưng lại có 3 "điểm mù" chí mạng:
1. **Không có dữ liệu thời gian thực**: Kiến thức dừng lại ở mốc cắt huấn luyện (knowledge cutoff).
2. **Không có quyền truy cập hệ thống**: Không thể tự đọc file, truy vấn cơ sở dữ liệu nội bộ, gọi REST API.
3. **Không thể thực thi hành động**: Không thể tự gửi email, cập nhật vé Jira, hay thay đổi trạng thái thế giới thực.

### 1.2. Sự tiến hóa của các giải pháp kết nối công cụ

```
Giai đoạn 1: Prompt Injection (Truyền toàn bộ context vào prompt)
  └── Hạn chế: Tốn token, dễ bị hallucination, dữ liệu tĩnh.

Giai đoạn 2: Function Calling thuần (Cung cấp JSON Schema thủ công)
  └── Tiến bộ: LLM biết chọn hàm và sinh tham số JSON có cấu trúc chuẩn.
  └── Hạn chế: Schema và logic thực thi gắn chặt (tightly coupled) vào từng app.

Giai đoạn 3: Model Context Protocol - MCP (Chuẩn hóa giao thức cắm rút)
  └── Đột phá: Tách biệt hoàn toàn AI Client và Tool Server. Tool tự công bố (self-describing).

Giai đoạn 4: Agentic Frameworks + MCP (Google ADK, LangChain, Claude Code)
  └── Toàn diện: Tự động hóa toàn bộ vòng lặp khám phá tool, chọn tool và gọi tool.
```

---

## 2. Bản chất cốt lõi: Function Calling vs MCP

Một hiểu lầm rất phổ biến là: *"MCP ra đời để thay thế Function Calling"*. Thực tế hoàn toàn không phải vậy.

| Tiêu chí | Function Calling | Model Context Protocol (MCP) |
|---|---|---|
| **Bản chất** | **Năng lực của mô hình (Model Capability)** | **Giao thức truyền thông (Communication Protocol)** |
| **Vai trò** | LLM đọc schema và sinh ra JSON gọi hàm | Quy chuẩn hóa cách kết nối, khám phá và gọi tool giữa các tiến trình/máy chủ |
| **Ai định nghĩa Schema?** | Lập trình viên viết tay trong ứng dụng | Server tự sinh từ code (Python type hints, docstring) |
| **Nơi thực thi tool** | Chạy ngay trong app của bạn | Chạy độc lập trên MCP Server (local hoặc remote) |
| **Tái sử dụng** | Rất khó (phải copy code schema & hàm sang app khác) | Viết 1 lần, mọi AI Client (Claude, Cursor, ADK) dùng chung |
| **Phương thức giao tiếp** | In-memory function call | `stdio` (tiến trình con) hoặc `Streamable HTTP / SSE` (mạng) |

### Mối quan hệ tương hỗ:
> **MCP sử dụng Function Calling làm nền tảng bên dưới.**  
> - MCP Server cung cấp danh sách công cụ và schema chuẩn.  
> - MCP Client đưa schema này cho LLM.  
> - LLM sử dụng **Function Calling** để quyết định gọi tool nào.  
> - MCP Client nhận quyết định đó và truyền lệnh thực thi sang MCP Server qua **Giao thức MCP**.

```
┌────────────────────────────────────────────────────────────────────────┐
│                               AI CLIENT                                │
│                                                                        │
│   User Prompt ──► [ LLM: Gemini / Claude ]                             │
│                          │                                             │
│                          │ (Function Calling: quyết định gọi tool)     │
│                          ▼                                             │
│                 [ MCP Client Session ]                                 │
└───────────────────────────┬────────────────────────────────────────────┘
                            │
                            │  Giao thức MCP (stdio hoặc Streamable HTTP)
                            │  1. list_tools()  -> Khám phá công cụ
                            │  2. call_tool()   -> Thực thi công cụ
                            ▼
┌────────────────────────────────────────────────────────────────────────┐
│                              MCP SERVER                                │
│                                                                        │
│   [ Tool Registry / Dispatcher ]                                       │
│          │                                                             │
│          ├── get_weather(city) ────────► Gọi API thời tiết              │
│          ├── query_database(sql) ──────► Truy vấn PostgreSQL           │
│          └── send_email(...) ──────────► Gửi email thông báo           │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Mổ xẻ Kiến trúc & Phương pháp giải quyết từng Module

---

### Module 01: Function Calling thuần (`01-function-calling`)

#### Bài toán:
Làm thế nào để Gemini biết thông tin thời tiết của Hà Nội và Đà Nẵng khi trong dữ liệu huấn luyện không có thời tiết ngày hôm nay?

#### Phương pháp giải quyết:
1. **App tự khai báo Schema thủ công**:
   ```python
   get_weather_declaration = types.FunctionDeclaration(
       name="get_weather",
       description="Lấy thời tiết hiện tại của một thành phố",
       parameters=types.Schema(
           type=types.Type.OBJECT,
           properties={"city": types.Schema(type=types.Type.STRING, description="Tên thành phố")},
           required=["city"],
       ),
   )
   ```
2. **Gửi prompt + schema cho model**: Model không trả lời ngay văn bản, mà trả về cấu trúc: `resp.function_calls = [get_weather(city='Hà Nội'), get_weather(city='Đà Nẵng')]`.
3. **App tự điều phối vòng lặp (`while resp.function_calls`)**:
   - App đọc tham số `fc.args`.
   - App tự gọi hàm Python cục bộ `get_weather(**fc.args)`.
   - App đóng gói kết quả vào `types.Part.from_function_response` và gửi ngược lại cho LLM để LLM tổng hợp câu trả lời tự nhiên bằng tiếng Việt.

---

### Module 02: MCP Cơ bản qua stdio (`02-mcp-basics`)

#### Bài toán:
Làm thế nào để logic lấy thời tiết trở thành một dịch vụ độc lập, tự mô tả bản thân để bất kỳ AI nào cắm vào cũng dùng được ngay?

#### Phương pháp giải quyết:
Tách biệt ứng dụng thành 2 thành phần độc lập: **Server** và **Client**.

1. **Server (`weather_server.py`)**:
   ```python
   from mcp.server.mcpserver import MCPServer
   mcp = MCPServer("weather")

   @mcp.tool()
   def get_weather(city: str) -> str:
       """Lấy thời tiết hiện tại của một thành phố."""
       return f"{city}: 29°C, trời mưa"
   ```
   *Điểm sáng*: Nhờ decorator `@mcp.tool()`, MCP SDK tự động dịch type hint `city: str` và docstring thành JSON Schema chuẩn. Lập trình viên không cần viết một dòng schema thủ công nào!

2. **Client (`weather_client.py`)**:
   - Sử dụng kênh truyền `stdio` (Standard Input / Output): Client spawn server thành một tiến trình con (subprocess).
   - **Giai đoạn Khám phá (Discovery)**: Gọi `session.list_tools()` để hỏi server: *"Bạn hỗ trợ những công cụ nào?"*.
   - **Giai đoạn Thực thi (Execution)**: Gọi `session.call_tool("get_weather", {"city": "Hanoi"})`. Server thực thi và trả kết quả về qua luồng stdout/stdin.

---

### Module 03: Đưa MCP vào Môi trường Production (`03-production`)

Ở môi trường doanh nghiệp (Production), MCP chạy stdio trên máy cá nhân là chưa đủ. Module 03 giải quyết **3 bài toán sống còn**:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Production MCP Architecture                  │
│                                                                 │
│   1. Security (Bảo mật)          2. Discovery (Khám phá)        │
│   • Streamable HTTP transport    • Tool-centric Registry        │
│   • Bearer Token Verifier        • Semantic search & tags       │
│   • Phân quyền theo Scopes       • Chọn version tốt nhất        │
│                                                                 │
│   3. Versioning (Tương thích)                                  │
│   • Không break client cũ (v1 & v2 chạy song song)             │
│   • Resource metadata: server://info                           │
│   • Migration guidance rõ ràng                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.1. Authentication & Authorization (`auth_server.py`, `auth_client.py`)
- **Vấn đề**: Server phục vụ qua mạng HTTP cho nhiều microservices khác nhau. Cần kiểm soát ai được phép gọi tool.
- **Giải pháp**:
  - Dùng transport `streamable-http`.
  - Cấu hình `AuthSettings` và kế thừa `TokenVerifier`:
    ```python
    class StaticTokenVerifier(TokenVerifier):
        async def verify_token(self, token: str) -> AccessToken | None:
            if token in VALID_TOKENS:
                return AccessToken(token=token, client_id=VALID_TOKENS[token], scopes=["weather:read"])
            return None
    ```
  - Khi client kết nối, bắt buộc gửi header: `Authorization: Bearer <token>`.
  - Nếu thiếu token -> trả về HTTP 401; nếu token không hợp lệ -> trả về HTTP 403.
  - **Lợi ích**: Logic nghiệp vụ của Tool hoàn toàn sạch sẽ, không bị trộn lẫn với logic xác thực. Tầng transport của MCP SDK xử lý toàn bộ auth.

#### 3.2. Tool Registry & Discovery (`registry_client.py`, `registry.json`)
- **Vấn đề**: Doanh nghiệp có hàng trăm tool trên hàng chục server khác nhau. Agent không thể hard-code URL và tên từng tool.
- **Giải pháp**: Thiết kế danh mục tập trung **Tool Registry** theo hướng **Tool-centric**:
  - Đơn vị tìm kiếm là **năng lực của Tool** (dựa vào `tags`, `keywords`, `description`), không phải tên server.
  - Agent cần thời tiết: Tìm kiếm `tag="weather"`. Registry trả về cả `get_weather (v1.0.0)` và `get_weather_v2 (v2.0.0)`.
  - Bộ so sánh phiên bản (`packaging.version`) tự động phân tích và chọn `v2.0.0` (phiên bản mới nhất, không bị đánh dấu deprecated).
  - Client tự động đọc thông tin kết nối của server tương ứng và mở kết nối tới đúng địa chỉ.

#### 3.3. Versioning & Backward Compatibility (`versioned_server.py`, `versioned_client.py`)
- **Vấn đề**: Nâng cấp API từ v1 (trả chuỗi text) lên v2 (trả JSON chi tiết có dự báo 3 ngày). Nếu sửa trực tiếp tool cũ, các client thế hệ cũ đang hoạt động trên hệ thống sẽ lập tức bị lỗi (breaking change).
- **Giải pháp kết hợp 3 kỹ thuật**:
  1. **Công bố song song (Side-by-side Tools)**: Giữ nguyên `get_weather` cho client cũ; tạo thêm `get_weather_v2` cho client mới.
  2. **Tham số tùy chọn (Optional Parameters with Defaults)**: Các trường mới như `include_forecast=False`, `units="celsius"` luôn có giá trị mặc định.
  3. **Resource Metadata (`server://info`)**: Server cung cấp một MCP Resource đặc biệt trả về metadata cấu trúc JSON thông báo:
     - Phiên bản hiện tại của server (`2.0.0`).
     - Danh sách công cụ đã deprecated: `["get_weather"]`.
     - Hướng dẫn chuyển đổi (migration guide) để client thông minh tự nhận biết và nâng cấp.

---

### Module 04: Lab Thực hành Google ADK + MCP Server (`04-lab`)

#### Bài toán:
Xây dựng một trợ lý AI thông minh hoàn chỉnh có giao diện Web chat, có khả năng tra cứu thời tiết thời gian thực qua giao thức MCP.

#### Tại sao lại dùng Google ADK (Agent Development Kit)?
Ở Module 01, ta phải tự viết vòng lặp `while resp.function_calls:` và xử lý thủ công từng bước gọi hàm.
Google ADK đóng vai trò là một **MCP Client cấp cao**:
1. **Tự động bắt tay (Handshake)** với MCP Server qua `StreamableHTTPConnectionParams(url="http://localhost:8085/mcp")`.
2. **Tự động khám phá công cụ** qua `McpToolset`.
3. **Tự động kết nối với Gemini 2.5 Flash**: Chuyển đổi toàn bộ tool từ MCP sang định dạng hiểu được của Gemini.
4. **Tự động điều phối vòng lặp Function Calling**: Người dùng hỏi -> Gemini chọn tool -> ADK gọi MCP Server qua HTTP -> Nhận kết quả -> Trả về cho Gemini tổng hợp -> Trả lời người dùng.
5. **Cung cấp sẵn Web Chat UI (`adk web`)**: Giao diện chat trực quan tại `http://localhost:8000`.

---

## 4. Nhật ký Thực nghiệm & Phân tích Chi tiết Từng Lần Chạy (Execution Traces)

Dưới đây là **chứng cứ thực nghiệm nguyên bản** được ghi lại từ quá trình chạy thực tế các script trong repository:

### 4.1. Thực nghiệm Module 01: Function Calling thuần

**Lệnh thực thi:**
```bash
cd 01-function-calling
../.venv/bin/python weather_function_calling.py
```

**Console Output thực tế:**
```text
Both GOOGLE_API_KEY and GEMINI_API_KEY are set. Using GOOGLE_API_KEY.
User: Thời tiết Hà Nội và Đà Nẵng hôm nay thế nào?

  [model yêu cầu] get_weather({'city': 'Hà Nội'})
  [app thực thi]  -> {"city": "Hà Nội", "nhiệt_độ": "29°C", "thời_tiết": "trời mưa nhẹ", "độ_ẩm": "82%", "gió": {"hướng": "Đông Nam", "tốc_độ": "12 km/h"}}
  [model yêu cầu] get_weather({'city': 'Đà Nẵng'})
  [app thực thi]  -> {"city": "Đà Nẵng", "nhiệt_độ": "30°C", "thời_tiết": "nhiều mây", "độ_ẩm": "78%", "gió": {"hướng": "Đông", "tốc_độ": "10 km/h"}}

Trả lời: Chào bạn! Dưới đây là thông tin thời tiết hôm nay cho Hà Nội và Đà Nẵng:

**Hà Nội** 🌧️:
*   Nhiệt độ: 29°C
*   Thời tiết: Trời mưa nhẹ
*   Độ ẩm: 82%
*   Gió: Đông Nam, 12 km/h

👉 Lời khuyên: Hôm nay Hà Nội có mưa nhẹ, bạn nhớ mang theo ô hoặc áo mưa khi ra ngoài nhé! Độ ẩm cao có thể hơi oi bức một chút.

**Đà Nẵng** ☁️:
*   Nhiệt độ: 30°C
*   Thời tiết: Nhiều mây
*   Độ ẩm: 78%
*   Gió: Đông, 10 km/h

👉 Lời khuyên: Đà Nẵng hôm nay nhiều mây nhưng trời vẫn khá ấm áp. Bạn có thể mặc trang phục thoáng mát và đừng quên uống đủ nước nhé!

Chúc bạn một ngày tốt lành! 😊
```

**Phân tích dưới góc nhìn hệ thống:**
1. **Lần gọi API 1**: Client gửi câu hỏi *"Thời tiết Hà Nội và Đà Nẵng hôm nay thế nào?"* kèm schema `get_weather`. Gemini không trả lời văn bản mà trả về 2 Function Calls: một cho `Hà Nội`, một cho `Đà Nẵng`.
2. **Thực thi trong App**: App bắt được 2 lệnh gọi này, chạy hàm Python nội bộ và in ra 2 dòng `[app thực thi]`.
3. **Lần gọi API 2**: App đóng gói kết quả vào `types.Content(role="user", parts=function_responses)` gửi ngược lại cho model. Model nhận dữ liệu thật và tổng hợp câu trả lời tiếng Việt thân thiện kèm emoji.

---

### 4.2. Thực nghiệm Module 02: MCP Cơ bản qua stdio

**Lệnh thực thi:**
```bash
cd 02-mcp-basics
../.venv/bin/python weather_client.py
```

**Console Output thực tế:**
```text
Tools server cung cấp:
  - get_weather: Lấy thời tiết hiện tại của một thành phố.

call_tool get_weather(city='Hanoi'):
  -> Hanoi: 29°C, trời mưa

call_tool get_weather(city='Danang'):
  -> Danang: 30°C, nhiều mây

call_tool get_weather(city='Haiphong'):
  -> Haiphong: 33°C, mưa rào
```

**Phân tích dưới góc nhìn hệ thống:**
* Client không hề import hàm `get_weather` từ file server.
* Client chỉ giao tiếp qua luồng chuẩn `sys.stdin`/`sys.stdout` của tiến trình con `python weather_server.py`.
* Bản tin JSON-RPC trao đổi ngầm:
  * Handshake: `{"method": "initialize", "params": {"protocolVersion": "2024-11-05"}}`
  * Khám phá: `{"method": "tools/list"}` -> Nhận lại mảng JSON Schema tự sinh.
  * Thực thi: `{"method": "tools/call", "params": {"name": "get_weather", "arguments": {"city": "Hanoi"}}}` -> Nhận lại kết quả text.

---

### 4.3. Thực nghiệm Module 03: MCP Production Patterns

#### 4.3.1. Authentication (Kiểm thử cả trường hợp Thành công & Thất bại)

**Trường hợp 1: Token hợp lệ**
```bash
# Terminal 1: Chạy Server
cd 03-production && ../.venv/bin/python auth_server.py

# Terminal 2: Chạy Client với đúng Token
MCP_AUTH_TOKEN="dev-token-abc123" ../.venv/bin/python auth_client.py
```
*Output Client:*
```text
Tools (có auth):
  - get_weather: Lấy thời tiết hiện tại của một thành phố.

Kết quả: Hanoi: 29°C, trời mưa
```
*Log Server ghi nhận:*
```text
INFO: 127.0.0.1:53554 - "POST /mcp HTTP/1.1" 200 OK
INFO: 127.0.0.1:53557 - "POST /mcp HTTP/1.1" 202 Accepted
INFO: 127.0.0.1:53558 - "GET /mcp HTTP/1.1" 200 OK
```

**Trường hợp 2: Token sai hoặc không có quyền**
```bash
MCP_AUTH_TOKEN="wrong-token-xyz" ../.venv/bin/python auth_client.py
```
*Log Server lập tức từ chối và ghi nhận:*
```text
INFO: 127.0.0.1:53567 - "POST /mcp HTTP/1.1" 401 Unauthorized
```
*Client bắt Exception:*
```text
mcp.shared.exceptions.MCPError: Server returned an error response (401 Unauthorized)
```
*Ý nghĩa kiến trúc*: Tầng xác thực hoạt động độc lập ở transport HTTP, bảo vệ tài nguyên hệ thống trước khi request chạm vào bất kỳ dòng code nghiệp vụ nào của Tool.

---

#### 4.3.2. Tool Registry & Discovery

**Lệnh thực thi:**
```bash
cd 03-production
../.venv/bin/python registry_client.py
```

**Console Output thực tế:**
```text
=== Tool Registry ===

  get_weather v1.0.0
    Lấy thời tiết hiện tại của một thành phố
    tags: ['weather', 'current', 'vietnam']  →  server: weather
  get_weather_v2 v2.0.0
    Lấy thời tiết chi tiết — JSON, hỗ trợ forecast và đơn vị đo
    tags: ['weather', 'forecast', 'detailed', 'vietnam']  →  server: weather-v2
  send_email v1.0.0
    Gửi email tới một hoặc nhiều người nhận
    tags: ['email', 'notification', 'communication']  →  server: email-service
  query_db v1.2.0
    Chạy truy vấn SQL trên database nội bộ
    tags: ['database', 'sql', 'query', 'analytics']  →  server: db-gateway

--- Agent cần tool có tag "weather" ---
Tìm thấy 2 tool(s):
  • get_weather v1.0.0 (server: weather)
  • get_weather_v2 v2.0.0 (server: weather-v2)

Best match: get_weather_v2 v2.0.0
Kết nối tới server [weather-v2]...
Kết quả: {"api_version": "2.0", "city": "Hanoi", "temp": 29, "units": "celsius", "condition": "trời mưa", "humidity": 82, "wind_speed_kmh": 12, "timestamp": "2026-10-14T17:45:55.356326+00:00"}

--- Agent tìm tool có keyword "forecast" ---
  • get_weather_v2: Lấy thời tiết chi tiết — JSON, hỗ trợ forecast và đơn vị đo
```

**Phân tích thuật toán Registry:**
* Registry tìm thấy 2 công cụ có tag `weather`.
* Thuật toán `ToolRegistry.best_match()` sử dụng `packaging.version.parse`:
  * `v2.0.0 > v1.0.0`
  * `v1.0.0` có cờ `deprecated: true` -> bị loại khỏi danh sách ưu tiên.
* Agent tự động chọn `get_weather_v2`, đọc cấu hình transport của `weather-v2` và tự spawn kết nối.

---

#### 4.3.3. Versioning & Backward Compatibility

**Lệnh thực thi:**
```bash
cd 03-production
../.venv/bin/python versioned_client.py
```

**Console Output thực tế:**
```text
Server: weather-v2 v2.0.0
Deprecated tools: ['get_weather']
Migration: Chuyển từ get_weather sang get_weather_v2. Tham số 'city' giữ nguyên, thêm include_forecast và units.

Tools:
  - get_weather: [v1] Lấy thời tiết hiện tại — trả chuỗi đơn giản. Deprecated, dùng get_weather_v2.
  - get_weather_v2: [v2] Lấy thời tiết chi tiết — JSON, hỗ trợ forecast và đơn vị đo.

    Args:
        city: Tên thành phố (ví dụ: Hanoi, Danang)
        include_forecast: Có trả thêm dự báo 2 ngày tới không (mặc định: False)
        units: Đơn vị nhiệt độ — "celsius" hoặc "fahrenheit" (mặc định: celsius)
    

[v1] get_weather('Hanoi'):
  Hanoi: 29°C, trời mưa

[v2] get_weather_v2('Hanoi', forecast=True):
  {
  "api_version": "2.0",
  "city": "Hanoi",
  "temp": 29,
  "units": "celsius",
  "condition": "trời mưa",
  "humidity": 82,
  "wind_speed_kmh": 12,
  "timestamp": "2026-10-14T17:46:00.352669+00:00",
  "forecast": [
    {
      "day": "tomorrow",
      "temp": 27,
      "condition": "mưa nhẹ"
    },
    {
      "day": "day_after",
      "temp": 31,
      "condition": "nắng"
    }
  ]
}
```

**Phân tích kỹ thuật Versioning:**
1. Client trước khi gọi tool sẽ đọc Resource `server://info` để hiểu hiện trạng của server.
2. Client cũ gọi `get_weather('Hanoi')` -> server vẫn phục vụ chuỗi text bình thường (không bị crash).
3. Client mới gọi `get_weather_v2('Hanoi', forecast=True)` -> nhận cấu trúc JSON giàu thông tin có dự báo 2 ngày kế tiếp.

---

### 4.4. Thực nghiệm Module 04: Lab Google ADK + FastMCP Streamable HTTP

#### 4.4.1. Khởi động FastMCP Server
```bash
cd 04-lab/mcp-server
uv run python weather.py
```
*Server Output:*
```text
✅ MCP server initialized with Streamable HTTP transport
🔧 Available tools: get_current_weather, get_forecast, health_check
🚀 Starting MCP server on http://0.0.0.0:8085/mcp
INFO: Uvicorn running on http://0.0.0.0:8085 (Press CTRL+C to quit)
```

#### 4.4.2. Chạy xác thực môi trường (`verify_setup.py`)
```bash
cd 04-lab/mcp-client
uv run python verify_setup.py
```
*Output:*
```text
============================================================
Weather Agent Setup Verification
============================================================

🔍 Checking environment configuration...
✅ GOOGLE_API_KEY configured (AIzaSyCK3W...)

🔍 Checking dependencies...
✅ Google ADK
✅ Google Generative AI
✅ MCP
✅ FastMCP
✅ python-dotenv
✅ httpx

🔍 Checking agent structure...
✅ weather_agent/agent.py
✅ weather_agent/__init__.py

🔍 Checking MCP server connectivity...
✅ MCP server reachable at http://localhost:8085/mcp (HTTP 406)

🔍 Checking agent import...
✅ Agent imported successfully: weather_agent
   Model: gemini-2.5-flash

============================================================
✅ All checks passed!
🚀 Ready to start!
   Run: uv run adk web
📍 Then open: http://localhost:8000
```

#### 4.4.3. Chạy Agent với truy vấn tiếng Việt thực tế

**Truy vấn 1: Thời tiết hiện tại**
```bash
uv run adk run weather_agent "Thời tiết ở Hà Nội hôm nay thế nào?"
```
*Kết quả Agent phản hồi:*
```text
[weather_agent]: Thời tiết hiện tại ở Hà Nội:

Nhiệt độ: 28.5°C (83.3°F)
Cảm giác như: 31.0°C (87.8°F)
Tình trạng: Mây một phần
Độ ẩm: 75%
Gió: 14.0 km/h (8.7 mph) SE
Áp suất: 1010.0 mb
Chỉ số UV: 6.0
Tầm nhìn: 10.0 km

Cập nhật lần cuối: 2026-10-15 00:46
```

**Truy vấn 2: Dự báo thời tiết 3 ngày**
```bash
uv run adk run weather_agent "Cho tôi dự báo thời tiết 3 ngày tới ở Đà Nẵng"
```
*Kết quả Agent phản hồi:*
```text
[weather_agent]: Đây là dự báo thời tiết 3 ngày tới ở Đà Nẵng:

**2026-10-15:**
*   Nhiệt độ cao nhất: 26.5°C
*   Nhiệt độ thấp nhất: 20.0°C
*   Tình trạng: Mây rải rác
*   Khả năng mưa: 20%
*   Gió tối đa: 12.0 km/h
*   Chỉ số UV: 5.0

**2026-10-16:**
*   Nhiệt độ cao nhất: 24.0°C
*   Nhiệt độ thấp nhất: 20.0°C
*   Tình trạng: Nắng
*   Khả năng mưa: 10%
*   Gió tối đa: 14.0 km/h
*   Chỉ số UV: 5.0

**2026-10-17:**
*   Nhiệt độ cao nhất: 26.5°C
*   Nhiệt độ thấp nhất: 20.0°C
*   Tình trạng: Mây rải rác
*   Khả năng mưa: 40%
*   Gió tối đa: 12.0 km/h
*   Chỉ số UV: 5.0
```

#### 4.4.4. Traces ghi nhận tại FastMCP Server trong phiên làm việc của ADK:
```text
INFO: 127.0.0.1:53588 - "POST /mcp HTTP/1.1" 200 OK      <-- Khởi tạo phiên MCP
INFO: 127.0.0.1:53591 - "POST /mcp HTTP/1.1" 202 Accepted
INFO: 127.0.0.1:53592 - "GET /mcp HTTP/1.1" 200 OK       <-- Kênh SSE nhận stream
INFO: Processing request of type ListToolsRequest        <-- ADK tự động lấy danh sách tools
INFO: Processing request of type CallToolRequest         <-- ADK tự động gọi get_current_weather
INFO: Terminating session: DELETE /mcp HTTP/1.1 200 OK   <-- Đóng kết nối khi hoàn tất
```

---

## 5. Bảng tổng hợp so sánh 4 mức độ triển khai

| Đặc tính | Mức 1: Function Calling thuần | Mức 2: MCP Cơ bản (stdio) | Mức 3: MCP Production | Mức 4: Full Agentic MCP (ADK) |
|---|---|---|---|---|
| **Vị trí Tool** | Cùng file với code gọi AI | Tiến trình riêng (subprocess) | Microservice độc lập trên mạng | Remote MCP Server (Cloud Run/K8s) |
| **Kênh truyền (Transport)** | In-memory | `stdio` | `Streamable HTTP / SSE` | `Streamable HTTP` |
| **Sinh Schema** | Viết tay 100% | Tự động từ Type Hints | Tự động + Version metadata | Tự động đồng bộ sang Agent |
| **Xác thực (Auth)** | Không có tầng riêng | Dựa vào quyền OS | Bearer Token / OAuth / Scopes | Bearer Token / Managed Identity |
| **Khám phá Tool** | Hard-code tĩnh | `list_tools()` runtime | Tool Registry (tìm theo tag/task) | `McpToolset` tự động hoàn toàn |
| **Vòng lặp gọi Tool** | Phải tự code vòng lặp `while` | Phải tự code client session | Tự động hóa qua Registry Client | Framework (ADK) quản lý 100% |
| **Giao diện người dùng** | CLI terminal | CLI terminal | CLI / API Backend | Web UI (`adk web`) tích hợp sẵn |

---

## 6. Hướng dẫn thực hành nhanh (Quick Run)

Tất cả các phần đã được thiết lập sẵn môi trường ảo và tự động nạp API key từ file `.env`.

### 1. Kiểm thử toàn bộ hệ thống bằng 1 lệnh duy nhất:
```bash
.venv/bin/python run_all.py
```
*Kịch bản sẽ tự động khởi động các server nền, gửi request kiểm thử 4 module và in bảng tổng kết trạng thái (PASSED/FAILED).*

### 2. Chạy Web Chat UI để trực tiếp thử nghiệm:
```bash
# Terminal 1: Bật MCP Weather Server (port 8085)
cd 04-lab/mcp-server
uv run python weather.py

# Terminal 2: Bật ADK Web Interface (port 8000)
cd 04-lab/mcp-client
uv run adk web
```
*Truy cập trình duyệt: `http://localhost:8000`, chọn `weather_agent` từ menu dropdown và bắt đầu trò chuyện.*

---

## 7. Checklist kinh nghiệm thực chiến khi xây dựng hệ thống MCP

1. **Thiết kế kích thước Tool (Tool Granularity)**:
   - *Không nên*: Tạo tool quá chi tiết (ví dụ: `get_temperature`, `get_humidity`, `get_wind` thành 3 tool riêng lẻ) -> Khiến LLM phải gọi 3 lần, tăng latency và chi phí token.
   - *Nên*: Gom nhóm thành 1 tool gắn kết logic (như `get_current_weather` trả về đầy đủ các chỉ số).

2. **Chất lượng Docstring quyết định độ chính xác của Agent**:
   - LLM dựa hoàn toàn vào `docstring` và mô tả tham số để quyết định có gọi tool hay không. Hãy mô tả rõ ràng: Mục đích của tool, ví dụ tham số đầu vào (ví dụ: `e.g., "Hanoi", "Tokyo"`), và định dạng kết quả trả về.

3. **Bảo mật và Nguyên tắc quyền tối thiểu (Least Privilege)**:
   - Khi đưa MCP Server lên mạng (HTTP), luôn áp dụng Token Verifier và chia Scopes.
   - Không chia sẻ khóa bí mật của hệ thống nội bộ (Database password, Master API keys) cho Client; Server là nơi duy nhất giữ bí mật và thực thi tác vụ.

4. **Luôn có chiến lược tương thích ngược (Backward Compatibility)**:
   - Mọi thay đổi tham số trên MCP Tool production đều phải có giá trị mặc định (`default value`).
   - Giữ lại tool v1 ít nhất 1-2 chu kỳ phát hành (kèm cảnh báo deprecated) trước khi chính thức loại bỏ.
