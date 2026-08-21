import axios from 'axios'
import type { ReviewItem, ReviewQueueResponse, ReviewStatus, SubmitDiff } from '@/types/review'
import type { ConfirmationReport, FieldDecision } from '@/types/confirmation'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
api.interceptors.request.use(
  (config) => {
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

// 人工複核 API
export const reviewApi = {
  getQueue: (status?: ReviewStatus) =>
    api.get<ReviewQueueResponse>('/v1/review/queue', {
      params: status ? { status } : {},
    }),
  getItem: (id: string) => api.get<ReviewItem>(`/v1/review/${id}`),
  claim: (id: string, reviewer: string) =>
    api.post<{ claimed: boolean }>(`/v1/review/${id}/claim`, { reviewer }),
  release: (id: string, reviewer: string) =>
    api.post<{ status: string }>(`/v1/review/${id}/release`, { reviewer }),
  submit: (id: string, reviewer: string, corrected_fields: Record<string, unknown>) =>
    api.post<{ status: string; diff: SubmitDiff }>(`/v1/review/${id}/submit`, {
      reviewer,
      corrected_fields,
    }),
}

// 使用者當場確認回灌(任務 9.2)
export const confirmationApi = {
  submit: (documentType: string, pageText: string, decisions: FieldDecision[]) =>
    api.post<ConfirmationReport>(`/v1/samples/${documentType}/confirm`, {
      page_text: pageText,
      decisions,
    }),
}

export default api
