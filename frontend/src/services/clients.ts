import api from './api';

export interface Client {
  id: number;
  name: string;
  contact_person?: string;
  contact_email?: string;
  phone_number?: string;
  address?: string;
  is_high_risk: boolean;
  risk_notes?: string;
  organization_id: number;
  created_at: string;
  updated_at: string;
}

export interface ClientCreate {
  name: string;
  contact_person?: string;
  contact_email?: string;
  phone_number?: string;
  address?: string;
  is_high_risk?: boolean;
  risk_notes?: string;
}

export const clientsService = {
  getClients: async (): Promise<Client[]> => {
    const response = await api.get('/v1/clients/');
    return response.data;
  },
  
  getClient: async (id: number): Promise<Client> => {
    const response = await api.get(`/v1/clients/${id}`);
    return response.data;
  },
  
  createClient: async (data: ClientCreate): Promise<Client> => {
    const response = await api.post('/v1/clients/', data);
    return response.data;
  }
};
