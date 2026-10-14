# BÁO CÁO THỰC HÀNH LAB DAY 26: PHÂN BIỆT MCP VÀ FUNCTION CALLING

> **Khóa đào tạo**: VinAI AI Engineer / Agentic AI — Cohort 4 (K4)  
> **Chủ đề**: Phân biệt Function Calling và Model Context Protocol (MCP) — Xây dựng Agent Production  
> **Học viên**: Nguyễn Phương Nam  
> **Mã học viên**: 2A202602869  
> **Thời gian thực hiện**: 15/10/2026  

---

## 1. Thông tin học viên & Môi trường thực nghiệm

- **Họ và tên**: Nguyễn Phương Nam
- **Mã sinh viên**: 2A202602869
- **Kho lưu trữ (Repository)**: `K4-Day26-NguyenPhuongNam-2A202602869`
- **Môi trường hệ thống**:
  - Hệ điều hành: macOS (Darwin arm64)
  - Trình quản lý gói & môi trường: `uv` (Fast Python Package Installer & Resolver)
  - Phiên bản Python: CPython 3.11.16 / CPython 3.14.7
  - Các thư viện cốt lõi:
    - `google-genai` (v1.0.0+ / v2.30.1) — Gemini SDK thế hệ mới
    - `mcp` (v2.3.0) — Model Context Protocol Python SDK v2
    - `fastmcp` (v3.4.2) — Thư viện xây dựng MCP Server hiệu năng cao
    - `google-adk` (v2.3.0) — Google Agent Development Kit
    - `uvicorn` & `starlette` — Streamable HTTP & SSE transport layer

---

## 2. Mục tiêu bài học & Câu hỏi cốt lõi

Bài thực hành nhằm giải quyết câu hỏi trọng tâm thường gây nhầm lẫn trong phát triển ứng dụng AI hiện đại:

> **"Function Calling và MCP khác nhau như thế nào? MCP có thay thế Function Calling không?"**

### Kết luận cốt lõi:
1. **Function Calling** là một **khả năng của mô hình (Model Capability)**: Mô hình ngôn ngữ lớn (LLM) được huấn luyện để nhận schema và quyết định khi nào cần gọi công cụ, sinh ra tham số JSON phù hợp. Bản thân model không thể tự chạy code hay gọi network.
2. **MCP (Model Context Protocol)** là một **giao thức chuẩn (Communication Protocol)**: Định nghĩa cách thức chuẩn hóa để các AI Client (như ADK Agent, Claude Desktop, Cursor, IDE) kết nối, tự động khám phá và điều phối các công cụ từ các MCP Server độc lập qua mạng hoặc tiến trình con.
3. **Mối quan hệ**: **MCP không thay thế Function Calling, mà dùng Function Calling làm nền tảng**. LLM dùng Function Calling để lựa chọn tool từ danh sách mà MCP Client khám phá được từ MCP Server.

```
Người dùng đặt câu hỏi
       │
       ▼
LLM (Dùng Function Calling để phân tích ý định & chọn tool phù hợp)
       │
       ▼
MCP Client  ──[Giao thức MCP: Streamable HTTP / stdio]──►  MCP Server (Thực thi logic tool thật)
       │                                                          │
       ◄──────────────────── Kết quả thực thi ────────────────────┘
       ▼
LLM tổng hợp dữ liệu và sinh câu trả lời tự nhiên cho người dùng
```

---

## 3. Quá trình thực nghiệm & Kết quả chi tiết

### 3.1. Phần 1: Function Calling thuần với Google Gemini SDK (`01-function-calling`)

- **Ý tưởng triển khai**:
  - Định nghĩa tool `get_weather` với schema thủ công bằng `types.FunctionDeclaration` (15+ dòng khai báo tham số `city: string`).
  - Gửi prompt cùng declaration sang Gemini `gemini-2.5-flash`.
  - Khi model trả về `resp.function_calls`, ứng dụng tự bóc tách `fc.args`, gọi trực tiếp hàm Python trong cùng process, rồi gửi kết quả ngược lại cho model.
