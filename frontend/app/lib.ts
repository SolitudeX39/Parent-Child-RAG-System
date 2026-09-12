export const API = "/rag";

export type Source = {
  page?: number | null;
  text: string;
  filename?: string | null;
  document_id?: string | null;
};

export type DocumentItem = {
  name: string;
  id: string;
  chunks?: number;
};

export type DocumentPage = {
  page: number | null;
  text: string;
};

export async function readError(res: Response) {
  try {
    const data = await res.json();
    const detail = data.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg || JSON.stringify(item)).join(", ");
    }
    return data.message || res.statusText;
  } catch {
    return res.statusText;
  }
}
