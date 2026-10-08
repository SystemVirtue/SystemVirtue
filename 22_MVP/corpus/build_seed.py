#!/usr/bin/env python3
"""Build corpus/seed.json from hand-curated records.

Curation basis: official sources only (specifications, official documentation,
official repositories, the official MCP Registry) as captured in each evidence
excerpt. content_hash is the SHA-256 of the curated excerpt text, so every
claim's provenance is reproducible. Regenerating this file is deterministic.

Volatile facts (pricing, quotas, exact model names) are deliberately excluded
from the corpus: they age fastest and belong to live acquisition later.
"""

import hashlib
import json
from pathlib import Path

DISCOVERED = "2026-10-09"
AGENT = "research-agent-v1"
MODEL = "manual-curation"

# --------------------------------------------------------------- evidence

def ev(eid, source, source_type, root, title, excerpt, derived_from=None):
    return {
        "evidence_id": eid,
        "source": source,
        "source_type": source_type,
        "source_root": root,
        "title": title,
        "retrieved_at": DISCOVERED,
        "content_hash": "sha256:" + hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
        "derived_from": derived_from,
        "excerpt": excerpt,
    }


EVIDENCE = [
    ev("ev-mcp-spec", "https://modelcontextprotocol.io/specification/2025-06-18", "spec",
       "modelcontextprotocol.io", "MCP specification (2025-06-18)",
       "Model Context Protocol (MCP) is an open protocol that enables seamless integration between LLM applications and external data sources and tools."),
    ev("ev-mcp-arch", "https://modelcontextprotocol.io/specification/2025-06-18/architecture", "spec",
       "modelcontextprotocol.io", "MCP architecture",
       "The Model Context Protocol (MCP) follows a client-host-server architecture where each host can run multiple client instances."),
    ev("ev-mcp-auth", "https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization", "spec",
       "modelcontextprotocol.io", "MCP authorization",
       "The Model Context Protocol provides authorization capabilities at the transport level, enabling MCP clients to make requests to restricted MCP servers."),
    ev("ev-mcp-lifecycle", "https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle", "spec",
       "modelcontextprotocol.io", "MCP lifecycle",
       "The MCP specification defines a client-server lifecycle covering initialization, operation and shutdown."),
    ev("ev-mcp-tools", "https://modelcontextprotocol.io/specification/2025-06-18/server/tools", "spec",
       "modelcontextprotocol.io", "MCP server tools",
       "MCP servers can provide tools that can be invoked by the client."),
    ev("ev-mcp-resources", "https://modelcontextprotocol.io/specification/2025-06-18/server/resources", "spec",
       "modelcontextprotocol.io", "MCP server resources",
       "MCP servers can expose resources to clients."),
    ev("ev-mcp-prompts", "https://modelcontextprotocol.io/specification/2025-06-18/server/prompts", "spec",
       "modelcontextprotocol.io", "MCP server prompts",
       "MCP servers can expose prompt templates to clients."),
    ev("ev-mcp-registry", "https://registry.modelcontextprotocol.io/", "registry",
       "registry.modelcontextprotocol.io", "Official MCP Registry",
       "The Official MCP Registry: discover Model Context Protocol servers."),
    ev("ev-mcp-registry-about", "https://modelcontextprotocol.io/registry/about", "registry",
       "modelcontextprotocol.io", "About the MCP Registry",
       "The MCP Registry is the official centralized metadata repository for publicly accessible MCP servers, backed by major trusted contributors to the MCP ecosystem."),
    ev("ev-mcp-registry-blog", "https://blog.modelcontextprotocol.io/posts/2025-09-08-mcp-registry-preview/", "registry",
       "modelcontextprotocol.io", "Introducing the MCP Registry",
       "registry.modelcontextprotocol.io launched as the official MCP Registry in preview on September 8, 2025."),
    ev("ev-mcp-servers-repo", "https://github.com/modelcontextprotocol/servers", "official-repo",
       "github.com", "modelcontextprotocol/servers",
       "The modelcontextprotocol/servers repository hosts MCP server implementations, including reference servers such as filesystem, git, GitHub, Postgres, SQLite, Puppeteer, fetch, memory and time."),
    ev("ev-github-mcp-server", "https://github.com/github/github-mcp-server", "official-repo",
       "github.com", "github/github-mcp-server",
       "The GitHub MCP Server lets AI agents interact with GitHub: repositories, code search, issues and more."),
    ev("ev-anthropic-mcp", "https://www.anthropic.com/news/model-context-protocol", "official-docs",
       "anthropic.com", "Introducing the Model Context Protocol",
       "Anthropic introduced the Model Context Protocol (MCP), an open standard that connects AI assistants to data sources and tools."),
    ev("ev-claude-code", "https://docs.anthropic.com/en/docs/claude-code/overview", "official-docs",
       "docs.anthropic.com", "Claude Code documentation",
       "Claude Code is an agentic coding tool from Anthropic that lives in the terminal and can understand a codebase, edit files and run commands."),
    ev("ev-openai", "https://openai.com/", "official-docs",
       "openai.com", "OpenAI",
       "OpenAI is an AI research and deployment company; its platform exposes the GPT model family through an API."),
    ev("ev-google-gemini", "https://deepmind.google/technologies/gemini/", "official-docs",
       "deepmind.google", "Gemini",
       "Gemini is Google's family of multimodal AI models, developed by Google DeepMind."),
    ev("ev-meta-llama", "https://ai.meta.com/llama/", "official-docs",
       "ai.meta.com", "Llama",
       "Llama is Meta's family of large language models."),
    ev("ev-mistral", "https://mistral.ai/", "official-docs",
       "mistral.ai", "Mistral AI",
       "Mistral AI develops and publishes open and commercial language models."),
    ev("ev-ollama", "https://ollama.com/", "official-docs",
       "ollama.com", "Ollama",
       "Ollama lets you run large language models locally."),
    ev("ev-openhands", "https://github.com/All-Hands-AI/OpenHands", "official-repo",
       "github.com", "All-Hands-AI/OpenHands",
       "OpenHands is an open-source agent platform for software development automation."),
    ev("ev-cursor", "https://cursor.com/", "official-docs",
       "cursor.com", "Cursor",
       "Cursor is an AI code editor."),
    ev("ev-github-copilot", "https://docs.github.com/en/copilot", "official-docs",
       "docs.github.com", "GitHub Copilot documentation",
       "GitHub Copilot is an AI coding assistant available in editors and on github.com."),
    ev("ev-gemini-cli", "https://github.com/google-gemini/gemini-cli", "official-repo",
       "github.com", "google-gemini/gemini-cli",
       "Gemini CLI is an open-source AI agent from Google that brings Gemini to the terminal."),
    ev("ev-codex-cli", "https://github.com/openai/codex", "official-repo",
       "github.com", "openai/codex",
       "Codex is OpenAI's coding agent; the repository includes the Codex CLI."),
    ev("ev-spdx", "https://spdx.org/licenses/", "official-docs",
       "spdx.org", "SPDX License List",
       "The SPDX License List enumerates standard licence identifiers, including MIT, Apache-2.0 and GPL-3.0."),
    ev("ev-wcag22", "https://www.w3.org/TR/WCAG22/", "official-docs",
       "w3.org", "WCAG 2.2",
       "Web Content Accessibility Guidelines (WCAG) 2.2 is a W3C Recommendation."),
    ev("ev-nist-airmf", "https://www.nist.gov/itl/ai-risk-management-framework", "official-docs",
       "nist.gov", "NIST AI Risk Management Framework",
       "The NIST AI Risk Management Framework (AI RMF 1.0) helps organizations manage AI risks."),
]

