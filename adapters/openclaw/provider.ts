/**
 * OpenMemory HTTP Provider — connects to the OpenMemory Python API instead of
 * using the mem0ai SDK directly.
 */

import type {
  AddOptions,
  ListOptions,
  MemoryItem,
  AddResult,
  AddResultItem,
  SearchOptions,
  Mem0Provider,
} from "./types.ts";

const HTTP_TIMEOUT_MS = 30_000;

// ============================================================================
// OpenMemoryProvider
// ============================================================================

export class OpenMemoryProvider implements Mem0Provider {
  constructor(private readonly apiUrl: string) {}

  // ---------------------------------------------------------------------------
  // Internal HTTP helper
  // ---------------------------------------------------------------------------

  private async request<T>(
    method: "GET" | "POST" | "PUT" | "DELETE",
    path: string,
    body?: unknown,
  ): Promise<T> {
    const url = `${this.apiUrl}${path}`;
    const opts: RequestInit = {
      method,
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(HTTP_TIMEOUT_MS),
    };
    if (body !== undefined) opts.body = JSON.stringify(body);

    const res = await fetch(url, opts);
    if (!res.ok) {
      const detail = await res.text().catch(() => res.statusText);
      throw new Error(
        `OpenMemory API ${method} ${path} failed ${res.status}: ${detail}`,
      );
    }
    // Some endpoints return 204 No Content
    if (res.status === 204) return {} as T;
    return res.json() as Promise<T>;
  }

  // ---------------------------------------------------------------------------
  // Result normalizers
  // ---------------------------------------------------------------------------

  private normalizeMemoryItem(raw: unknown): MemoryItem {
    const r = raw as Record<string, unknown>;
    return {
      id: String(r.id ?? r.memory_id ?? ""),
      // Qdrant list returns "content", single get returns "text"
      memory: String(r.memory ?? r.text ?? r.content ?? ""),
      user_id: String(r.user_id ?? r.userId ?? ""),
      score: typeof r.score === "number" ? r.score : undefined,
      categories: Array.isArray(r.categories)
        ? (r.categories as unknown[]).map(String)
        : undefined,
      metadata: (r.metadata ?? r.metadata_) as Record<string, unknown> | undefined,
      created_at: String(r.created_at ?? r.createdAt ?? ""),
      updated_at: String(r.updated_at ?? r.updatedAt ?? ""),
    };
  }

  // ---------------------------------------------------------------------------
  // add — Creates a Turn via POST /api/v1/turns/, Worker handles fact extraction
  // ---------------------------------------------------------------------------

  async add(
    messages: Array<{ role: string; content: string }>,
    options: AddOptions,
  ): Promise<AddResult> {
    const agentId = options.run_id ?? undefined;
    const sessionId = `openclaw-${Date.now()}`;

    const res = await this.request<{ success: boolean; turn_id?: string }>(
      "POST",
      "/api/v1/turns/",
      {
        session_id: sessionId,
        user_id: options.user_id,
        agent_id: agentId,
        messages,
        source: "openclaw",
      },
    );

    return {
      results: res.turn_id
        ? [{ id: res.turn_id, memory: "Turn created, Worker will extract facts", event: "ADD" as const }]
        : [],
    };
  }

  // ---------------------------------------------------------------------------
  // recall — intelligent parallel recall via POST /api/v2/recall
  //          falls back to search() if unavailable
  // ---------------------------------------------------------------------------

  async recall(
    query: string,
    userId: string,
    agentId?: string,
    budgetTokens?: number,
  ): Promise<{ contextText: string; sources: unknown[]; timing: Record<string, number> } | null> {
    try {
      const body: Record<string, unknown> = {
        user_id: userId,
        query,
        context_budget_tokens: budgetTokens ?? 2000,
      };
      if (agentId) body.agent_id = agentId;

      const resp = await this.request<{
        context_text: string;
        sources: unknown[];
        timing: Record<string, number>;
      }>("POST", "/api/v2/recall", body);

      return {
        contextText: resp.context_text ?? "",
        sources: resp.sources ?? [],
        timing: resp.timing ?? {},
      };
    } catch (err) {
      this.log?.(`recall failed, will fallback to search: ${err}`);
      return null;
    }
  }

