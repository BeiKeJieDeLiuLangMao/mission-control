"use client";

export const dynamic = "force-dynamic";

import { useState, useCallback, useEffect } from "react";
import {
  Brain,
  Search,
  Plus,
  Trash2,
  RefreshCw,
  Bot,
  Filter,
  ChevronDown,
  ChevronUp,
  MessageSquare,
  Clock,
  FileText,
  Layers,
  Wrench,
  ClipboardList,
} from "lucide-react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { DashboardShell } from "@/components/templates/DashboardShell";
import { DashboardSidebar } from "@/components/organisms/DashboardSidebar";
import { Button } from "@/components/ui/button";
import { AILearnView } from "@/components/molecules/AILearnView";
import { MemoryGraph } from "@/components/molecules/MemoryGraph";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useAuth } from "@/auth/clerk";
import { useOrganizationMembership } from "@/lib/use-organization-membership";
import { cn } from "@/lib/utils";
import { getApiBaseUrl } from "@/lib/api-base";

// ------ Types ------
interface MemoryItem {
  id: string;
  content: string; // Changed from 'memory' to 'content' to match OpenMemory API
  created_at: number;
  state: string;
  app_name?: string;
  categories: string[];
  metadata__?: Record<string, unknown>; // Qdrant payload metadata
  score?: number; // For search results
  turn_id?: string | null; // 关联的 turn ID
  agent_id?: string; // 顶层 agent_id 字段
  memory_type?: string; // 顶层 memory_type 字段
  source?: string; // 顶层 source 字段（从 turns 表关联获取）
  userId?: string; // Qdrant payload 中的 userId 字段
  agentId?: string; // Qdrant payload 中的 agentId 字段
}

interface SourceInfo {
  source_id: string; // 来源标识: claude-code, openclaw, manual
  label: string; // 显示标签
  count: number;
}

interface MemoryStats {
  total: number;
  by_source: Record<string, number>;
  by_agent: Array<{ agent_id: string; count: number }>;
}

interface AgentInfo {
  agent_id: string;
  count: number;
}

interface ContentBlock {
  type: "text" | "tool_use" | "tool_result";
  text?: string;
  id?: string;
  name?: string;
  input?: unknown;
  tool_use_id?: string;
  content?: string;
}

interface TurnMessage {
  role: string;
  content: string | ContentBlock[];
}

interface TurnDetail {
  id: string;
  session_id: string;
  user_id: string;
  agent_id: string;
  messages: TurnMessage[];
  source: string;
  processing_status: string;
  created_at: string;
}

// ------ API ------
const fetchMemories = async (params: {
  userId?: string;
  agentId?: string;
  source?: string; // 按来源筛选
}): Promise<MemoryItem[]> => {
  const url = new URL(`${getApiBaseUrl()}/api/v1/memories`);
  url.searchParams.set("user_id", params.userId ?? "yishu");
  if (params.agentId) url.searchParams.set("agent_id", params.agentId);
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`Failed to fetch memories: ${res.statusText}`);
  const data = await res.json();
  let items = data.items || data;

  // 客户端来源筛选（因为 API 没有按 source 筛选的参数）
  if (params.source) {
    items = items.filter((m: MemoryItem) => inferSource(m) === params.source);
  }

  // 按时间倒序排序（最新的在前）
  items.sort((a: MemoryItem, b: MemoryItem) => {
    const timeA = new Date(a.created_at).getTime();
    const timeB = new Date(b.created_at).getTime();
    return timeB - timeA; // 倒序：b - a
  });

  // 处理 Qdrant payload 结构
  // API 返回: { content, metadata: { userId, agentId, data, ... } } (metadata 一个下划线)
  // TypeScript 接口用: metadata__ (两个下划线)
  return items.map((m: MemoryItem) => {
    // API 返回的 metadata 在 m.metadata 中（一个下划线）
    const apiMetadata =
      ((m as unknown as Record<string, unknown>).metadata as Record<
        string,
        unknown
      >) || {};
    return {
      ...m,
      // content 可能在顶层或 metadata.data 中
      content: m.content || String(apiMetadata.data || ""),
      // 从 metadata 中提取 userId 和 agentId
      userId: String(apiMetadata.userId || m.userId || ""),
      agentId: String(apiMetadata.agentId || m.agentId || ""),
      // 统一放到 metadata__ 中（两个下划线）
      metadata__: apiMetadata,
    };
  });
};