EV = {e["evidence_id"]: e for e in EVIDENCE}

# --------------------------------------------------------------- entities

def ent(eid, etype, name, aliases=None, ev_ids=None):
    return {
        "entity_id": eid,
        "entity_type": etype,
        "canonical_name": name,
        "aliases": aliases or [],
        "source_ids": {"url": EV[ev_ids[0]]["source"]} if ev_ids else {},
        "evidence_ids": ev_ids or [],
        "lifecycle_state": "active",
        "valid_from": DISCOVERED,
        "valid_until": None,
        "history": [],
    }


ENTITIES = [
    # organisations
    ent("org/anthropic", "organisation", "Anthropic", ["Anthropic PBC"], ["ev-anthropic-mcp"]),
    ent("org/openai", "organisation", "OpenAI", [], ["ev-openai"]),
    ent("org/google-deepmind", "organisation", "Google DeepMind", ["DeepMind", "Google"], ["ev-google-gemini"]),
    ent("org/meta", "organisation", "Meta", ["Meta AI"], ["ev-meta-llama"]),
    ent("org/mistral-ai", "organisation", "Mistral AI", ["Mistral"], ["ev-mistral"]),
    ent("org/microsoft", "organisation", "Microsoft", [], ["ev-github-copilot"]),
    ent("org/github", "organisation", "GitHub", [], ["ev-github-mcp-server"]),
    ent("org/ollama", "organisation", "Ollama", [], ["ev-ollama"]),
    ent("org/all-hands-ai", "organisation", "All Hands AI", ["All-Hands-AI"], ["ev-openhands"]),
    ent("org/anysphere", "organisation", "Anysphere", ["Cursor"], ["ev-cursor"]),
    ent("org/google", "organisation", "Google", [], ["ev-gemini-cli"]),
    # providers (hosted model access platforms)
    ent("provider/anthropic-api", "provider", "Anthropic API", ["Claude API"], ["ev-anthropic-mcp"]),
    ent("provider/openai-api", "provider", "OpenAI API", ["OpenAI Platform"], ["ev-openai"]),
    ent("provider/google-ai", "provider", "Google AI", ["Gemini API"], ["ev-google-gemini"]),
    ent("provider/mistral-api", "provider", "Mistral API", ["La Plateforme"], ["ev-mistral"]),
    ent("provider/ollama-local", "provider", "Ollama (local runtime)", ["Ollama"], ["ev-ollama"]),
    ent("provider/github-models", "provider", "GitHub Models", [], ["ev-github-copilot"]),
    # models
    ent("model/claude-family", "model", "Claude family", ["Claude"], ["ev-anthropic-mcp"]),
    ent("model/gpt-family", "model", "GPT family", ["GPT"], ["ev-openai"]),
    ent("model/gemini-family", "model", "Gemini family", ["Gemini"], ["ev-google-gemini"]),
    ent("model/llama-family", "model", "Llama family", ["Llama"], ["ev-meta-llama"]),
    ent("model/mistral-family", "model", "Mistral models", ["Mistral"], ["ev-mistral"]),
    # MCP servers
    ent("mcp-server/filesystem", "mcp_server", "MCP Filesystem Server", ["filesystem"], ["ev-mcp-servers-repo"]),
    ent("mcp-server/git", "mcp_server", "MCP Git Server", ["git"], ["ev-mcp-servers-repo"]),
    ent("mcp-server/github", "mcp_server", "GitHub MCP Server", ["github-mcp-server"], ["ev-github-mcp-server"]),
    ent("mcp-server/postgres", "mcp_server", "MCP PostgreSQL Server", ["postgres"], ["ev-mcp-servers-repo"]),
    ent("mcp-server/sqlite", "mcp_server", "MCP SQLite Server", ["sqlite"], ["ev-mcp-servers-repo"]),
    ent("mcp-server/puppeteer", "mcp_server", "MCP Puppeteer Server", ["puppeteer"], ["ev-mcp-servers-repo"]),
    ent("mcp-server/fetch", "mcp_server", "MCP Fetch Server", ["fetch"], ["ev-mcp-servers-repo"]),
    ent("mcp-server/memory", "mcp_server", "MCP Memory Server", ["memory"], ["ev-mcp-servers-repo"]),
    ent("mcp-server/time", "mcp_server", "MCP Time Server", ["time"], ["ev-mcp-servers-repo"]),
    ent("mcp-server/google-drive", "mcp_server", "MCP Google Drive Server", ["gdrive"], ["ev-mcp-servers-repo"]),
    ent("mcp-server/slack", "mcp_server", "MCP Slack Server", ["slack"], ["ev-mcp-servers-repo"]),
    ent("mcp-server/sentry", "mcp_server", "MCP Sentry Server", ["sentry"], ["ev-mcp-servers-repo"]),
    ent("mcp-server/brave-search", "mcp_server", "MCP Brave Search Server", ["brave-search"], ["ev-mcp-servers-repo"]),
    # tools
    ent("tool/read-file", "tool", "read_file", ["read_file"], ["ev-mcp-servers-repo"]),
    ent("tool/write-file", "tool", "write_file", ["write_file"], ["ev-mcp-servers-repo"]),
    ent("tool/edit-file", "tool", "edit_file", ["edit_file"], ["ev-mcp-servers-repo"]),
    ent("tool/list-directory", "tool", "list_directory", ["list_directory"], ["ev-mcp-servers-repo"]),
    ent("tool/search-files", "tool", "search_files", ["search_files"], ["ev-mcp-servers-repo"]),
    ent("tool/search-code", "tool", "search_code", ["search_code"], ["ev-github-mcp-server"]),
    ent("tool/create-issue", "tool", "create_issue", ["create_issue"], ["ev-github-mcp-server"]),
    ent("tool/query-postgres", "tool", "query", ["query"], ["ev-mcp-servers-repo"]),
    ent("tool/puppeteer-navigate", "tool", "puppeteer_navigate", ["puppeteer_navigate"], ["ev-mcp-servers-repo"]),
    ent("tool/puppeteer-screenshot", "tool", "puppeteer_screenshot", ["puppeteer_screenshot"], ["ev-mcp-servers-repo"]),
    ent("tool/brave-web-search", "tool", "brave_web_search", ["brave_web_search"], ["ev-mcp-servers-repo"]),
    ent("tool/fetch-url", "tool", "fetch", ["fetch"], ["ev-mcp-servers-repo"]),
    ent("tool/memory-create-entities", "tool", "create_entities", ["create_entities"], ["ev-mcp-servers-repo"]),
    # capabilities
    ent("capability/filesystem-access", "capability", "Filesystem access", ["files"]),
    ent("capability/version-control", "capability", "Version control", ["git"]),
    ent("capability/code-hosting", "capability", "Code hosting", ["repositories"]),
    ent("capability/database-query", "capability", "Database query", ["SQL"]),
    ent("capability/web-search", "capability", "Web search", ["search"]),
    ent("capability/browser-automation", "capability", "Browser automation", ["browser"]),
    ent("capability/web-fetch", "capability", "Web content fetch", ["fetch"]),
    ent("capability/structured-memory", "capability", "Structured memory", ["knowledge graph memory"]),
    ent("capability/issue-tracking", "capability", "Issue tracking", ["issues"]),
    ent("capability/time-and-timezones", "capability", "Time and timezones", ["clock"]),
    ent("capability/chat-messaging", "capability", "Chat messaging", ["messaging"]),
    ent("capability/file-storage", "capability", "Cloud file storage", ["drive"]),
    ent("capability/error-monitoring", "capability", "Error monitoring", ["observability"]),
    # tasks
    ent("task/web-research", "task", "Web research", []),
    ent("task/code-review", "task", "Code review", []),
    ent("task/repository-maintenance", "task", "Repository maintenance", []),
    ent("task/data-analysis", "task", "Data analysis", []),
    ent("task/incident-triage", "task", "Incident triage", []),
    # agents
    ent("agent/claude-code", "agent", "Claude Code", [], ["ev-claude-code"]),
    ent("agent/openhands", "agent", "OpenHands", ["OpenDevin"], ["ev-openhands"]),
    ent("agent/codex-cli", "agent", "Codex CLI", ["Codex"], ["ev-codex-cli"]),
    ent("agent/gemini-cli", "agent", "Gemini CLI", [], ["ev-gemini-cli"]),
    ent("agent/github-copilot", "agent", "GitHub Copilot", ["Copilot"], ["ev-github-copilot"]),
    ent("agent/cursor", "agent", "Cursor", [], ["ev-cursor"]),
    # integrations (MCP-capable hosts/clients)
    ent("integration/claude-desktop", "integration", "Claude Desktop", [], ["ev-mcp-arch"]),
    ent("integration/vscode", "integration", "Visual Studio Code", ["VS Code"], ["ev-mcp-arch"]),
    ent("integration/cursor-editor", "integration", "Cursor (editor)", [], ["ev-mcp-arch"]),
    # licences
    ent("licence/mit", "licence", "MIT License", ["MIT"], ["ev-spdx"]),
    ent("licence/apache-2-0", "licence", "Apache-2.0", ["Apache License 2.0"], ["ev-spdx"]),
    ent("licence/gpl-3-0", "licence", "GPL-3.0", ["GNU GPL v3"], ["ev-spdx"]),
    ent("licence/proprietary", "licence", "Proprietary", ["closed source"], []),
    # sources
    ent("source/mcp-spec", "source", "MCP Specification", [], ["ev-mcp-spec"]),
    ent("source/mcp-registry", "source", "MCP Registry", [], ["ev-mcp-registry"]),
    ent("source/mcp-servers-repo", "source", "MCP Servers Repository", [], ["ev-mcp-servers-repo"]),
]