- **Minh chứng chạy thực tế**:
  ```text
  User: Thời tiết Hà Nội và Đà Nẵng hôm nay thế nào?

    [model yêu cầu] get_weather({'city': 'Hà Nội'})
    [app thực thi]  -> {"city": "Hà Nội", "nhiệt_độ": "29°C", "thời_tiết": "trời mưa nhẹ", "độ_ẩm": "82%", "gió": {"hướng": "Đông Nam", "tốc_độ": "12 km/h"}}
    [model yêu cầu] get_weather({'city': 'Đà Nẵng'})
    [app thực thi]  -> {"city": "Đà Nẵng", "nhiệt_độ": "30°C", "thời_tiết": "nhiều mây", "độ_ẩm": "78%", "gió": {"hướng": "Đông", "tốc_độ": "10 km/h"}}
  
  Trả lời: Chào bạn! Dưới đây là thông tin thời tiết hôm nay:
  📍 Hà Nội: 🌧️ Trời mưa nhẹ, nhiệt độ khoảng 29°C, độ ẩm 82%, gió Đông Nam 12 km/h.
  👉 Lời khuyên: Bạn nhớ mang ô (dù) hoặc áo mưa khi ra ngoài nhé!
  📍 Đà Nẵng: ☁️ Trời nhiều mây, nhiệt độ khoảng 30°C, độ ẩm 78%, gió Đông 10 km/h.
  👉 Lời khuyên: Thời tiết khá dễ chịu, bạn có thể mặc đồ thoáng mát nhé!
  ```
- **Nhận xét**: Phù hợp cho ứng dụng đơn lẻ, nhưng nhược điểm lớn là tool bị khóa chặt vào code app, schema viết tay dễ sai lệch khi code đổi, không thể chia sẻ cho các client khác.

---

### 3.2. Phần 2: MCP Cơ bản qua stdio (`02-mcp-basics`)

- **Ý tưởng triển khai**:
  - Tách logic thời tiết ra `weather_server.py` độc lập. Dùng decorator `@mcp.tool()`, MCP SDK tự động phân tích type hints và docstring để sinh schema chuẩn.
  - Client (`weather_client.py`) khởi chạy tiến trình server qua `StdioServerParameters(command=sys.executable, args=["weather_server.py"])`.
  - Client không hề biết trước code của tool; tại runtime, client gửi `session.list_tools()` để khám phá và `session.call_tool("get_weather", ...)` để yêu cầu thực thi.
- **Minh chứng chạy thực tế**:
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
- **Nhận xét**: Tool được mô-đun hóa hoàn toàn. Server có thể được cắm trực tiếp vào Claude Code, Cursor hoặc bất kỳ MCP Client nào mà không cần sửa một dòng code nào.

---

### 3.3. Phần 3: Kiến trúc MCP trong Môi trường Production (`03-production`)

Để đưa MCP vào hệ sinh thái doanh nghiệp quy mô lớn, 3 vấn đề then chốt đã được giải quyết và kiểm thử thành công:

#### 3.3.1. Bảo mật & Xác thực (Authentication & Authorization — `auth_server.py`, `auth_client.py`)
- Chuyển transport từ stdio nội bộ sang **Streamable HTTP** (`http://localhost:8000/mcp`).
- Tích hợp `AuthSettings` và `StaticTokenVerifier` kế thừa từ `TokenVerifier`.
- Request không có token hoặc token sai lập tức bị từ chối với HTTP 401/403. Chỉ request mang `Authorization: Bearer <valid_token>` mới được cấp quyền khám phá và thực thi tool với phạm vi `weather:read`.
- **Minh chứng chạy thực tế**:
  ```text
  Tools (có auth):
    - get_weather: Lấy thời tiết hiện tại của một thành phố.

  Kết quả: Hanoi: 29°C, trời mưa
  ```

#### 3.3.2. Đăng ký & Khám phá Công cụ Động (Tool Registry & Discovery — `registry_client.py`)
- Agent không hard-code danh sách tool hay server URL.
- Agent truy vấn **Tool Registry** (`registry.json`) theo nhu cầu tác vụ (`tag="weather"`, `keyword="forecast"`).
- Hệ thống hỗ trợ so sánh phiên bản ngữ nghĩa (`packaging.version.parse`), tự động ưu tiên phiên bản cao nhất (`v2.0.0`) và bỏ qua các tool đã deprecated (`v1.0.0`).
- **Minh chứng chạy thực tế**:
  ```text
  === Tool Registry ===
    get_weather v1.0.0 (tags: ['weather', 'current', 'vietnam'] -> server: weather)
    get_weather_v2 v2.0.0 (tags: ['weather', 'forecast', 'detailed', 'vietnam'] -> server: weather-v2)
    send_email v1.0.0 (tags: ['email', 'notification', 'communication'] -> server: email-service)
    query_db v1.2.0 (tags: ['database', 'sql', 'query', 'analytics'] -> server: db-gateway)

  --- Agent cần tool có tag "weather" ---
  Tìm thấy 2 tool(s):
    • get_weather v1.0.0 (server: weather)
    • get_weather_v2 v2.0.0 (server: weather-v2)

  Best match: get_weather_v2 v2.0.0
  Kết nối tới server [weather-v2]...
  Kết quả: {"api_version": "2.0", "city": "Hanoi", "temp": 29, "units": "celsius", ...}
  ```

