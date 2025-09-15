# Kasal - AI Agent Workflow Orchestration Platform

## Overview

Kasal is a sophisticated AI agent workflow orchestration platform built with a clean architecture pattern, designed to enable users to create, manage, and execute complex AI agent workflows. The platform combines React-based frontend interfaces with a robust FastAPI backend, leveraging CrewAI for agent orchestration and Databricks for enterprise-grade AI capabilities.

## Architecture Overview
Below is a semi-detailed architecture of the most important architectural components of Kasal. Below this diagram there will be a brief introduction to each of those components to understand the logical & physical separation of them. 

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                FRONTEND                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                      │
│  │   React UI      │  │   Material-UI   │  │   ReactFlow     │                      │
│  │   Components    │  │   Design        │  │   Workflows     │                      │
│  │ src/frontend/   │  │ src/frontend/   │  │ src/frontend/   │                      │
│  │ src/components/ │  │ src/theme/      │  │ src/components/ │                      │
│  │                 │  │                 │  │ ReactFlowDiagram│                      │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                      │
│                                    │                                                │
│                              ┌─────────────┐                                        │
│                              │   API       │                                        │
│                              │   Client    │                                        │
│                              │ src/frontend│                                        │
│                              │ /src/api/   │                                        │
│                              └─────────────┘                                        │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                   HTTP/REST
                                       │
┌───────────────────────────────────────────────────────────────────────────────────-──┐
│                                BACKEND                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐ │
│  │                           FastAPI Router Layer                                  │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────┐   │ │
│  │  │   Auth      │ │   Crews     │ │   Memory    │ │     ...     │ │ Config   │   │ │
│  │  │   Router    │ │   Router    │ │   Router    │ │     ...     │ │ Router   │   │ │
│  │  │ auth_router │ │ crews_router│ │memory_router│ │     ...     │ │ /api/    │   │ │
│  │  │ .py         │ │ .py         │ │ .py         │ │             │ │          │   │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ └──────────┘   │ │
│  └─────────────────────────────────────────────────────────────────────────────────┘ │
│                                       │                                              │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐ │
│  │                            Service Layer                                        │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────┐   │ │
│  │  │   Auth      │ │   Crew      │ │   Memory    │ │     ...     │ │ CrewAI   │   │ │
│  │  │   Service   │ │   Service   │ │   Service   │ │     ...     │ │ Engine   │   │ │
│  │  │ auth_service│ │ crew_service│ │ memory_     │ │     ...     │ │ /engines/│   │ │
│  │  │ .py         │ │ .py         │ │ service.py  │ │             │ │ crewai/  │   │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ └──────────┘   │ │
│  └─────────────────────────────────────────────────────────────────────────────────┘ │
│                                       │                                              │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐ │
│  │                          Repository Layer                                       │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────┐   │ │
│  │  │   User      │ │   Crew      │ │   Memory    │ │     ...     │ │ Tool     │   │ │
│  │  │   Repo      │ │   Repo      │ │   Repo      │ │     ...     │ │ Factory  │   │ │
│  │  │ user_repo   │ │ crew_repo   │ │ memory_repo │ │     ...     │ │ tool_    │   │ │
│  │  │ .py         │ │ .py         │ │ .py         │ │             │ │ factory  │   │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ └──────────┘   │ │
│  └─────────────────────────────────────────────────────────────────────────────────┘ │
│                                       │                                              │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐ │
│  │                              ORM Layer                                          │ │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐│ │
│  │  │                         SQLAlchemy 2.0                                      ││ │
│  │  │                      /src/models/ & /src/db/                                ││ │
│  │  └─────────────────────────────────────────────────────────────────────────────┘│ │
│  └─────────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────-─┘
                                       │
                          ┌─────────────────────────────┐
                          │                             │
                          ▼                             ▼
                ┌───────────────-──┐            ┌─────────────────┐
                │   Database       │            │   External      │
                │   (app.db)       │            │   Services      │
                │                  │            │                 │
                │ • execution_logs │            │ • Vector Search │
                │ • execution_trace│            │ • Model Serving │
                │ • chat_history   │            │ • MLflow        │
                │ • crews          │            │ • Unity Catalog │
                │ • memory_backend │            │ • Volumes       │
                │ • users          │            │ • MCP Servers   │
                └──────────────-───┘            └─────────────────┘