const searchMemories = async (params: {
  query: string;
  userId?: string;
  agentId?: string;
  limit?: number;
}): Promise<MemoryItem[]> => {
  const url = new URL(`${getApiBaseUrl()}/api/v1/memories/search`);
  url.searchParams.set("query", params.query);
  url.searchParams.set("user_id", params.userId ?? "yishu");
  url.searchParams.set("limit", String(params.limit ?? 20));
  if (params.agentId) url.searchParams.set("agent_id", params.agentId);
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`Failed to search memories: ${res.statusText}`);
  const data = await res.json();
  // Handle both array and paginated response
  return data.items || data;
};

// 从数据中推断记忆来源（优先使用 API 返回的 source 字段）
function inferSource(m: MemoryItem): string {
  // 1. 优先使用 API 返回的 source 字段（现在已正确实现）
  if (m.source && m.source !== "manual") {
    return m.source;
  }

  // 2. 如果 API 返回 "manual"，检查是否有 agent_id 判断真实来源
  if (m.source === "manual" && m.agent_id && m.agent_id !== "unknown") {
    // 如果有 agent_id 但 source 是 manual，可能是新添加的记忆
    return "manual";
  }

  // 3. 从 metadata 中提取 agentId/userId 推断来源（兼容旧数据）
  const metadata = m.metadata__ as Record<string, unknown> | undefined;
  const userId = String(metadata?.userId || m.userId || "");
  const agentId = String(metadata?.agentId || m.agentId || m.agent_id || "");

  // 根据 agentId 特点判断来源
  if (agentId.startsWith("mc-")) {
    // mc- 前缀是 Mission Control 管理的 agent，属于 OpenClaw
    return "openclaw";
  }

  if (userId.includes("claude-code") || agentId.includes("claude-code")) {
    return "claude-code";
  }

  if (agentId === "main" || agentId.startsWith("lead-")) {
    // main 和 lead- 是 OpenClaw 的默认 agent
    return "openclaw";
  }

  // 默认为手工（手动添加）
  return "manual";
}

// Derive source list from memories
function deriveSources(memories: MemoryItem[]): SourceInfo[] {
  const countMap: Record<string, number> = {};
  for (const m of memories) {
    const src = inferSource(m);
    countMap[src] = (countMap[src] ?? 0) + 1;
  }

  // 定义来源顺序和标签
  const sourceLabels: Record<string, string> = {
    "claude-code": "Claude Code",
    openclaw: "OpenClaw",
    conversation: "对话",
    manual: "手工",
    unknown: "未知",
  };

  return Object.entries(countMap)
    .map(([source_id, count]) => ({
      source_id,
      label: sourceLabels[source_id] || source_id,
      count,
    }))
    .sort((a, b) => {
      // 按固定顺序排序
      const order = [
        "claude-code",
        "openclaw",
        "conversation",
        "manual",
        "unknown",
      ];
      return order.indexOf(a.source_id) - order.indexOf(b.source_id);
    });
}

// Derive stats from memories list (mem0 has no /stats endpoint)
function deriveStats(memories: MemoryItem[]): MemoryStats {
  const by_source: Record<string, number> = {};
  const by_agent: Record<string, number> = {};
  for (const m of memories) {
    // 使用 inferSource 推断来源
    const src = inferSource(m);
    by_source[src] = (by_source[src] ?? 0) + 1;

    // agent_id 优先使用顶层字段，其次 metadata
    const agentId =
      m.agentId || String(m.agent_id || m.metadata__?.agentId || "unknown");
    by_agent[agentId] = (by_agent[agentId] ?? 0) + 1;
  }
  return {
    total: memories.length,
    by_source,
    by_agent: Object.entries(by_agent).map(([agent_id, count]) => ({
      agent_id,
      count,
    })),
  };
}

// Derive agent list from memories
function deriveAgents(memories: MemoryItem[]): AgentInfo[] {
  const countMap: Record<string, number> = {};
  for (const m of memories) {
    // 从 metadata 中提取 agentId（API 返回的结构）
    const metadata = m.metadata__ as Record<string, unknown> | undefined;
    const agentId = String(
      metadata?.agentId || m.agentId || m.agent_id || "unknown",
    );
    countMap[agentId] = (countMap[agentId] ?? 0) + 1;
  }
  return Object.entries(countMap).map(([agent_id, count]) => ({
    agent_id,
    count,
  }));
}