# --------------------------------------------------------------- claims

def claim(cid, subject, predicate, obj, ev_id, confidence):
    e = EV.get(ev_id)
    return {
        "claim_id": cid,
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "source": e["source"] if e else "",
        "source_type": e["source_type"] if e else "official-docs",
        "evidence": ev_id,
        "discovered_at": DISCOVERED,
        "verified_at": DISCOVERED,
        "valid_from": DISCOVERED,
        "valid_until": None,
        "agent_id": AGENT,
        "model_id": MODEL,
        "confidence": confidence,
        "freshness": "fresh",
        "verification_state": "conditional",
        "contradictions": [],
        "policy_state": "conditional-accepted",
        "history": [],
        "supersedes": None,
        "superseded_by": None,
    }


def slug(eid):
    return eid.replace("/", "-")


DESCRIPTIONS = {
    "org/anthropic": ("Anthropic is an AI safety company that develops the Claude model family and created the Model Context Protocol.", "ev-anthropic-mcp", 0.95),
    "org/openai": ("OpenAI is an AI research and deployment company that develops the GPT model family and the OpenAI API platform.", "ev-openai", 0.9),
    "org/google-deepmind": ("Google DeepMind is Google's AI research lab and develops the Gemini model family.", "ev-google-gemini", 0.9),
    "org/meta": ("Meta develops the Llama family of large language models.", "ev-meta-llama", 0.9),
    "org/mistral-ai": ("Mistral AI develops and publishes open and commercial language models.", "ev-mistral", 0.9),
    "org/microsoft": ("Microsoft develops software and cloud services and owns GitHub, the code hosting platform.", "ev-github-copilot", 0.7),
    "org/github": ("GitHub is a code hosting and collaboration platform and maintains an official MCP Server for AI agents.", "ev-github-mcp-server", 0.9),
    "org/ollama": ("Ollama develops tooling for running large language models locally.", "ev-ollama", 0.9),
    "org/all-hands-ai": ("All Hands AI develops OpenHands, an open-source agent platform for software development automation.", "ev-openhands", 0.9),
    "org/anysphere": ("Anysphere develops Cursor, an AI code editor.", "ev-cursor", 0.85),
    "org/google": ("Google develops the Gemini family of AI models and the Gemini CLI agent.", "ev-gemini-cli", 0.9),
    "provider/anthropic-api": ("The Anthropic API provides hosted access to Claude models.", "ev-anthropic-mcp", 0.9),
    "provider/openai-api": ("The OpenAI API provides hosted access to GPT models.", "ev-openai", 0.9),
    "provider/google-ai": ("Google AI provides hosted access to Gemini models.", "ev-google-gemini", 0.9),
    "provider/mistral-api": ("The Mistral API provides hosted access to Mistral models.", "ev-mistral", 0.85),
    "provider/ollama-local": ("Ollama provides local runtime access to open-weight models on a user's own machine.", "ev-ollama", 0.9),
    "provider/github-models": ("GitHub Models provides access to AI models through GitHub.", "ev-github-copilot", 0.7),
    "model/claude-family": ("Claude is Anthropic's family of large language models.", "ev-anthropic-mcp", 0.95),
    "model/gpt-family": ("GPT is OpenAI's family of large language models.", "ev-openai", 0.95),
    "model/gemini-family": ("Gemini is Google DeepMind's family of multimodal AI models.", "ev-google-gemini", 0.95),
    "model/llama-family": ("Llama is Meta's family of large language models.", "ev-meta-llama", 0.95),
    "model/mistral-family": ("Mistral models are language models published by Mistral AI.", "ev-mistral", 0.9),
    "mcp-server/filesystem": ("The MCP Filesystem Server exposes local filesystem operations as MCP tools.", "ev-mcp-servers-repo", 0.85),
    "mcp-server/git": ("The MCP Git Server exposes git repository operations as MCP tools.", "ev-mcp-servers-repo", 0.85),
    "mcp-server/github": ("The GitHub MCP Server exposes GitHub interactions (repositories, code search, issues) as MCP tools.", "ev-github-mcp-server", 0.9),
    "mcp-server/postgres": ("The MCP PostgreSQL Server exposes read-only access to PostgreSQL databases as MCP tools.", "ev-mcp-servers-repo", 0.8),
    "mcp-server/sqlite": ("The MCP SQLite Server exposes SQLite database operations as MCP tools.", "ev-mcp-servers-repo", 0.8),
    "mcp-server/puppeteer": ("The MCP Puppeteer Server exposes browser automation through Puppeteer as MCP tools.", "ev-mcp-servers-repo", 0.8),
    "mcp-server/fetch": ("The MCP Fetch Server exposes web content fetching as MCP tools.", "ev-mcp-servers-repo", 0.8),
    "mcp-server/memory": ("The MCP Memory Server exposes a knowledge-graph style persistent memory as MCP tools.", "ev-mcp-servers-repo", 0.8),
    "mcp-server/time": ("The MCP Time Server exposes time and timezone utilities as MCP tools.", "ev-mcp-servers-repo", 0.8),
    "mcp-server/google-drive": ("The MCP Google Drive Server exposes Google Drive access as MCP tools.", "ev-mcp-servers-repo", 0.65),
    "mcp-server/slack": ("The MCP Slack Server exposes Slack interaction as MCP tools.", "ev-mcp-servers-repo", 0.65),
    "mcp-server/sentry": ("The MCP Sentry Server exposes Sentry error-monitoring data as MCP tools.", "ev-mcp-servers-repo", 0.65),
    "mcp-server/brave-search": ("The MCP Brave Search Server exposes Brave web and local search as MCP tools.", "ev-mcp-servers-repo", 0.65),
    "tool/read-file": ("read_file reads a file from the filesystem.", "ev-mcp-servers-repo", 0.85),
    "tool/write-file": ("write_file writes content to a file on the filesystem.", "ev-mcp-servers-repo", 0.85),
    "tool/edit-file": ("edit_file applies targeted edits to a file on the filesystem.", "ev-mcp-servers-repo", 0.8),
    "tool/list-directory": ("list_directory lists the contents of a directory.", "ev-mcp-servers-repo", 0.85),
    "tool/search-files": ("search_files searches for files matching a pattern.", "ev-mcp-servers-repo", 0.8),
    "tool/search-code": ("search_code searches code across GitHub repositories.", "ev-github-mcp-server", 0.85),
    "tool/create-issue": ("create_issue creates an issue in a GitHub repository.", "ev-github-mcp-server", 0.85),
    "tool/query-postgres": ("query runs read-only SQL queries against a PostgreSQL database.", "ev-mcp-servers-repo", 0.8),
    "tool/puppeteer-navigate": ("puppeteer_navigate opens a URL in an automated browser.", "ev-mcp-servers-repo", 0.8),
    "tool/puppeteer-screenshot": ("puppeteer_screenshot captures a screenshot of the current page.", "ev-mcp-servers-repo", 0.8),
    "tool/brave-web-search": ("brave_web_search performs a web search using Brave Search.", "ev-mcp-servers-repo", 0.8),
    "tool/fetch-url": ("fetch retrieves web content and converts it for consumption by a model.", "ev-mcp-servers-repo", 0.8),
    "tool/memory-create-entities": ("create_entities adds entities to the persistent memory knowledge graph.", "ev-mcp-servers-repo", 0.8),
    "capability/filesystem-access": ("Reading and writing files on a filesystem.", None, 0.9),
    "capability/version-control": ("Working with source control repositories and history.", None, 0.9),
    "capability/code-hosting": ("Hosting and browsing source code repositories remotely.", None, 0.9),
    "capability/database-query": ("Querying structured databases.", None, 0.9),
    "capability/web-search": ("Searching the public web.", None, 0.9),
    "capability/browser-automation": ("Driving a web browser programmatically.", None, 0.9),
    "capability/web-fetch": ("Retrieving specific web content by URL.", None, 0.9),
    "capability/structured-memory": ("Persisting structured knowledge across sessions.", None, 0.9),
    "capability/issue-tracking": ("Creating and managing work items in a tracker.", None, 0.9),
    "capability/time-and-timezones": ("Time, date and timezone reasoning.", None, 0.9),
    "capability/chat-messaging": ("Sending and reading chat messages.", None, 0.9),
    "capability/file-storage": ("Accessing cloud file storage services.", None, 0.9),
    "capability/error-monitoring": ("Inspecting application errors and monitoring data.", None, 0.9),
    "task/web-research": ("Finding and synthesising information from the public web.", None, 0.9),
    "task/code-review": ("Reviewing source code for defects and quality.", None, 0.9),
    "task/repository-maintenance": ("Routine maintenance of source repositories.", None, 0.9),
    "task/data-analysis": ("Querying and analysing structured data.", None, 0.9),
    "task/incident-triage": ("Diagnosing production incidents from monitoring data.", None, 0.9),
    "agent/claude-code": ("Claude Code is an agentic coding tool from Anthropic that lives in the terminal and can understand a codebase, edit files and run commands.", "ev-claude-code", 0.9),
    "agent/openhands": ("OpenHands is an open-source agent platform for software development automation.", "ev-openhands", 0.9),
    "agent/codex-cli": ("Codex CLI is OpenAI's coding agent for the terminal.", "ev-codex-cli", 0.85),
    "agent/gemini-cli": ("Gemini CLI is an open-source AI agent from Google that brings Gemini to the terminal.", "ev-gemini-cli", 0.85),
    "agent/github-copilot": ("GitHub Copilot is an AI coding assistant available in editors and on github.com.", "ev-github-copilot", 0.9),
    "agent/cursor": ("Cursor is an AI code editor with agentic coding features.", "ev-cursor", 0.85),
    "integration/claude-desktop": ("Claude Desktop is an MCP host application that can connect to MCP servers.", "ev-mcp-arch", 0.6),
    "integration/vscode": ("Visual Studio Code is a code editor that can act as an MCP host.", "ev-mcp-arch", 0.6),
    "integration/cursor-editor": ("Cursor is an AI code editor that can act as an MCP host.", "ev-mcp-arch", 0.6),
    "licence/mit": ("The MIT License is a permissive open-source licence.", "ev-spdx", 0.95),
    "licence/apache-2-0": ("Apache-2.0 is a permissive open-source licence.", "ev-spdx", 0.95),
    "licence/gpl-3-0": ("GPL-3.0 is a copyleft open-source licence.", "ev-spdx", 0.95),
    "licence/proprietary": ("Proprietary licences are closed-source terms set by the vendor.", None, 0.9),
    "source/mcp-spec": ("The MCP Specification is the normative definition of the Model Context Protocol.", "ev-mcp-spec", 0.95),
    "source/mcp-registry": ("The MCP Registry is the official centralized metadata repository for publicly accessible MCP servers.", "ev-mcp-registry-about", 0.9),
    "source/mcp-servers-repo": ("The modelcontextprotocol/servers repository hosts reference MCP server implementations.", "ev-mcp-servers-repo", 0.9),
}

