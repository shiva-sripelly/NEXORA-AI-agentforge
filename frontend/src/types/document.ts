export type Document = {
  id: string;
  original_filename: string;
  display_name: string;
  content_type: string;
  file_size: number;
  status: "uploaded" | "processing" | "ready" | "failed";
  processing_error: string | null;
  chunk_count: number;
  created_at: string;
  updated_at: string;
};
export type DocumentList = {
  items: Document[];
  total: number;
  page: number;
  page_size: number;
};