const addMemory = async (params: {
  text: string;
  userId?: string;
  agentId?: string;
}): Promise<{ id: string; status: string }> => {
  const res = await fetch(`${getApiBaseUrl()}/api/v1/memories`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: params.text,
      user_id: params.userId ?? "yishu",
      agent_id: params.agentId,
    }),
  });
  if (!res.ok) throw new Error(`Failed to add memory: ${res.statusText}`);
  return res.json();
};

const deleteMemory = async (memoryId: string): Promise<void> => {
  const res = await fetch(`${getApiBaseUrl()}/api/v1/memories/${memoryId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Failed to delete memory: ${res.statusText}`);
};

const fetchTurn = async (turnId: string): Promise<TurnDetail> => {
  const res = await fetch(`${getApiBaseUrl()}/api/v2/turns/${turnId}`);
  if (!res.ok) throw new Error(`Failed to fetch turn: ${res.statusText}`);
  return res.json();
};

const fetchMemoriesByTurn = async (
  turnId: string,
  userId: string,
): Promise<MemoryItem[]> => {
  const url = new URL(`${getApiBaseUrl()}/api/v2/memories/`);
  url.searchParams.set("user_id", userId);
  url.searchParams.set("turn_id", turnId);
  const res = await fetch(url.toString());
  if (!res.ok)
    throw new Error(`Failed to fetch turn memories: ${res.statusText}`);
  const data = await res.json();
  return data.items || [];
};

// ------ Helpers ------
function formatDate(dateStr: unknown): string {
  if (!dateStr) return "—";
  try {
    const d = new Date(String(dateStr));
    return d.toLocaleString("zh-CN", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return String(dateStr);
  }
}

function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max) + "…" : text;
}

// ------ Stat Card ------
function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: number;
  sub?: string;
  accent?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
        {label}
      </p>
      <p className={cn("mt-2 text-3xl font-bold", accent ?? "text-slate-900")}>
        {value.toLocaleString()}
      </p>
      {sub && <p className="mt-1 text-xs text-slate-400">{sub}</p>}
    </div>
  );
}

// 来源标签映射
const SOURCE_LABELS: Record<string, string> = {
  "claude-code": "Claude Code",
  openclaw: "OpenClaw",
  conversation: "对话",
  manual: "手工",
  unknown: "未知",
};

// 来源对应的颜色
const SOURCE_COLORS: Record<string, string> = {
  "claude-code": "bg-purple-100 text-purple-700 border-purple-200",
  openclaw: "bg-blue-100 text-blue-700 border-blue-200",
  conversation: "bg-green-100 text-green-700 border-green-200",
  manual: "bg-slate-100 text-slate-700 border-slate-200",
  unknown: "bg-gray-100 text-gray-700 border-gray-200",
};

// memory_type 标签和颜色
const TYPE_LABELS: Record<string, string> = {
  fact: "事实",
  summary: "摘要",
  correction: "纠正",
  procedure: "流程",
  task_fact: "任务事实",
};

const TYPE_COLORS: Record<string, string> = {
  fact: "bg-amber-100 text-amber-700 border-amber-200",
  summary: "bg-teal-100 text-teal-700 border-teal-200",
  correction: "bg-red-100 text-red-700 border-red-200",
  procedure: "bg-blue-100 text-blue-700 border-blue-200",
  task_fact: "bg-purple-100 text-purple-700 border-purple-200",
};

// processing_status 颜色
const STATUS_COLORS: Record<string, string> = {
  completed: "bg-green-100 text-green-700",
  pending: "bg-yellow-100 text-yellow-700",
  processing: "bg-blue-100 text-blue-700",
  failed: "bg-red-100 text-red-700",
};