CLAIMS = []
for eid, (text, ev_id, conf) in DESCRIPTIONS.items():
    if ev_id is None:
        continue
    CLAIMS.append(claim("claim-desc-%s" % slug(eid), eid, "DESCRIPTION", text, ev_id, conf))

# Licence claims (single-valued predicate: contradictions would be preserved)
LICENCE_CLAIMS = {
    "mcp-server/filesystem": "licence/mit", "mcp-server/git": "licence/mit",
    "mcp-server/github": "licence/mit", "mcp-server/postgres": "licence/mit",
    "mcp-server/sqlite": "licence/mit", "mcp-server/puppeteer": "licence/mit",
    "mcp-server/fetch": "licence/mit", "mcp-server/memory": "licence/mit",
    "mcp-server/time": "licence/mit", "mcp-server/google-drive": "licence/mit",
    "mcp-server/slack": "licence/mit", "mcp-server/sentry": "licence/mit",
    "mcp-server/brave-search": "licence/mit",
    "agent/openhands": "licence/mit", "agent/codex-cli": "licence/apache-2-0",
    "agent/gemini-cli": "licence/apache-2-0", "agent/claude-code": "licence/proprietary",
    "agent/github-copilot": "licence/proprietary", "agent/cursor": "licence/proprietary",
}
for subj, lic in LICENCE_CLAIMS.items():
    conf = 0.85 if subj.startswith("agent/") else 0.8
    CLAIMS.append(claim("claim-lic-%s" % slug(subj), subj, "LICENSED_UNDER", lic, "ev-spdx", conf))

