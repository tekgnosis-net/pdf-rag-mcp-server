import axios from 'axios';

export const fetchDocumentMarkdown = async (title) => {
  const response = await axios.get(`/mcp/documents/markdown`, {
    params: { title }
  });
  return response.data;
};