// ------ Memory Card ------
function MemoryCard({
  memory,
  onDelete,
  onSelect,
}: {
  memory: MemoryItem;
  onDelete: (id: string) => void;
  onSelect: (memory: MemoryItem) => void;
}) {
  const [deleting, setDeleting] = useState(false);
  const source = inferSource(memory);
  const sourceLabel = SOURCE_LABELS[source] || source;
  const sourceColor = SOURCE_COLORS[source] || SOURCE_COLORS["unknown"];
  const typeLabel = memory.memory_type ? TYPE_LABELS[memory.memory_type] : null;
  const typeColor = memory.memory_type
    ? TYPE_COLORS[memory.memory_type] || ""
    : "";

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleting(true);
    try {
      await deleteMemory(memory.id);
      onDelete(memory.id);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div
      className="cursor-pointer rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-blue-300"
      onClick={() => onSelect(memory)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm leading-relaxed text-slate-700">
            {truncate(memory.content, 300)}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {/* 来源 Badge */}
            <span
              className={cn(
                "rounded-full border px-2 py-0.5 text-xs font-medium",
                sourceColor,
              )}
            >
              {sourceLabel}
            </span>
            {/* memory_type Badge */}
            {typeLabel && (
              <span
                className={cn(
                  "rounded-full border px-2 py-0.5 text-xs font-medium",
                  typeColor,
                )}
              >
                {typeLabel}
              </span>
            )}
            {/* Agent Badge */}
            {(() => {
              const metadata = memory.metadata__ as
                | Record<string, unknown>
                | undefined;
              const agentId =
                memory.agentId ||
                memory.agent_id ||
                String(metadata?.agentId || "");
              return agentId ? (
                <Badge variant="outline" className="gap-1 text-xs">
                  <Bot className="h-3 w-3" />
                  {agentId}
                </Badge>
              ) : null;
            })()}
            {/* 搜索得分 */}
            {memory.score != null && memory.score !== undefined && (
              <Badge variant="outline" className="text-xs">
                {(memory.score * 100).toFixed(0)}%
              </Badge>
            )}
            <span className="text-xs text-slate-400">
              {formatDate(memory.created_at)}
            </span>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleDelete}
          disabled={deleting}
          className="shrink-0 text-slate-400 hover:text-red-500"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

// ------ Source Filter ------
function SourceFilter({
  sources,
  selected,
  onSelect,
}: {
  sources: SourceInfo[];
  selected?: string;
  onSelect: (source?: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-slate-500">来源:</span>
      <button
        onClick={() => onSelect(undefined)}
        className={cn(
          "rounded-full px-3 py-1 text-xs font-medium transition",
          !selected
            ? "bg-blue-500 text-white"
            : "bg-slate-100 text-slate-600 hover:bg-slate-200",
        )}
      >
        全部
      </button>
      {sources.map((src) => {
        const colorClass =
          SOURCE_COLORS[src.source_id] || SOURCE_COLORS["unknown"];
        return (
          <button
            key={src.source_id}
            onClick={() => onSelect(src.source_id)}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium transition",
              selected === src.source_id
                ? "bg-blue-500 text-white"
                : colorClass,
            )}
          >
            {src.label} ({src.count})
          </button>
        );
      })}
    </div>
  );
}

// ------ Agent Filter ------
function AgentFilter({
  agents,
  selected,
  onSelect,
}: {
  agents: AgentInfo[];
  selected?: string;
  onSelect: (agentId?: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Filter className="h-4 w-4 text-slate-400" />
      <button
        onClick={() => onSelect(undefined)}
        className={cn(
          "rounded-full px-3 py-1 text-xs font-medium transition",
          !selected
            ? "bg-blue-500 text-white"
            : "bg-slate-100 text-slate-600 hover:bg-slate-200",
        )}
      >
        All
      </button>
      {agents.map((agent) => (
        <button
          key={agent.agent_id}
          onClick={() => onSelect(agent.agent_id)}
          className={cn(
            "rounded-full px-3 py-1 text-xs font-medium transition",
            selected === agent.agent_id
              ? "bg-blue-500 text-white"
              : "bg-slate-100 text-slate-600 hover:bg-slate-200",
          )}
        >
          <span className="flex items-center gap-1">
            <Bot className="h-3 w-3" />
            {agent.agent_id} ({agent.count})
          </span>
        </button>
      ))}
    </div>
  );
}

// ------ Tool Call / Message Content Rendering ------
function ToolCallBlock({ block }: { block: ContentBlock }) {
  const [expanded, setExpanded] = useState(false);

  if (block.type === "tool_use") {
    const inputStr =
      typeof block.input === "string"
        ? block.input
        : JSON.stringify(block.input, null, 2);
    return (
      <div className="my-1 rounded border border-amber-200 bg-amber-50 p-2 text-xs">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 font-mono font-semibold text-amber-700"
        >
          <Wrench className="h-3 w-3" />
          {block.name || "unknown"}
          {expanded ? (
            <ChevronUp className="h-3 w-3" />
          ) : (
            <ChevronDown className="h-3 w-3" />
          )}
        </button>
        {expanded && (
          <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap text-amber-600 text-[11px]">
            {inputStr.length > 2000
              ? inputStr.slice(0, 2000) + "\n...[truncated]"
              : inputStr}
          </pre>
        )}
      </div>
    );
  }

  if (block.type === "tool_result") {
    const resultStr =
      typeof block.content === "string"
        ? block.content
        : JSON.stringify(block.content);
    return (
      <div className="my-1 rounded border border-green-200 bg-green-50 p-2 text-xs">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 font-mono font-semibold text-green-700"
        >
          <ClipboardList className="h-3 w-3" />
          Result
          {expanded ? (
            <ChevronUp className="h-3 w-3" />
          ) : (
            <ChevronDown className="h-3 w-3" />
          )}
        </button>
        {expanded && (
          <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap text-green-600 text-[11px]">
            {resultStr.length > 2000
              ? resultStr.slice(0, 2000) + "\n...[truncated]"
              : resultStr}
          </pre>
        )}
      </div>
    );
  }

  return null;
}

function MessageContent({ content }: { content: string | ContentBlock[] }) {
  if (typeof content === "string") {
    return (
      <p className="mt-1 whitespace-pre-wrap text-slate-700">
        {content.length > 500 ? content.slice(0, 500) + "..." : content}
      </p>
    );
  }

  // Structured content with tool blocks
  const toolCount = content.filter((b) => b.type === "tool_use").length;
  return (
    <div className="mt-1 space-y-1">
      {toolCount > 0 && (
        <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-700">
          <Wrench className="h-2.5 w-2.5" />
          {toolCount} tool call{toolCount > 1 ? "s" : ""}
        </span>
      )}
      {content.map((block, j) => {
        if (block.type === "text") {
          const text = block.text || "";
          return (
            <p key={j} className="whitespace-pre-wrap text-slate-700">
              {text.length > 500 ? text.slice(0, 500) + "..." : text}
            </p>
          );
        }
        return <ToolCallBlock key={j} block={block} />;
      })}
    </div>
  );
}

// ------ Memory Detail Dialog ------
function MemoryDetailDialog({
  memory,
  open,
  onClose,
  userId,
  onDelete,
}: {
  memory: MemoryItem | null;
  open: boolean;
  onClose: () => void;
  userId: string;
  onDelete: (id: string) => void;
}) {
  const [turn, setTurn] = useState<TurnDetail | null>(null);
  const [turnMemories, setTurnMemories] = useState<MemoryItem[]>([]);
  const [turnLoading, setTurnLoading] = useState(false);
  const [messagesExpanded, setMessagesExpanded] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!open || !memory?.turn_id) {
      setTurn(null);
      setTurnMemories([]);
      setMessagesExpanded(false);
      return;
    }
    setTurnLoading(true);
    Promise.all([
      fetchTurn(memory.turn_id).catch(() => null),
      fetchMemoriesByTurn(memory.turn_id, userId).catch(() => []),
    ])
      .then(([t, mems]) => {
        setTurn(t);
        setTurnMemories(mems);
      })
      .finally(() => setTurnLoading(false));
  }, [open, memory?.turn_id, userId]);

  if (!memory) return null;

  const source = inferSource(memory);
  const sourceLabel = SOURCE_LABELS[source] || source;
  const sourceColor = SOURCE_COLORS[source] || SOURCE_COLORS["unknown"];
  const typeLabel = memory.memory_type ? TYPE_LABELS[memory.memory_type] : null;
  const typeColor = memory.memory_type
    ? TYPE_COLORS[memory.memory_type] || ""
    : "";

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await deleteMemory(memory.id);
      onDelete(memory.id);
      onClose();
    } finally {
      setDeleting(false);
    }
  };

  // 同 Turn 其他记忆（排除当前记忆）
  const siblingMemories = turnMemories.filter((m) => m.id !== memory.id);

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-slate-500" />
            记忆详情
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* 元数据 */}
          <div className="flex flex-wrap items-center gap-2">
            {typeLabel && (
              <span
                className={cn(
                  "rounded-full border px-2 py-0.5 text-xs font-medium",
                  typeColor,
                )}
              >
                {typeLabel}
              </span>
            )}
            <span
              className={cn(
                "rounded-full border px-2 py-0.5 text-xs font-medium",
                sourceColor,
              )}
            >
              {sourceLabel}
            </span>
            {(() => {
              const metadata = memory.metadata__ as
                | Record<string, unknown>
                | undefined;
              const agentId =
                memory.agentId ||
                memory.agent_id ||
                String(metadata?.agentId || "");
              return agentId ? (
                <Badge variant="outline" className="gap-1 text-xs">
                  <Bot className="h-3 w-3" />
                  {agentId}
                </Badge>
              ) : null;
            })()}
            <span className="text-xs text-slate-400">
              <Clock className="mr-1 inline h-3 w-3" />
              {formatDate(memory.created_at)}
            </span>
          </div>

          {/* 完整记忆内容 */}
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
              {memory.content}
            </p>
          </div>

          {/* Turn 关联 */}
          {memory.turn_id && (
            <div className="rounded-lg border border-slate-200 bg-white p-4 space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                <Layers className="h-4 w-4" />
                Turn 关联
              </div>

              {turnLoading ? (
                <div className="h-16 animate-pulse rounded-lg bg-slate-100" />
              ) : turn ? (
                <div className="space-y-3">
                  {/* Turn 元数据 */}
                  <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                    <div>
                      <span className="text-slate-400">Turn ID: </span>
                      <span className="font-mono text-slate-600">
                        {turn.id.slice(0, 12)}...
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-400">状态: </span>
                      <span
                        className={cn(
                          "rounded px-1.5 py-0.5 font-medium",
                          STATUS_COLORS[turn.processing_status] ||
                            "bg-slate-100 text-slate-600",
                        )}
                      >
                        {turn.processing_status}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-400">Session: </span>
                      <span className="font-mono text-slate-600">
                        {turn.session_id.length > 24
                          ? turn.session_id.slice(0, 24) + "..."
                          : turn.session_id}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-400">来源: </span>
                      <span className="text-slate-600">{turn.source}</span>
                    </div>
                    <div>
                      <span className="text-slate-400">Agent: </span>
                      <span className="text-slate-600">{turn.agent_id}</span>
                    </div>
                    <div>
                      <span className="text-slate-400">时间: </span>
                      <span className="text-slate-600">
                        {formatDate(turn.created_at)}
                      </span>
                    </div>
                  </div>

                  {/* 消息列表 (折叠/展开) */}
                  {turn.messages.length > 0 && (
                    <div>
                      <button
                        onClick={() => setMessagesExpanded(!messagesExpanded)}
                        className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800"
                      >
                        <MessageSquare className="h-3 w-3" />
                        消息 ({turn.messages.length})
                        {messagesExpanded ? (
                          <ChevronUp className="h-3 w-3" />
                        ) : (
                          <ChevronDown className="h-3 w-3" />
                        )}
                      </button>
                      {messagesExpanded && (
                        <div className="mt-2 space-y-2">
                          {turn.messages.map((msg, i) => (
                            <div
                              key={i}
                              className={cn(
                                "rounded-lg p-3 text-xs",
                                msg.role === "user"
                                  ? "bg-blue-50 border border-blue-100"
                                  : "bg-slate-50 border border-slate-100",
                              )}
                            >
                              <span className="font-semibold text-slate-500">
                                {msg.role === "user"
                                  ? "👤 user"
                                  : msg.role === "system"
                                    ? "⚙️ system"
                                    : "🤖 assistant"}
                              </span>
                              <MessageContent content={msg.content} />
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* 同 Turn 其他记忆 */}
                  {siblingMemories.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-slate-500 mb-2">
                        同 Turn 其他记忆 ({siblingMemories.length})
                      </p>
                      <div className="space-y-1.5">
                        {siblingMemories.map((m) => {
                          const tl = m.memory_type
                            ? TYPE_LABELS[m.memory_type]
                            : null;
                          const tc = m.memory_type
                            ? TYPE_COLORS[m.memory_type] || ""
                            : "";
                          return (
                            <div
                              key={m.id}
                              className="flex items-start gap-2 rounded-lg bg-slate-50 p-2 text-xs"
                            >
                              {tl && (
                                <span
                                  className={cn(
                                    "shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-medium",
                                    tc,
                                  )}
                                >
                                  {tl}
                                </span>
                              )}
                              <span className="text-slate-600">
                                {truncate(m.content, 120)}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-xs text-slate-400">Turn 信息不可用</p>
              )}
            </div>
          )}

          {/* 操作按钮 */}
          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleDelete}
              disabled={deleting}
              className="text-red-500 hover:text-red-700"
            >
              <Trash2 className="mr-1 h-3 w-3" />
              {deleting ? "删除中..." : "删除"}
            </Button>
            <Button variant="outline" size="sm" onClick={onClose}>
              关闭
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ------ Main Page ------
export default function MemoriesPage() {
  const { isSignedIn } = useAuth();
  const { isAdmin } = useOrganizationMembership(isSignedIn);

  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [sources, setSources] = useState<SourceInfo[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string | undefined>();
  const [selectedSource, setSelectedSource] = useState<string | undefined>();
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newMemoryText, setNewMemoryText] = useState("");
  const [addingMemory, setAddingMemory] = useState(false);
  const [view, setView] = useState<"list" | "graph" | "ailearn">("list");
  const [selectedMemory, setSelectedMemory] = useState<MemoryItem | null>(null);

  const userId = "yishu";

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      // mem0 has no /stats or /agents endpoints; derive from memories list
      const data = await fetchMemories({
        userId,
        agentId: selectedAgent,
        source: selectedSource,
      });
      setMemories(data);
      setStats(deriveStats(data));
      setAgents(deriveAgents(data));
      setSources(deriveSources(data));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    } finally {
      setIsLoading(false);
    }
  }, [userId, selectedAgent, selectedSource]);

  const loadMemories = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchMemories({
        userId,
        agentId: selectedAgent,
        source: selectedSource,
      });
      setMemories(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load memories");
    } finally {
      setIsLoading(false);
    }
  }, [userId, selectedAgent, selectedSource]);

  // Initial load and re-load when filters change
  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, selectedAgent, selectedSource]);

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      loadMemories();
      return;
    }
    setIsSearching(true);
    setError(null);
    try {
      const results = await searchMemories({
        query: searchQuery,
        userId,
        agentId: selectedAgent,
        limit: 20,
      });
      setMemories(results);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setIsSearching(false);
    }
  };

  const handleAddMemory = async () => {
    if (!newMemoryText.trim()) return;
    setAddingMemory(true);
    setError(null);
    try {
      await addMemory({
        text: newMemoryText,
        userId,
        agentId: selectedAgent,
      });
      setNewMemoryText("");
      setShowAddForm(false);
      await Promise.all([loadData(), loadMemories()]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add memory");
    } finally {
      setAddingMemory(false);
    }
  };

  const handleDeleteMemory = (id: string) => {
    setMemories((prev) => prev.filter((m) => m.id !== id));
    loadData();
  };

  if (!isAdmin) {
    return (
      <DashboardShell>
        <DashboardSidebar />
        <main className="flex-1 overflow-y-auto bg-slate-50">
          <div className="flex h-full items-center justify-center">
            <p className="text-slate-500">Only admins can access memories.</p>
          </div>
        </main>
      </DashboardShell>
    );
  }

  return (
    <DashboardShell>
      <DashboardSidebar />
      <main className="flex-1 overflow-y-auto bg-slate-50">
        <div className="p-4 md:p-8 space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Brain className="h-6 w-6 text-blue-500" />
              <div>
                <h1 className="text-xl font-bold text-slate-900">记忆管理</h1>
                <p className="text-sm text-slate-500">
                  Agent 记忆隔离 · 向量搜索
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Tabs
                value={view}
                onValueChange={(v) =>
                  setView(v as "list" | "graph" | "ailearn")
                }
              >
                <TabsList className="h-8">
                  <TabsTrigger value="list" className="text-xs">
                    列表
                  </TabsTrigger>
                  <TabsTrigger value="graph" className="text-xs">
                    图谱
                  </TabsTrigger>
                  <TabsTrigger value="ailearn" className="text-xs">
                    AI 学习
                  </TabsTrigger>
                </TabsList>
              </Tabs>
              <Button
                variant="outline"
                size="sm"
                onClick={() => Promise.all([loadData(), loadMemories()])}
                disabled={isLoading}
              >
                <RefreshCw
                  className={cn("h-4 w-4", isLoading && "animate-spin")}
                />
              </Button>
              <Button size="sm" onClick={() => setShowAddForm(!showAddForm)}>
                <Plus className="h-4 w-4" />
                添加记忆
              </Button>
            </div>
          </div>

          {/* Graph View */}
          {view === "graph" && <MemoryGraph userId={userId} />}

          {/* AI Learning View */}
          {view === "ailearn" && <AILearnView />}

          {/* Error */}
          {error && (
            <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Add Memory Form */}
          {showAddForm && (
            <div className="rounded-xl border border-blue-200 bg-white p-4 shadow-sm">
              <h3 className="mb-3 text-sm font-semibold text-slate-700">
                添加新记忆
              </h3>
              <div className="flex gap-2">
                <Input
                  value={newMemoryText}
                  onChange={(e) => setNewMemoryText(e.target.value)}
                  placeholder="输入要记住的内容..."
                  onKeyDown={(e) => e.key === "Enter" && handleAddMemory()}
                  className="flex-1"
                />
                <Button
                  onClick={handleAddMemory}
                  disabled={addingMemory || !newMemoryText.trim()}
                >
                  {addingMemory ? "添加中…" : "保存"}
                </Button>
                <Button variant="ghost" onClick={() => setShowAddForm(false)}>
                  取消
                </Button>
              </div>
              {selectedAgent && (
                <p className="mt-2 text-xs text-slate-500">
                  将添加到 Agent: {selectedAgent.slice(0, 8)}…
                </p>
              )}
            </div>
          )}

          {/* Stats */}
          {isLoading && !stats ? (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              {[...Array(4)].map((_, i) => (
                <div
                  key={i}
                  className="h-24 animate-pulse rounded-xl border border-slate-200 bg-white shadow-sm"
                />
              ))}
            </div>
          ) : stats && view === "list" ? (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <StatCard label="总记忆数" value={stats.total} />
              <StatCard
                label="来源"
                value={Object.keys(stats.by_source).length}
                sub={Object.entries(stats.by_source)
                  .slice(0, 2)
                  .map(([k, v]) => `${k}: ${v}`)
                  .join(", ")}
              />
              <StatCard label="Agent 数" value={stats.by_agent.length} />
              <StatCard
                label="当前筛选"
                value={selectedAgent ? 1 : 0}
                accent={selectedAgent ? "text-blue-500" : undefined}
                sub={selectedAgent ?? "全部"}
              />
            </div>
          ) : null}

          {/* Source Filter */}
          {sources.length > 0 && view === "list" && (
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <SourceFilter
                sources={sources}
                selected={selectedSource}
                onSelect={(source) => setSelectedSource(source)}
              />
            </div>
          )}

          {/* Agent Filter */}
          {agents.length > 0 && view === "list" && (
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <AgentFilter
                agents={agents}
                selected={selectedAgent}
                onSelect={(agentId) => setSelectedAgent(agentId)}
              />
            </div>
          )}

          {/* Search */}
          {view === "list" && (
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <Input
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="搜索记忆内容..."
                    onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                    className="pl-10"
                  />
                </div>
                <Button onClick={handleSearch} disabled={isSearching}>
                  {isSearching ? "搜索中…" : "搜索"}
                </Button>
                {searchQuery && (
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setSearchQuery("");
                      loadMemories();
                    }}
                  >
                    清除
                  </Button>
                )}
              </div>
            </div>
          )}

          {/* Memory List */}
          {view === "list" && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-700">
                  记忆列表 ({memories.length})
                </h2>
              </div>

              {isLoading ? (
                <div className="space-y-3">
                  {[...Array(3)].map((_, i) => (
                    <div
                      key={i}
                      className="h-24 animate-pulse rounded-xl border border-slate-200 bg-white shadow-sm"
                    />
                  ))}
                </div>
              ) : memories.length === 0 ? (
                <div className="flex h-[120px] items-center justify-center rounded-lg border border-slate-200 bg-slate-50 text-sm text-slate-500">
                  {searchQuery
                    ? "未找到匹配的记忆"
                    : "暂无记忆，使用上方搜索框添加"}
                </div>
              ) : (
                <div className="space-y-3">
                  {memories.map((memory) => (
                    <MemoryCard
                      key={memory.id}
                      memory={memory}
                      onDelete={handleDeleteMemory}
                      onSelect={setSelectedMemory}
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </main>

      {/* Memory Detail Dialog */}
      <MemoryDetailDialog
        memory={selectedMemory}
        open={selectedMemory !== null}
        onClose={() => setSelectedMemory(null)}
        userId={userId}
        onDelete={handleDeleteMemory}
      />
    </DashboardShell>
  );
}