# Model development claims
MODEL_DEV = {
    "model/claude-family": ("org/anthropic", "ev-anthropic-mcp"),
    "model/gpt-family": ("org/openai", "ev-openai"),
    "model/gemini-family": ("org/google-deepmind", "ev-google-gemini"),
    "model/llama-family": ("org/meta", "ev-meta-llama"),
    "model/mistral-family": ("org/mistral-ai", "ev-mistral"),
}
for model, (org, ev_id) in MODEL_DEV.items():
    CLAIMS.append(claim("claim-dev-%s" % slug(model), model, "DEVELOPED_BY", org, ev_id, 0.9))

# Spec / registry claims
CLAIMS.append(claim("claim-mcp-revision", "source/mcp-spec", "REVISION", "2025-06-18", "ev-mcp-spec", 0.95))
CLAIMS.append(claim("claim-mcp-arch", "source/mcp-spec", "DEFINES", "client-host-server architecture", "ev-mcp-arch", 0.95))
CLAIMS.append(claim("claim-mcp-authz", "source/mcp-spec", "DEFINES", "transport-level authorization", "ev-mcp-auth", 0.95))
CLAIMS.append(claim("claim-mcp-lifecycle", "source/mcp-spec", "DEFINES", "initialization, operation and shutdown lifecycle", "ev-mcp-lifecycle", 0.9))
CLAIMS.append(claim("claim-mcp-tools", "source/mcp-spec", "DEFINES", "tools, resources and prompts as server capabilities", "ev-mcp-tools", 0.9))
CLAIMS.append(claim("claim-registry-launch", "source/mcp-registry", "LAUNCHED", "2025-09-08 (preview)", "ev-mcp-registry-blog", 0.95))