```

## Component Details with Repository Locations:
Kasal is a complex full-stack application that is composed of a frontend that communicates with a complex and diverse backend structure. Some core components and their main characteristics are outlined in this section after the architectural overview.

### Frontend Components:
The Frontend provides a comprehensive React-based user interface for managing AI agent workflows, built with modern TypeScript patterns and Material-UI design system. Key architectural features include:

#### **Core UI Framework:**
- **React 18 with TypeScript**: `src/frontend/src/components/` - Modern React architecture with strong typing and component composition
- **Material-UI Design System**: `src/frontend/src/theme/` - Consistent design tokens, theming, and responsive components
- **ReactFlow Workflow Editor**: `src/frontend/src/components/ReactFlowDiagram/` - Visual workflow builder with drag-drop interface and real-time execution monitoring
- **API Client Layer**: `src/frontend/src/api/` - Centralized HTTP client services with TypeScript interfaces for all backend communication

#### **Key UI Modules:**
- **Plans Management**: `src/frontend/src/components/Plans/` - Interface for creating and managing high-level AI workflow objectives
- **Agent Configuration**: `src/frontend/src/components/Agents/` - Agent creation wizard with role selection, tool assignment, and personality configuration
- **Task Designer**: `src/frontend/src/components/Tasks/` - Task definition interface with dependency management and output specification
- **Memory Backend Setup**: `src/frontend/src/components/MemoryBackend/` - Vector search configuration and memory type selection interface
- **Execution Monitoring**: `src/frontend/src/components/Execution/` - Real-time workflow execution tracking with live agent communications
- **Chat Interface**: `src/frontend/src/components/Chat/` - Interactive chat panel for direct agent communication and workflow guidance

#### **State Management & Services:**
- **Redux/Zustand Stores**: `src/frontend/src/store/` - Global state management for workflow configurations, execution state, and user preferences
- **Service Layer**: `src/frontend/src/api/` - 25+ specialized services including CrewService, ModelService, DatabricksVectorSearchService, and MCPService
- **Real-time Updates**: WebSocket integration for live execution progress and agent communication streaming

### Backend Components:
Since most functionalties are handled on the server and not on the client side and the client simply acts as a classical WebUI the backend is much more complex and defined via the following key compoents and their respective functionalties. 

#### **Backend Router Layer:**
Routers in general handle incoming HTTP requests and route different types of traffic (auth, crews, memory, tools) to appropriate service handlers. Some of the most predominent examples of our library include:
- **Auth Router**: `src/backend/src/api/auth_router.py` - Authentication, authorization, and user session management
- **Crews Router**: `src/backend/src/api/crews_router.py` - CRUD operations for crew configurations and execution
- **Memory Router**: `src/backend/src/api/memory_backend_router.py` - Memory backend configuration and vector search setup
- **Tools Router**: `src/backend/src/api/tools_router.py` - Tool discovery, configuration, and custom tool management
- **Config Router**: `src/backend/src/api/` - System configuration and settings management

#### **Service Layer:**
The Service Layer contains the core business logic and orchestrates what operations should be performed for each request. A none exhaustive list of operations defined here is:
- **Auth Service**: `src/backend/src/services/auth_service.py` - User authentication, OBO token handling, and permission management
- **Crew Service**: `src/backend/src/services/crew_service.py` - Crew orchestration, agent coordination, and task execution
- **Memory Service**: `src/backend/src/services/memory_backend_service.py` - Memory backend management and vector storage operations
- **Execution Service**: `src/backend/src/services/execution_service.py` - Background task execution, monitoring, and result handling
- **CrewAI Engine**: `src/backend/src/engines/crewai/` - Multi-agent workflow orchestration and execution

#### **Repository Layer:**
The Repository Layer provides data access connectors to external services (Databricks, Vector Search, Genie, etc.) and internal database operations. Some key features that are supported so far include:
- **User Repo**: `src/backend/src/repositories/user_repository.py` - User data access, profile management, and group associations
- **Crew Repo**: `src/backend/src/repositories/crew_repository.py` - Crew configuration persistence and retrieval
- **Memory Repo**: `src/backend/src/repositories/memory_backend_repository.py` - Memory backend configuration storage
- **Execution Repo**: `src/backend/src/repositories/execution_repository.py` - Execution history, logs, and trace data access
- **Tool Factory**: `src/backend/src/engines/crewai/tools/tool_factory.py` - Dynamic tool instantiation and MCP integration

#### **ORM Layer:**
The ORM (Object Relationship Model) defines the database structure and data models (and their core functionaltieis) for tracking and handling logs, keys, execution history, and other persistent data. Some key tables and functionaltities handled include: 
- User Model: src/backend/src/models/user.py - User profiles, authentication details, group memberships, and permissions
- Execution Log Model: src/backend/src/models/execution_log.py - Detailed logs of crew executions, agent activities, and system events
- Memory Backend Model: src/backend/src/models/memory_backend.py - Vector search configurations, index mappings, and memory type settings
- Crew Model: src/backend/src/models/crew.py - Crew configurations, agent definitions, task assignments, and execution parameters
- Chat History Model: src/backend/src/models/chat_history.py - Conversation threads, message history, and user interaction tracking

## Core Components

### 1. Authentication Workflow

Kasal implements a sophisticated multi-tier authentication system designed for enterprise Databricks environments:

#### Authentication Hierarchy (Priority Order):

1. **OBO (On-Behalf-Of) Authentication**
   - **Location**: `src/backend/src/repositories/databricks_auth_helper.py`
   - **Header**: `X-Forwarded-Access-Token`
   - **Use Case**: Databricks Apps environment with user impersonation
   - **Flow**: User token → OBO service principal → API access
   - **Implementation**: 
     ```python
     # Primary authentication method
     if user_token:
         self._user_token = user_token
         self._auth_method = AuthMethod.OBO_TOKEN
     ```

2. **PAT (Personal Access Token) from Database**
   - **Location**: `src/backend/src/services/api_keys_service.py`
   - **Storage**: Encrypted in database (`DATABRICKS_TOKEN`, `DATABRICKS_API_KEY`)
   - **Use Case**: Managed enterprise tokens with rotation capabilities
   - **Security**: AES encryption with environment-based keys

3. **PAT from Environment Variables** 🌍
   - **Variables**: `DATABRICKS_TOKEN` or `DATABRICKS_API_KEY`
   - **Use Case**: Development and simple deployments
   - **Fallback**: When OBO and database PATs are unavailable

#### Security Enhancements:
- **Query Filtering**: `src/backend/src/engines/crewai/tools/custom/databricks_custom_tool.py`
- **Audit Logging**: All authentication attempts and query executions logged
- **Admin Override**: Configurable security bypass for administrative operations

### 2. Memory Architecture

Kasal implements a sophisticated multi-tier memory system for persistent agent knowledge:

#### Memory Types:

**Short-Term Memory** 
- **Purpose**: Recent conversation context and immediate task memory
- **Retention**: Session-based, cleared between major task transitions
- **Location**: `src/backend/src/engines/crewai/memory/`
- **Vector Index**: `{catalog}.{schema}.short_term_memory_{unique_id}`

**Long-Term Memory** 
- **Purpose**: Persistent knowledge across sessions and conversations
- **Retention**: Permanent until explicitly cleared
- **Use Cases**: Learned patterns, user preferences, domain knowledge
- **Vector Index**: `{catalog}.{schema}.long_term_memory_{unique_id}`

**Entity Memory**
- **Purpose**: Information about people, organizations, and key entities in results
- **Features**: Relationship mapping, attribute tracking
- **Vector Index**: `{catalog}.{schema}.entity_memory_{unique_id}`

#### Group Isolation:
```python
# Memory is isolated by group_id ensuring tenant separation
crew_id = hash(agent_roles + task_names + crew_name + model + group_id)
```

**Implementation Details:**
- **Vector Storage**: Databricks Vector Search with Direct Access indexes
- **Schema Management**: `src/backend/src/schemas/databricks_index_schemas.py`
- **Memory Backend**: `src/backend/src/engines/crewai/memory/databricks_vector_storage.py`

### 3. Agent Workflow Components

#### Plans, Tasks & Agents - Entry Point to Agentic AI

**Plans**
- **Definition**: High-level objectives defining what needs to be accomplished
- **Components**: Goal description, success criteria, resource requirements
- **Location**: `src/frontend/src/components/Plans/`

**Tasks**
- **Definition**: Specific, actionable steps within a plan
- **Properties**: Description, expected output, tools required, agent assignment
- **Dependencies**: Task ordering and conditional execution
- **Location**: `src/backend/src/models/task.py`

**Agents**
- **Definition**: AI entities with specific roles, capabilities, and personalities
- **Configuration**: Role definition, tool access, model selection, behavioral parameters
- **Types**: Researcher, Analyst, Writer, Coordinator, etc.
- **Location**: `src/backend/src/models/agent.py`

#### Workflow Execution:
```
Plan → Task Breakdown → Agent Assignment → Tool Selection → Execution → Memory Storage
```
**Frontend Responsibilities**:
- **Plan** - UI for creating/editing high-level objectives (`src/frontend/src/components/Plans/`)
- **Task Breakdown** - Visual task designer with dependency management (`src/frontend/src/components/Tasks/`)
- **Agent Assignment** - Agent configuration wizard and role assignment (`src/frontend/src/components/Agents/`)
- **Tool Selection** - Tool picker interface and configuration dialogs (`src/frontend/src/components/Tools/`)

**Backend Responsibilities**:
- **Execution** - CrewAI orchestration, agent coordination, background processing (`src/backend/src/engines/crewai/`)
- **Memory Storage** - Vector search operations, persistence to Databricks indexes (`src/backend/src/repositories/databricks_vector_*`)

**Shared Responsibilities**:
- **Real-time Monitoring** - Frontend displays execution progress via WebSocket, backend streams execution events
- **Configuration Validation** - Frontend validates UI inputs, backend validates execution parameters
- **State Synchronization** - Frontend manages UI state, backend persists workflow configurations to database

The frontend handles all configuration and visualization, while the backend handles all execution and persistence.


### 4. Database Schema (app.db)

The SQLite database (`app.db`) contains several key tables for system operation:

#### Core Tables:
The below list contains the most important components, but doesn't comprise a full list. The key idea is to get an overview of the architectural setup of the key database configurations.

**execution_logs**
- **Purpose**: Detailed logs of background execution processes
- **Location**: `src/backend/src/models/execution_log.py`
- **Fields**: `execution_id`, `timestamp`, `level`, `message`, `context`

**execution_trace**
- **Purpose**: Timeline tracking of API requests and system traces
- **Location**: `src/backend/src/models/execution_trace.py`
- **Fields**: `trace_id`, `span_id`, `operation`, `duration`, `metadata`

**chat_history**
- **Purpose**: Conversation history between users and agents
- **Location**: `src/backend/src/models/chat_history.py`
- **Fields**: `session_id`, `user_id`, `message`, `response`, `timestamp`

**crews**
- **Purpose**: Historical crew configurations created by users/groups
- **Location**: `src/backend/src/models/crew.py`
- **Fields**: `crew_id`, `name`, `agents`, `tasks`, `configuration`, `created_by`

**execution_history**
- **Purpose**: Housekeeping table for execution metadata and cleanup
- **Location**: `src/backend/src/models/execution_history.py`
- **Fields**: `execution_id`, `status`, `start_time`, `end_time`, `resource_usage`

**memory_backend**
- **Purpose**: Configuration for different memory storage backends
- **Location**: `src/backend/src/models/memory_backend.py`
- **Fields**: `backend_id`, `type`, `configuration`, `group_id`, `enabled`

**users**
- **Purpose**: User account and profile information
- **Location**: `src/backend/src/models/user.py`
- **Fields**: `user_id`, `email`, `groups`, `preferences`, `permissions`

## Technology Stack

### Frontend
- **Framework**: React 18 with TypeScript
- **UI Library**: Material-UI (MUI)
- **Workflow Visualization**: ReactFlow
- **State Management**: React Context + Hooks
- **Build Tool**: Create React App with custom configurations

### Backend
- **Framework**: FastAPI
- **ORM**: SQLAlchemy 2.0 with Alembic migrations
- **AI Engine**: CrewAI framework for agent orchestration
- **Database**: SQLite (development) / PostgreSQL (production)
- **Authentication**: JWT tokens with Databricks OAuth/OBO

### External Integrations
- **Databricks Vector Search**: Enterprise vector storage for memory
- **Databricks Model Serving**: LLM inference endpoints
- **MLflow**: Model tracking and versioning
- **Unity Catalog**: Data governance and lineage
- **Databricks Volumes**: File storage and management

## Key File Locations

### Authentication & Security
- `src/backend/src/repositories/databricks_auth_helper.py` - Authentication hierarchy
- `src/backend/src/engines/crewai/tools/custom/databricks_custom_tool.py` - SQL security filtering
- `src/backend/src/services/api_keys_service.py` - Encrypted token management

### Memory System
- `src/backend/src/engines/crewai/memory/databricks_vector_storage.py` - Vector memory implementation
- `src/backend/src/schemas/databricks_index_schemas.py` - Memory schema definitions
- `src/backend/src/services/memory_backend_service.py` - Memory configuration management

### Core Workflow
- `src/backend/src/engines/crewai/crewai_engine_service.py` - Main orchestration service
- `src/backend/src/engines/crewai/execution_runner.py` - Async execution management
- `src/backend/src/engines/crewai/tools/tool_factory.py` - Dynamic tool creation

### Frontend Components
- `src/frontend/src/components/Plans/` - Plan management interface
- `src/frontend/src/components/Agents/` - Agent configuration UI
- `src/frontend/src/components/MemoryBackend/` - Memory backend configuration

## CrewAI Engine Integration Details

### Multi-Agent Orchestration Framework

**CrewAI Engine Service**
- **Location**: `src/backend/src/engines/crewai/crewai_engine_service.py`
- **Purpose**: Main orchestration service for multi-agent workflows
- **Key Features**: Agent coordination, task delegation, conversation management
- **Configuration**: Dynamic agent and task configuration from frontend UI

**Configuration Adapter**
- **Location**: `src/backend/src/engines/crewai/configuration_adapter.py`
- **Purpose**: Transforms frontend configurations to CrewAI framework format
- **Responsibilities**: Schema validation, model mapping, tool assignment

**Execution Runner**
- **Location**: `src/backend/src/engines/crewai/execution_runner.py`
- **Purpose**: Manages async execution workflows with progress tracking
- **Features**: Background processing, real-time status updates, error handling

### Agent Types and Roles:
- **Researcher**: Information gathering and analysis
- **Writer**: Content generation and documentation
- **Analyst**: Data processing and insights
- **Coordinator**: Task orchestration and workflow management

## Tool System & MCP Integration

### Dynamic Tool Factory
**Tool Factory**
- **Location**: `src/backend/src/engines/crewai/tools/tool_factory.py`
- **Purpose**: Extensible tool system with dynamic instantiation
- **Architecture**: Plugin-based tool discovery and configuration

**Custom Tools**
- **Databricks Custom Tool**: `src/backend/src/engines/crewai/tools/custom/databricks_custom_tool.py`
  - SQL query execution with security filtering
  - Vector search operations
  - Data manipulation and analysis
- **MCP Tools**: Model Context Protocol integration for external tool systems

### Tool Categories:
1. **Data Tools**: SQL querying, vector search, data transformation
2. **Analysis Tools**: Statistical analysis, visualization, reporting
3. **Communication Tools**: External API calls, notifications, integrations
4. **File Tools**: Document processing, file operations, content management

## Streaming & Real-time Features

### Execution Streaming
**Background Execution**
- **Location**: `src/backend/src/services/execution_service.py`
- **Purpose**: Async task execution with real-time progress streaming
- **Features**: WebSocket updates, progress tracking, cancellation support

**Trace Collection** 
- **Location**: `src/backend/src/models/execution_trace.py`
- **Purpose**: Comprehensive execution timeline and performance metrics
- **Data**: Request/response cycles, tool usage, agent interactions

### Real-time Updates:
- **Execution Progress**: Live updates of task completion status
- **Agent Communications**: Real-time agent-to-agent message flow
- **Tool Usage**: Live monitoring of tool invocations and results

## Configuration Management

### Model Configuration
**Model Support** 
- **Location**: `src/backend/src/seeds/model_configs.py`
- **Providers**: Databricks, OpenAI, Anthropic, Meta, Google
- **Configuration**: Temperature, context window, max tokens, provider-specific settings

**API Keys Management** 
- **Location**: `src/backend/src/services/api_keys_service.py`
- **Security**: AES encryption with environment-based keys
- **Rotation**: Support for token rotation and expiration handling

### Environment Configuration:
```bash
# Databricks Authentication
DATABRICKS_TOKEN=dapi-xxx           # Personal Access Token
DATABRICKS_CLIENT_ID=xxx            # OAuth client ID
DATABRICKS_CLIENT_SECRET=xxx        # OAuth client secret
DATABRICKS_host=https//:-xxx        # Workspace ID

