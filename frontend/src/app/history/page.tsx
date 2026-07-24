"use client";

import { useEffect, useState } from "react";

import { readJson } from "@/lib/api";

interface Conversation {
  request_id: string; source: "text" | "voice"; user_text: string; assistant_text: string;
  status: "processing" | "completed" | "failed"; error_message: string; created_at: string;
}

export default function HistoryPage() {
  const [items, setItems] = useState<Conversation[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    readJson<{ conversations: Conversation[] }>("/api/conversations?limit=100")
      .then((result) => setItems(result.conversations))
      .catch(() => setError("Không tải được lịch sử hội thoại."));
  }, []);
  return <main><header className="dashboard-hero"><div><p className="eyebrow">LỊCH SỬ TRỢ LÝ</p><h1>Các yêu cầu gần đây.</h1><p className="lede">Nội dung người dùng, phản hồi cuối và trạng thái xử lý.</p></div></header>{error ? <p className="error">{error}</p> : null}<section className="conversation-list">{!error && !items.length ? <p className="trace-empty">Chưa có hội thoại.</p> : items.map((item) => <article className="conversation-card" key={item.request_id}><header><span>{item.source === "voice" ? "Giọng nói" : "Văn bản"}</span><time>{new Date(item.created_at).toLocaleString("vi-VN")}</time></header><strong>{item.user_text}</strong>{item.assistant_text ? <p>{item.assistant_text}</p> : null}{item.error_message ? <p className="trace-error">{item.error_message}</p> : null}<small>{item.status}</small></article>)}</section></main>;
}