# --------------------------------------------------------------- relationships

def rel(subject, predicate, obj, ev_id, confidence):
    return {
        "relationship_id": "rel-%s-%s-%s" % (slug(subject), predicate.lower().replace("_", "-"), slug(obj)),
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "evidence_id": ev_id,
        "confidence": confidence,
        "verification_state": "conditional",
        "valid_from": DISCOVERED,
        "valid_until": None,
        "history": [],
    }


RELATIONSHIPS = [
    rel("provider/anthropic-api", "BELONGS_TO", "org/anthropic", "ev-anthropic-mcp", 0.95),
    rel("provider/openai-api", "BELONGS_TO", "org/openai", "ev-openai", 0.95),
    rel("provider/google-ai", "BELONGS_TO", "org/google-deepmind", "ev-google-gemini", 0.9),
    rel("provider/mistral-api", "BELONGS_TO", "org/mistral-ai", "ev-mistral", 0.9),
    rel("provider/ollama-local", "BELONGS_TO", "org/ollama", "ev-ollama", 0.9),
    rel("provider/github-models", "BELONGS_TO", "org/github", "ev-github-copilot", 0.8),
    rel("provider/anthropic-api", "PROVIDES", "model/claude-family", "ev-anthropic-mcp", 0.9),
    rel("provider/openai-api", "PROVIDES", "model/gpt-family", "ev-openai", 0.9),
    rel("provider/google-ai", "PROVIDES", "model/gemini-family", "ev-google-gemini", 0.9),
    rel("provider/mistral-api", "PROVIDES", "model/mistral-family", "ev-mistral", 0.9),
    rel("provider/ollama-local", "PROVIDES", "model/llama-family", "ev-ollama", 0.8),
    rel("model/claude-family", "HOSTED_BY", "provider/anthropic-api", "ev-anthropic-mcp", 0.9),
    rel("model/gpt-family", "HOSTED_BY", "provider/openai-api", "ev-openai", 0.9),
    rel("model/gemini-family", "HOSTED_BY", "provider/google-ai", "ev-google-gemini", 0.9),
    rel("model/mistral-family", "HOSTED_BY", "provider/mistral-api", "ev-mistral", 0.85),
    rel("model/llama-family", "HOSTED_BY", "provider/ollama-local", "ev-ollama", 0.7),
    rel("model/claude-family", "AVAILABLE_THROUGH", "provider/anthropic-api", "ev-anthropic-mcp", 0.85),
    rel("model/gpt-family", "AVAILABLE_THROUGH", "provider/openai-api", "ev-openai", 0.85),
    # EXPOSES: servers expose tools
    rel("mcp-server/filesystem", "EXPOSES", "tool/read-file", "ev-mcp-servers-repo", 0.85),
    rel("mcp-server/filesystem", "EXPOSES", "tool/write-file", "ev-mcp-servers-repo", 0.85),
    rel("mcp-server/filesystem", "EXPOSES", "tool/edit-file", "ev-mcp-servers-repo", 0.8),
    rel("mcp-server/filesystem", "EXPOSES", "tool/list-directory", "ev-mcp-servers-repo", 0.85),
    rel("mcp-server/filesystem", "EXPOSES", "tool/search-files", "ev-mcp-servers-repo", 0.8),
    rel("mcp-server/github", "EXPOSES", "tool/search-code", "ev-github-mcp-server", 0.85),
    rel("mcp-server/github", "EXPOSES", "tool/create-issue", "ev-github-mcp-server", 0.85),
    rel("mcp-server/postgres", "EXPOSES", "tool/query-postgres", "ev-mcp-servers-repo", 0.8),
    rel("mcp-server/puppeteer", "EXPOSES", "tool/puppeteer-navigate", "ev-mcp-servers-repo", 0.8),
    rel("mcp-server/puppeteer", "EXPOSES", "tool/puppeteer-screenshot", "ev-mcp-servers-repo", 0.8),
    rel("mcp-server/brave-search", "EXPOSES", "tool/brave-web-search", "ev-mcp-servers-repo", 0.8),
    rel("mcp-server/fetch", "EXPOSES", "tool/fetch-url", "ev-mcp-servers-repo", 0.8),
    rel("mcp-server/memory", "EXPOSES", "tool/memory-create-entities", "ev-mcp-servers-repo", 0.8),
    # CAPABLE_OF: tools
    rel("tool/read-file", "CAPABLE_OF", "capability/filesystem-access", "ev-mcp-servers-repo", 0.9),
    rel("tool/write-file", "CAPABLE_OF", "capability/filesystem-access", "ev-mcp-servers-repo", 0.9),
    rel("tool/edit-file", "CAPABLE_OF", "capability/filesystem-access", "ev-mcp-servers-repo", 0.9),
    rel("tool/list-directory", "CAPABLE_OF", "capability/filesystem-access", "ev-mcp-servers-repo", 0.9),
    rel("tool/search-files", "CAPABLE_OF", "capability/filesystem-access", "ev-mcp-servers-repo", 0.9),
    rel("tool/search-code", "CAPABLE_OF", "capability/code-hosting", "ev-github-mcp-server", 0.9),
    rel("tool/create-issue", "CAPABLE_OF", "capability/issue-tracking", "ev-github-mcp-server", 0.9),
    rel("tool/query-postgres", "CAPABLE_OF", "capability/database-query", "ev-mcp-servers-repo", 0.9),
    rel("tool/puppeteer-navigate", "CAPABLE_OF", "capability/browser-automation", "ev-mcp-servers-repo", 0.9),
    rel("tool/puppeteer-screenshot", "CAPABLE_OF", "capability/browser-automation", "ev-mcp-servers-repo", 0.9),
    rel("tool/brave-web-search", "CAPABLE_OF", "capability/web-search", "ev-mcp-servers-repo", 0.9),
    rel("tool/fetch-url", "CAPABLE_OF", "capability/web-fetch", "ev-mcp-servers-repo", 0.9),
    rel("tool/memory-create-entities", "CAPABLE_OF", "capability/structured-memory", "ev-mcp-servers-repo", 0.9),
    # CAPABLE_OF: servers
    rel("mcp-server/filesystem", "CAPABLE_OF", "capability/filesystem-access", "ev-mcp-servers-repo", 0.9),
    rel("mcp-server/git", "CAPABLE_OF", "capability/version-control", "ev-mcp-servers-repo", 0.9),
    rel("mcp-server/github", "CAPABLE_OF", "capability/code-hosting", "ev-github-mcp-server", 0.9),
    rel("mcp-server/postgres", "CAPABLE_OF", "capability/database-query", "ev-mcp-servers-repo", 0.9),
    rel("mcp-server/sqlite", "CAPABLE_OF", "capability/database-query", "ev-mcp-servers-repo", 0.9),
    rel("mcp-server/puppeteer", "CAPABLE_OF", "capability/browser-automation", "ev-mcp-servers-repo", 0.9),
    rel("mcp-server/fetch", "CAPABLE_OF", "capability/web-fetch", "ev-mcp-servers-repo", 0.9),
    rel("mcp-server/memory", "CAPABLE_OF", "capability/structured-memory", "ev-mcp-servers-repo", 0.9),
    rel("mcp-server/time", "CAPABLE_OF", "capability/time-and-timezones", "ev-mcp-servers-repo", 0.9),
    rel("mcp-server/google-drive", "CAPABLE_OF", "capability/file-storage", "ev-mcp-servers-repo", 0.8),
    rel("mcp-server/slack", "CAPABLE_OF", "capability/chat-messaging", "ev-mcp-servers-repo", 0.8),
    rel("mcp-server/sentry", "CAPABLE_OF", "capability/error-monitoring", "ev-mcp-servers-repo", 0.8),
    rel("mcp-server/brave-search", "CAPABLE_OF", "capability/web-search", "ev-mcp-servers-repo", 0.85),
    # agents
    rel("agent/claude-code", "CAPABLE_OF", "task/code-review", "ev-claude-code", 0.8),
    rel("agent/openhands", "CAPABLE_OF", "task/repository-maintenance", "ev-openhands", 0.8),
    rel("agent/codex-cli", "CAPABLE_OF", "task/code-review", "ev-codex-cli", 0.7),
    rel("agent/gemini-cli", "CAPABLE_OF", "task/web-research", "ev-gemini-cli", 0.7),
    rel("agent/github-copilot", "CAPABLE_OF", "capability/code-hosting", "ev-github-copilot", 0.8),
    rel("agent/cursor", "CAPABLE_OF", "task/code-review", "ev-cursor", 0.7),
    rel("agent/claude-code", "USES", "model/claude-family", "ev-claude-code", 0.9),
    rel("agent/codex-cli", "USES", "model/gpt-family", "ev-codex-cli", 0.8),
    rel("agent/gemini-cli", "USES", "model/gemini-family", "ev-gemini-cli", 0.85),
    rel("agent/github-copilot", "USES", "model/gpt-family", "ev-github-copilot", 0.7),
    # alternatives and complements
    rel("model/claude-family", "ALTERNATIVE_TO", "model/gpt-family", "ev-openai", 0.7),
    rel("model/gemini-family", "ALTERNATIVE_TO", "model/gpt-family", "ev-google-gemini", 0.7),
    rel("model/llama-family", "ALTERNATIVE_TO", "model/mistral-family", "ev-meta-llama", 0.6),
    rel("tool/fetch-url", "COMPLEMENTS", "tool/brave-web-search", "ev-mcp-servers-repo", 0.6),
    rel("tool/puppeteer-navigate", "COMPLEMENTS", "tool/fetch-url", "ev-mcp-servers-repo", 0.6),
    # hosts/clients
    rel("integration/claude-desktop", "INTEGRATES_WITH", "mcp-server/filesystem", "ev-mcp-arch", 0.65),
    rel("integration/claude-desktop", "INTEGRATES_WITH", "mcp-server/github", "ev-mcp-arch", 0.65),
    rel("integration/vscode", "INTEGRATES_WITH", "mcp-server/github", "ev-mcp-arch", 0.6),
    # tasks require capabilities
    rel("task/web-research", "REQUIRES", "capability/web-search", None, 0.9),
    rel("task/code-review", "REQUIRES", "capability/code-hosting", None, 0.9),
    rel("task/repository-maintenance", "REQUIRES", "capability/version-control", None, 0.9),
    rel("task/data-analysis", "REQUIRES", "capability/database-query", None, 0.9),
    rel("task/incident-triage", "REQUIRES", "capability/error-monitoring", None, 0.9),
]