  // ---------------------------------------------------------------------------
  // search — semantic vector search via new /search endpoint
  //           falls back to keyword filter if unavailable
  // ---------------------------------------------------------------------------

  async search(query: string, options: SearchOptions): Promise<MemoryItem[]> {
    const limit = options.limit ?? options.top_k ?? 5;
    const threshold = options.threshold ?? 0.0;

    // Build query params for the semantic search endpoint
    const params = new URLSearchParams({
      user_id: options.user_id,
      query,
      limit: String(limit),
    });
    if (options.run_id) params.set("agent_id", options.run_id);
    if (options.threshold != null) params.set("threshold", String(options.threshold));

    let raw: unknown;
    try {
      // Primary: semantic vector search via v2
      raw = await this.request<{ items: unknown[]; total?: number }>(
        "GET",
        `/api/v2/memories/search?${params}`,
      );
    } catch (_err) {
      // Fallback: keyword filter via existing endpoint
      const fallback = await this.request<{ items: unknown[] }>(
        "POST",
        "/api/v1/memories/filter",
        {
          user_id: options.user_id,
          search_query: query,
          page: 1,
          size: limit,
        },
      );
      raw = fallback;
    }

    const resp = raw as { items?: unknown[] };
    const items = resp.items ?? [];
    const normalized = items.map((item) => this.normalizeMemoryItem(item));

    // Apply client-side threshold filter
    return normalized.filter((item) => (item.score ?? 0) >= threshold);
  }

  // ---------------------------------------------------------------------------
  // get — GET /api/v1/memories/{memory_id}
  // ---------------------------------------------------------------------------

  async get(memoryId: string): Promise<MemoryItem> {
    const raw = await this.request<Record<string, unknown>>(
      "GET",
      `/api/v1/memories/${memoryId}`,
    );
    return this.normalizeMemoryItem(raw);
  }

  // ---------------------------------------------------------------------------
  // getAll — GET /api/v1/memories/?user_id=...&agent_id=...&limit=...
  // ---------------------------------------------------------------------------

  async getAll(options: ListOptions): Promise<MemoryItem[]> {
    const params = new URLSearchParams({ user_id: options.user_id });
    if (options.run_id) params.set("agent_id", options.run_id);
    const limit = options.page_size ?? 200;
    params.set("limit", String(limit));

    const raw = await this.request<{ items: unknown[] }>(
      "GET",
      `/api/v2/memories/?${params}`,
    );
    return (raw.items ?? []).map((item) => this.normalizeMemoryItem(item));
  }

  // ---------------------------------------------------------------------------
  // delete — DELETE /api/v1/memories/
  // ---------------------------------------------------------------------------

  async delete(memoryId: string): Promise<void> {
    // DELETE /memories/ requires { memory_ids: [...], user_id }
    await this.request("DELETE", "/api/v1/memories/", {
      memory_ids: [memoryId],
      user_id: "",
    });
  }

  // ---------------------------------------------------------------------------
  // recordTurn — POST /api/v2/turns/
  // ---------------------------------------------------------------------------

  async recordTurn(params: {
    sessionId: string;
    userId: string;
    agentId: string;
    messages: Array<{ role: string; content: string }>;
  }): Promise<{ success: boolean; turn_id?: string }> {
    const res = await this.request<{ success: boolean; turn_id?: string }>(
      "POST",
      "/api/v2/turns/",
      {
        session_id: params.sessionId,
        user_id: params.userId,
        agent_id: params.agentId,
        messages: params.messages,
        source: "openclaw",
      },
    );
    return res;
  }
}
