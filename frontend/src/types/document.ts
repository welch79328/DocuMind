export interface Document {
  id: string
  file_name: string
  file_url: string
  mime_type: string
  file_size: number
  status: 'uploaded' | 'processing' | 'completed' | 'failed'
  error_message?: string
  created_at: string
  updated_at: string
}

export interface AIResult {
  id: string
  document_id: string
  doc_type: string
  confidence: number
  summary?: string
  risks?: any[]
  extracted_data: Record<string, any>
  ai_model?: string
  processing_time?: number
  created_at: string
}

export interface ChatMessage {
  question: string
  answer: string
}