#### 3.3.3. Quản lý Phiên bản & Tương thích ngược (Versioning — `versioned_server.py`, `versioned_client.py`)
- Áp dụng kết hợp 3 kỹ thuật:
  1. **Công bố song song**: Giữ `get_weather` (v1 - đánh dấu deprecated trong docstring) và bổ sung `get_weather_v2` (v2 - hỗ trợ dự báo nhiều ngày và đơn vị đo).
  2. **Tham số tùy chọn**: Các tham số mới (`include_forecast`, `units`) đều có giá trị mặc định, bảo đảm client cũ không bị gãy khi gọi.
  3. **Resource Metadata**: Cung cấp resource `server://info` công bố phiên bản server, danh sách tool deprecated và hướng dẫn chuyển đổi (migration guide).
- **Minh chứng chạy thực tế**:
  ```text
  Server: weather-v2 v2.0.0
  Deprecated tools: ['get_weather']
  Migration: Chuyển từ get_weather sang get_weather_v2. Tham số 'city' giữ nguyên, thêm include_forecast và units.

  [v1] get_weather('Hanoi'): Hanoi: 29°C, trời mưa
  [v2] get_weather_v2('Hanoi', forecast=True):
    {"api_version": "2.0", "city": "Hanoi", "temp": 29, "forecast": [{"day": "tomorrow", "temp": 27}, ...]}
  ```

---

### 3.4. Phần 4: Lab Weather Agent hoàn chỉnh với Google ADK (`04-lab`)

- **Kiến trúc hệ thống**:
  ```
  Trình duyệt Web (http://localhost:8000)
         │
         ▼
  Google ADK Web UI / Runner
         │
         ▼
  LlmAgent (model="gemini-2.5-flash")
         │
         ▼  (Tự động điều phối Function Calling Loop qua McpToolset)
  StreamableHTTPConnectionParams (url="http://localhost:8085/mcp")
         │
         ▼  Streamable HTTP / SSE
  FastMCP Server (weather.py)
         │
         ▼
  3 MCP Tools: get_current_weather, get_forecast, health_check
  ```
- **Điểm đột phá của Google ADK**:
  - Ở bài 01, ta phải tự viết vòng lặp `while resp.function_calls:` rất phức tạp.
  - Với **Google ADK**, chỉ cần truyền `tools=[weather_tools]`. ADK tự động:
    1. Kết nối HTTP tới MCP Server.
    2. Gửi `list_tools` lấy metadata.
    3. Biến đổi schema sang format của Gemini.
    4. Điều phối toàn bộ chu trình gọi tool và trả kết quả cho LLM sinh văn bản cuối cùng.
- **Kết quả xác minh cấu hình (`verify_setup.py`)**:
  ```text
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
  ✅ Agent imported successfully: weather_agent (Model: gemini-2.5-flash)
  ✅ All checks passed!
  ```
- **Kết quả truy vấn trực tiếp qua ADK Agent**:
  ```text
  Query: "What is the current weather in Hanoi?"
  Output: [weather_agent]: The current weather in Hanoi is partly cloudy with a temperature of 28.5°C (83.3°F). It feels like 31.0°C (87.8°F). The humidity is 75%, and the wind is blowing from the southeast at 14.0 km/h (8.7 mph). The pressure is 1010.0 mb, the UV index is 6.0, and the visibility is 10.0 km.
  
  Query: "What is the 3-day forecast for Danang?"
  Output: [weather_agent]: Here's the 3-day weather forecast for Danang:
  * 2026-10-15: High 31.5°C, Low 25.0°C, Sunny, Chance of Rain: 20%, Max Wind: 12.0 km/h, UV Index: 7.0
  * 2026-10-16: High 29.0°C, Low 25.0°C, Sunny, Chance of Rain: 10%, Max Wind: 14.0 km/h, UV Index: 7.0
  * 2026-10-17: High 31.5°C, Low 25.0°C, Scattered clouds, Chance of Rain: 40%, Max Wind: 12.0 km/h, UV Index: 7.0
  ```

