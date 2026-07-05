// 人工複核相關型別

export type ReviewStatus = 'pending' | 'in_review' | 'completed'

export interface ReviewItem {
  id: string
  document_id: string | null
  document_type: string
  overall_confidence: number | null
  status: ReviewStatus
  reviewer: string | null
  original_result: Record<string, unknown>
  corrected_result: Record<string, unknown> | null
}

export interface ReviewQueueResponse {
  items: ReviewItem[]
}

export interface SubmitDiff {
  [field: string]: { before: unknown; after: unknown }
}
