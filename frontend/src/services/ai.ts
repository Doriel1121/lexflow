import api from './api';
import { AskAIRequest, AskAIResponse } from '../types';

/**
 * AI Service for Retrieval-Augmented Generation (RAG)
 * Allows users to ask questions about cases or documents.
 */
export const aiService = {
  /**
   * Ask AI a natural language question.
   * Can be scoped to a case or specific documents.
   */
  askAI: async (request: AskAIRequest): Promise<AskAIResponse> => {
    const response = await api.post<AskAIResponse>('/v1/ai/ask', request);
    return response.data;
  },
};

export default aiService;