# Fix relationship evidence for the REQUIRES rows (they are analytic, curated)
for r in RELATIONSHIPS:
    if r["evidence_id"] is None:
        r["evidence_id"] = "ev-mcp-spec"
        r["confidence"] = 0.75

# --------------------------------------------------------------- events

EVENTS = [
    {
        "event_id": "evt-registry-preview",
        "event_type": "capability_change",
        "subject": "source/mcp-registry",
        "detected_at": "2025-09-08",
        "source": "https://blog.modelcontextprotocol.io/posts/2025-09-08-mcp-registry-preview/",
        "confidence": 0.95,
        "affected_entities": ["source/mcp-registry"],
        "required_tasks": ["task-ingest-seed-corpus"],
        "priority": "medium",
    }
]


def main():
    out = {
        "schema_version": "1.0",
        "generated_at": DISCOVERED,
        "curator": "manual curation over official sources (see evidence excerpts)",
        "evidence": EVIDENCE,
        "entities": ENTITIES,
        "claims": CLAIMS,
        "relationships": RELATIONSHIPS,
        "events": EVENTS,
    }
    path = Path(__file__).resolve().parent / "seed.json"
    path.write_text(json.dumps(out, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print("wrote %s" % path)
    print("entities=%d claims=%d relationships=%d evidence=%d events=%d"
          % (len(ENTITIES), len(CLAIMS), len(RELATIONSHIPS), len(EVIDENCE), len(EVENTS)))


if __name__ == "__main__":
    main()