# Vector Search
DATABRICKS_VECTOR_SEARCH_ENDPOINT=https://xxx.databricks.com

# Model Serving
DATABRICKS_MODEL_SERVING_ENDPOINT=https://xxx.databricks.com
```

## Background Task Processing

### Async Execution Architecture
**Execution Management** 
- **Pattern**: FastAPI BackgroundTasks for non-blocking operations
- **Monitoring**: Real-time status tracking with WebSocket updates
- **Scalability**: Horizontal scaling with shared database state

**Task Queue Features**:
- **Priority Scheduling**: High-priority tasks execute first
- **Failure Recovery**: Automatic retry with exponential backoff
- **Resource Management**: CPU and memory usage monitoring
- **Cancellation**: Graceful task cancellation and cleanup

### Process Isolation:
- **Memory Isolation**: Each execution runs in isolated context
- **Group Isolation**: Complete tenant separation for multi-user environments
- **Resource Limits**: Configurable execution timeouts and resource constraints

## Logging & Monitoring System

### Comprehensive Audit Trail
**Execution Logs**
- **Location**: `src/backend/src/models/execution_log.py`
- **Purpose**: Detailed logs of all background processes and agent activities
- **Retention**: Configurable log retention with automatic cleanup

**Security Audit**
- **Location**: `src/backend/src/engines/crewai/tools/custom/databricks_custom_tool.py`
- **Purpose**: Complete audit trail of authentication attempts and query executions
- **Compliance**: GDPR and SOX compliance features

### Monitoring Features:
- **Performance Metrics**: Execution duration, resource usage, success rates
- **Error Tracking**: Comprehensive error logging with stack traces
- **Security Events**: Authentication failures, unauthorized access attempts
- **Usage Analytics**: Tool usage patterns, agent performance metrics

## API Design & Versioning

### RESTful API Architecture
**API Structure**
- **Base URL**: `/api/v1/`
- **Authentication**: JWT Bearer tokens with refresh capability
- **Documentation**: Auto-generated OpenAPI/Swagger documentation
- **Validation**: Pydantic schemas for request/response validation

### Endpoint Categories:
1. **Authentication**: `/api/v1/auth/` - Login, logout, token refresh
2. **Crews**: `/api/v1/crews/` - CRUD operations for crew configurations
3. **Memory**: `/api/v1/memory/` - Memory backend management
4. **Execution**: `/api/v1/execution/` - Task execution and monitoring
5. **Tools**: `/api/v1/tools/` - Tool discovery and configuration

### API Versioning Strategy:
- **Semantic Versioning**: Major.Minor.Patch format
- **Backward Compatibility**: Maintained for at least 2 major versions
- **Deprecation Policy**: 6-month notice for breaking changes

## Performance & Scalability

### Architecture Scalability
**Horizontal Scaling**
- **Stateless Design**: All application state stored in database
- **Database Scaling**: SQLite for development, PostgreSQL for production
- **Memory Scaling**: Distributed vector storage with Databricks Vector Search

**Performance Optimizations**:
- **Async I/O**: Non-blocking operations throughout the stack
- **Connection Pooling**: Efficient database connection management
- **Caching Strategy**: In-memory caching for frequently accessed data
- **Background Processing**: CPU-intensive tasks executed asynchronously

### Load Balancing:
- **API Gateway**: Multiple FastAPI instances behind load balancer
- **Database Sharding**: Group-based data partitioning for tenant isolation
- **Vector Search Scaling**: Databricks handles vector index scaling automatically

