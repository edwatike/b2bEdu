import type { CabinetMessageDTO } from "./types"
import { getCabinetMessages } from "./api"

// Оптимизированные API функции с кэшированием
export async function fetchYandexStatus(): Promise<{ connected: boolean; email: string | null }> {
  const response = await fetch("/api/yandex/status", { 
    cache: "force-cache",
    next: { revalidate: 30 } // 30 секунд
  });
  const data = await response.json().catch(() => ({ connected: false }));
  return { 
    connected: Boolean(data?.connected), 
    email: typeof data?.email === "string" ? data.email : null 
  };
}

export async function fetchYandexFolderCounts(): Promise<Record<string, { mailbox?: string; total: number; unseen: number }>> {
  const response = await fetch("/api/yandex/folders", { 
    cache: "force-cache",
    next: { revalidate: 60 } // 1 минута
  });
  const data = await response.json().catch(() => null);
  
  if (!response.ok || !data?.folders) {
    return {};
  }
  
  const next: Record<string, { mailbox?: string; total: number; unseen: number }> = {};
  for (const [role, meta] of Object.entries<any>(data.folders)) {
    next[role] = {
      mailbox: String(meta?.mailbox || ""),
      total: Number(meta?.total || 0),
      unseen: Number(meta?.unseen || 0),
    };
  }
  return next;
}

export async function fetchOptimizedMessages(params: {
  folder: string;
  yandexConnected: boolean;
  yandexFolderCounts?: Record<string, { mailbox?: string; total: number; unseen: number }>;
}): Promise<{
  messages: CabinetMessageDTO[];
  total: number;
  page: number;
  limit: number;
  demo?: boolean;
  error?: string;
}> {
  if (params.yandexConnected) {
    const mappedMailbox = params.yandexFolderCounts?.[params.folder]?.mailbox;
    const imapFolder = mappedMailbox || (params.folder === "spam" ? "SPAM" : params.folder === "sent" ? "Sent" : params.folder === "trash" ? "Trash" : "INBOX");
    
    const response = await fetch(`/api/yandex/mail?limit=20&page=1&folder=${encodeURIComponent(imapFolder)}`, {
      cache: "no-store"
    });
    
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      return {
        messages: [],
        total: 0,
        page: 1,
        limit: 20,
        error: data?.error || "Failed to fetch messages"
      };
    }
    
    return {
      messages: data.messages || [],
      total: data.total || 0,
      page: data.page || 1,
      limit: data.limit || 20,
      demo: Boolean(data.demo),
      error: data.error
    };
  } else {
    // Демо режим или обычные сообщения
    const data = await getCabinetMessages().catch(() => [] as any);
    return {
      messages: data,
      total: data.length,
      page: 1,
      limit: 20,
      demo: data.length > 0 && data[0]?.id?.toString().startsWith('demo_')
    };
  }
}

// Parallel загрузка всех данных
export async function fetchAllMailData(params: {
  folder: string;
  yandexConnected: boolean;
}) {
  try {
    const status = await fetchYandexStatus()

    const [folderCounts, messages] = await Promise.all([
      status.connected ? fetchYandexFolderCounts() : Promise.resolve({}),
      fetchOptimizedMessages({ folder: params.folder, yandexConnected: status.connected, yandexFolderCounts: {} }),
    ])

    return {
      status,
      folderCounts: status.connected ? folderCounts : {},
      messages,
      error: messages.error
    };
  } catch (error) {
    return {
      status: { connected: false, email: null },
      folderCounts: {},
      messages: { messages: [], total: 0, page: 1, limit: 20, demo: true },
      error: error instanceof Error ? error.message : "Unknown error"
    };
  }
}