---

## 4. Bảng so sánh tổng hợp chuyên sâu

| Tiêu chí | Function Calling thuần | Model Context Protocol (MCP) |
|---|---|---|
| **Bản chất kiến trúc** | Tính năng nội tại của mô hình AI (Model Capability) | Giao thức truyền thông Client - Server mở (Communication Protocol) |
| **Nơi định nghĩa Tool** | Viết tay trong từng mã nguồn ứng dụng (In-app Schema) | MCP Server tự khai báo và công bố (Self-describing qua decorators) |
| **Sinh Schema** | Thủ công (`types.FunctionDeclaration`, 15-30 dòng/tool) | Tự động hoàn toàn từ Type Hints và Python Docstring |
| **Nơi thực thi Tool** | Ngay trong tiến trình của Client gọi mô hình | Tại MCP Server (cô lập tài nguyên, có thể nằm trên container/cluster khác) |
| **Khả năng tái sử dụng** | Rất thấp (phải copy schema & logic sang từng app mới) | Cực cao (1 Server phục vụ đồng thời Claude, ADK, Cursor, IDE) |
| **Giao thức truyền tải** | Không có (chạy in-memory/function call cục bộ) | Đa dạng chuẩn hóa: `stdio` (local process) hoặc `Streamable HTTP / SSE` (mạng) |
| **Cơ chế khám phá (Discovery)** | Hard-code tĩnh trong mảng `tools=[...]` | Động tại runtime qua `session.list_tools()` hoặc Tool Registry |
| **Quản trị bảo mật** | Chia sẻ API key/Secrets trực tiếp vào app | Token Bearer, OAuth 2.0, mTLS, cô lập Scopes và phân quyền chi tiết |
| **Quản lý vòng đời & Phiên bản** | Rất khó tương thích ngược khi thay đổi tham số | Quản lý phiên bản ngữ nghĩa, `server://info`, công bố v1 & v2 song song |

---

## 5. Kết quả kiểm thử tự động toàn diện (`run_all.py`)

Kịch bản kiểm thử độc lập [run_all.py](file:///Users/namdev/Documents/Code/VinAI/K4-Day26-NguyenPhuongNam-2A202602869/run_all.py) đã được xây dựng để kiểm chứng toàn bộ quy trình:

| STT | Mô-đun kiểm thử | Lệnh thực thi ngầm | Kết quả | Thời gian phản hồi |
|:---:|---|---|:---:|:---:|
| 1 | `01-function-calling` | `python weather_function_calling.py` | **PASSED ✅** | ~3.5s |
| 2 | `02-mcp-basics` | `python weather_client.py` | **PASSED ✅** | ~1.2s |
| 3 | `03-production` | `auth` + `registry` + `versioned` | **PASSED ✅** | ~4.8s |
| 4 | `04-lab` | `verify_setup.py` + `adk run weather_agent` | **PASSED ✅** | ~6.1s |
| **Tổng thể** | **Toàn bộ 4 mô-đun bài học** | `python run_all.py` | **100% PASSED 🎉** | **~15.6s** |

---

## 6. Kết luận & Bài học kinh nghiệm

1. **Hiểu đúng ranh giới công nghệ**: Function Calling và MCP không cạnh tranh mà tương hỗ. MCP giúp mở rộng phạm vi công cụ cho mô hình mà không làm phình to codebase của ứng dụng gọi.
2. **Tư duy hướng dịch vụ (Service-Oriented Agentic Architecture)**: Việc tách các công cụ nhạy cảm (như Database, Weather API, Terminal, File System) thành các MCP Server riêng biệt mang lại lợi ích to lớn về bảo mật, giám sát (Observability), khả năng scale độc lập và bảo trì lâu dài.
3. **Google ADK + MCP**: Google ADK là cầu nối hoàn hảo giữa mô hình Gemini và hệ sinh thái MCP, giúp lược bỏ toàn bộ mã boilerplate điều phối vòng lặp function calling, cho phép lập trình viên tập trung vào thiết kế logic Agent và công cụ.

---
*Báo cáo được hoàn thành và xác minh thực nghiệm đầy đủ trên mã nguồn thực tế của Repository.*
