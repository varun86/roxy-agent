# roxy-agent

<div align="center">
  <img src="desktop/assets/roxy/roxy-idle.svg" alt="Roxy - Your Desktop Companion" width="128" height="128" />
  <p>
    <strong>roxy-agent</strong> — 一个把桌面桌宠、Agent Harness、3D VRM 动作资产与本地 TTS 融合在一起的桌面 AI Companion。
  </p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python">
    <img src="https://img.shields.io/badge/Node.js-18+-green.svg" alt="Node">
    <img src="https://img.shields.io/badge/Platform-macOS%20%7C%20Windows-blueviolet.svg" alt="Platform">
  </p>
</div>

---

## 项目简介

`roxy-agent` 是一个偏作品型、也偏产品型的桌面 AI Agent 项目。

它不只是“接个模型聊聊天”，而是把这些层真正拼到一起：

- **桌面存在感**：Roxy 常驻桌宠 + 对话弹层 + 状态反馈
- **Agent Runtime**：tool loop、sandbox、memory、RAG、subagent、host browser action
- **3D Character Stack**：VRM 模型、VRMA 动作、情绪与状态切换
- **Voice Stack**：本地 GPT-SoVITS TTS 服务 + 桌宠语音播放反馈
- **Persona Layer**：围绕洛琪希构建的角色技能、语气与陪伴式交互

目标很直接：让桌面助手不只是能回答问题，而是真的像一个会想、会动、会出声的角色存在。

## 对话展示

双击打开对话的轻交互模式

| 常态模式                       | 思考状态                               |
|----------------------------|------------------------------------|
| ![idle.png](docs/idle.png) | ![thinking.png](docs/thinking.png) |

## Why It Feels Different

| 能力层 | 现在已经有的内容 |
|------|------|
| **Agent Runtime** | 多轮 tool-call、thread context、knowledge search、subagent、宿主浏览器动作 |
| **Desktop Presence** | Electron 常驻桌宠、轻量对话弹层、事件驱动反馈 |
| **3D Character Assets** | `desktop/assets/roxy_3D/roxi.vrm` 主模型 + 多组 `VRMA` 动作资源 |
| **Voice Layer** | `scripts/tts/roxy_gsv_service.py` 本地 TTS 服务 + `desktop/assets/voice/ja/*.wav` 语音素材 |
| **Roleplay / Persona** | `roxy-skill` 驱动的洛琪希角色表达与陪伴感 |

### 核心特性

- **桌面桌宠**：像素风格的 Roxy 桌宠，内置于 Electron 应用，实时响应 Agent 状态
- **3D 角色演出**：内置 VRM 模型与 VRMA 动作资源，桌宠不再只是平面贴图，而是可扩展的 3D 角色层
- **本地语音能力**：接入 GPT-SoVITS 本地 TTS 服务，为桌面陪伴体验预留真正“开口说话”的能力
- **Agent 能力**：基于 deer-flow 思路演进出的完整 Harness 系统，包含 loop、tool registry、sandbox、memory、RAG 与 subagent
- **RoxySkills**：内置蒸馏好的洛琪希角色技能系统，深度定制的角色 prompt 和行为模式
- **可扩展性**：完整的工具注册与执行框架，轻松添加自定义工具
- **沙箱安全**：基于路径边界和命令过滤的本地安全执行环境

## Media Stack

### Pixel Pet Layer

- 资源目录：`desktop/assets/roxy/`
- 当前内置 idle、thinking、working、sleeping、drag reaction 等像素状态资源
- 适合常驻桌面、轻量反馈、通知提醒与低功耗展示

### 3D Pet Layer

- 主模型：`desktop/assets/roxy_3D/roxi.vrm`
- 备用模型：`desktop/assets/roxy_3D/roxy_asset_3d.vrm`
- 动作目录：`desktop/assets/roxy_3D/vrma/`
- 当前已接入 `Thinking`、`LookAround`、`Relax`、`Angry`、`Blush`、`Clapping`、`Sleepy`、`Sad`、`Jump`、`Surprised`、`Goodbye`
- 渲染入口：`desktop/src/renderer/pet/PetApp.tsx`

### Voice / TTS Layer

- 本地 TTS 服务：`scripts/tts/roxy_gsv_service.py`
- 启动脚本：`scripts/tts/run_roxy_gsv_service.sh`
- 使用说明：`docs/roxy-gsv-local-tts.md`
- 桌宠语音素材：`desktop/assets/voice/ja/`
- Electron 主进程已经具备语音事件转发与播放能力

这意味着这个项目现在已经不只是一个聊天壳子，而是正在把这五层能力汇成同一个角色：

- 文本大脑
- 工具手脚
- 桌面形象
- 动作表达
- 声音反馈

### 灵感来源

本项目参考三个开源项目的核心能力：

