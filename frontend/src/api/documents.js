import axios from 'axios';

export const fetchDocumentMarkdown = async ({ id, start_page = 1, max_pages = null, max_characters = null, title = null }) => {
  if (id) {
    const params = { start_page };
    if (max_pages) params.max_pages = max_pages;
    if (max_characters) params.max_characters = max_characters;
    const response = await axios.get(`/api/documents/${id}/markdown`, { params });
    return response.data;
  }

  // Fallback to title-based MCP endpoint (backwards compatibility)
  const response = await axios.get(`/mcp/documents/markdown`, {
    params: { title, start_page, max_pages, max_characters }
  });
  return response.data;
};

export const searchDocuments = async ({ query, limit = 10, offset = 0 }) => {
  const params = { q: query, limit, offset };
  const response = await axios.get('/api/search', { params });
  return response.data;
};
