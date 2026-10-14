# TÀI LIỆU KIẾN TRÚC & HƯỚNG DẪN HỌC TẬP CHUYÊN SÂU
# PHÂN BIỆT FUNCTION CALLING VÀ MODEL CONTEXT PROTOCOL (MCP)

> Tài liệu này được thiết kế để giúp bạn nắm bắt bản chất cốt lõi, kiến trúc hệ thống và phương pháp luận giải quyết bài toán tích hợp công cụ cho AI Agent — từ mức cơ bản đến cấp độ doanh nghiệp (Production).

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

## 3. Mổ xẻ từng Module trong Repository

Repo được thiết kế theo lộ trình tiến hóa 4 bước từ cơ bản đến ứng dụng thực tế.

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

#### Hạn chế của cách này:
- Schema phải viết tay rất dài dòng, nếu sửa hàm thì phải nhớ sửa schema.
- Toàn bộ logic tool bị gắn chặt (tight coupling) vào file app. Muốn dùng lại hàm này ở một chatbot khác hoặc giao diện khác thì phải copy toàn bộ code.

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

## 4. Bảng tổng hợp so sánh 4 mức độ triển khai

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

## 5. Hướng dẫn thực hành nhanh (Quick Run)

Tất cả các phần đã được thiết lập sẵn môi trường ảo và tự động nạp API key từ file `.env`.

### 1. Kiểm thử toàn bộ hệ thống bằng 1 lệnh duy nhất:
```bash
.venv/bin/python run_all.py
```
*Kịch bản sẽ tự động khởi động các server nền, gửi request kiểm thử 4 module và in bảng tổng kết trạng thái (PASSED/FAILED).*

### 2. Chạy trải nghiệm từng thành phần:

#### Chạy Function Calling thuần:
```bash
cd 01-function-calling
../.venv/bin/python weather_function_calling.py
```

#### Chạy MCP stdio:
```bash
cd 02-mcp-basics
../.venv/bin/python weather_client.py
```

#### Chạy Production Patterns:
```bash
cd 03-production
../.venv/bin/python registry_client.py   # Test Tool Registry
../.venv/bin/python versioned_client.py  # Test Versioning & server://info
```

#### Chạy Lab Web UI với Google ADK:
```bash
# Terminal 1: Bật MCP Weather Server (port 8085)
cd 04-lab/mcp-server
uv run python weather.py

# Terminal 2: Bật ADK Web Interface (port 8000)
cd 04-lab/mcp-client
uv run adk web
```
*Truy cập trình duyệt: `http://localhost:8000`, chọn `weather_agent` và bắt đầu đặt câu hỏi.*

---

## 6. Checklist kinh nghiệm khi xây dựng hệ thống MCP thực tế

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
