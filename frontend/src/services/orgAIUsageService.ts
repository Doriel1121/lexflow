import api from './api';
import type { AIUsageFilters, AIUsageResponse } from './adminService';

export const orgAIUsageService = {
  getAIUsage: (filters: AIUsageFilters = {}): Promise<AIUsageResponse> =>
    api.get('/v1/org/ai-usage', { params: filters }).then((response) => response.data),
};