| 项目 | 贡献 |
|------|------|
| [deer-flow](https://github.com/bytedance/deer-flow) | 模块化 Agent 运行时引擎核心 |
| [clawd-on-desk](https://github.com/rullerzhou-afk/clawd-on-desk) | Electron 桌宠实现参考 |
| [RoxySkills](https://github.com/umikok7/Roxy-SKILL) | 洛琪希角色定制化技能系统 |

## 快速开始

### 环境要求

- **Python**: 3.11+
- **Node.js**: 18+
- **pnpm** (推荐) 或 npm

### 安装与运行

```bash
# 1. 克隆项目
git clone https://github.com/umikok7/my-deer-flow.git
cd my-deer-flow

# 2. 安装后端依赖
uv sync

# 3. 启动后端 API 服务
cd APP && uvicorn main:app --reload

# 4. 新开终端，启动前端（可选，用于 Web 界面）
cd frontend && npm install && npm run dev

# 5. 新开终端，启动桌面客户端
cd desktop && npm install && npm run dev
```

如果你想把本地语音链路也一起跑起来，可以额外启动：

```bash
scripts/tts/run_roxy_gsv_service.sh
```

### 一键启动所有服务

现在也可以直接从项目根目录统一管理全部服务：

```bash
# 首次安装依赖
make bootstrap

# 一键启动 qdrant + backend + frontend + desktop
make up

# 查看状态与健康检查
make status
make health

# 查看日志
make logs SERVICE=backend
make frontend-logs
make desktop-logs

# 一键停止
make down
```

运行说明：

- `make up` 会后台启动 `qdrant`、FastAPI 后端、Next.js 前端和 Electron desktop
- 日志会写入 `.runtime/logs/`
- PID 文件会写入 `.runtime/pids/`
- 如果只是想重启整套开发环境，可以直接执行 `make restart`

### 配置

在项目根目录创建 `.env` 文件：

```env
MINIMAX_API_KEY=your_api_key_here
HARNESS_DEFAULT_MODEL=minimax-m2.7
HARNESS_SANDBOX_ROOT=.sandbox
HARNESS_MAX_STEPS=8
HARNESS_LOCAL_BROWSER_ENABLED=true
HARNESS_LOCAL_BROWSER_SEARCH_ENGINE=https://www.bing.com/search?q={query}
```

## 项目架构

```
my-deer-flow/
├── desktop/               # Electron 桌面客户端
│   ├── assets/roxy/       # Roxy 像素资源
│   └── src/               # 客户端源码
│
├── harness/               # Agent 运行时引擎核心
│   ├── agents/            # AsyncAgentLoop 异步执行循环
│   ├── tools/             # 工具注册与执行 (ToolRegistry, ToolExecutor)
│   ├── sandbox/           # BasicSandbox 权限隔离
│   ├── context/            # ThreadContext 线程级上下文
│   ├── skills/            # SkillsLoader 技能加载
│   └── models/            # 数据结构定义
│
├── APP/                   # FastAPI 应用层
│   ├── api/               # API 路由 (/chat, /chat/stream)
│   ├── dto/               # 数据传输对象
│   └── service/            # ChatService 业务逻辑
│
├── frontend/              # Next.js Web 界面（可选）
├── skills/               # 技能系统
│   ├── public/           # 内置公共技能
│   └── custom/            # 自定义技能（如 roxy-skill）
│
└── tests/                 # 测试文件
```


## 核心模块

### AsyncAgentLoop (`harness/agents/loop.py`)

异步 Agent 执行循环，支持多步 Tool-Call 迭代。

```python
from harness.agents.loop import AsyncAgentLoop

loop = AsyncAgentLoop(client=chat_client, executor=tool_executor)
result = await loop.run(messages, max_steps=8)
```

### ToolRegistry (`harness/tools/registry.py`)

可扩展的工具注册表，默认注册 9 个工具：

| 工具 | 功能 |
|------|------|
| `bash` | 执行 Bash 命令 |
| `ls` | 列出目录内容 |
| `read_file` | 读取文件 |
| `write_file` | 写入文件 |
| `str_replace` | 原地编辑文件 |
| `browser_search` | 打开本地默认浏览器并发起搜索 |
| `browser_open` | 在本地默认浏览器中打开指定网页 |
| `knowledge_search` | 搜索本地知识库与上传资料 |
| `web_search` | 网页搜索 |

### BasicSandbox (`harness/sandbox/runtime.py`)

安全执行环境，强制：
- 路径边界限制（禁止访问 `.sandbox` 外部）
- 危险命令过滤（`rm -rf`, `sudo`, `shutdown` 等）

### Skills 系统

技能是 Markdown 文件，位于 `skills/{public,custom}/*/SKILL.md`，通过 `extensions_config.json` 启用/禁用。

```
skills/
├── public/        # 内置技能
└── custom/        # 自定义技能
    └── roxy-skill/
        └── SKILL.md
```

## 自定义你的桌宠

想换掉 Roxy？完全可以！roxy-agent设计为可泛化的IP定制框架：

1. **替换像素资源**：将 `desktop/assets/roxy/` 下的 SVG 替换为你喜欢的角色（已弃用，目前全面转向3D资产）
2. **替换 3D 资产**：将 `desktop/assets/roxy_3D/` 下的 `VRM / VRMA` 模型与动作替换成新的角色包
3. **替换语音能力**：调整 `scripts/tts/` 下的本地 TTS 服务权重、参考音频与输出风格
4. **创建新技能**：在 `skills/custom/` 下创建新的技能目录和 `SKILL.md`
5. **修改 Agent Prompt**：编辑技能文件中的 system prompt 来定义角色行为

如果你想做自己的桌面角色项目，这个仓库已经给出了一个很完整的骨架：

- 桌宠容器
- Agent runtime
- 角色技能系统
- 3D 资产接入方式
- 本地语音服务入口
- 工具与沙箱机制

## License

MIT License
