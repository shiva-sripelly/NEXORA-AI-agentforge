import { api } from "../api/client";
import type { Document, DocumentList } from "../types/document";
export const documents = {
  list: (page = 1) => api<DocumentList>(`/documents?page=${page}&page_size=100`),
  async all() {
    const first = await documents.list();
    const items = [...first.items];
    for (let page = 2; page <= Math.ceil(first.total / first.page_size); page++) {
      items.push(...(await documents.list(page)).items);
    }
    return items;
  },
  get: (id: string) => api<Document>(`/documents/${id}`),
  remove: (id: string) => api<void>(`/documents/${id}`, { method: "DELETE" }),
  async upload(file: File) {
    const form = new FormData();
    form.append("file", file);
    return api<Document>("/documents", { method: "POST", body: form });
  },
};
