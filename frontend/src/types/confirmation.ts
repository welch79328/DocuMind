// 使用者當場確認流程相關型別(ocr-vlm-consensus 需求 4.4)
//
// 對應後端 PageResult 的 field_confidences 與選填的 consensus 明細。
// consensus 在共識模式關閉時整個不存在,因此所有相關型別皆為選填。

/** 單一欄位的共識狀態(後端 FieldAgreement) */
export interface FieldAgreement {
  value: unknown
  confidence: number
  agreed: boolean
  /** 各引擎的原始判讀:{ paddleocr: '0221-0000', tesseract: 'O221-OOOO' } */
  engine_values: Record<string, unknown>
}

/** 頁面層共識明細;available=false 代表只有單一候選,不得宣稱已達成共識 */
export interface ConsensusDetail {
  available: boolean
  agreements: Record<string, FieldAgreement>
}

/** 使用者對單一欄位的處置 */
export type FieldAction = 'confirmed' | 'corrected'

/** 欄位確認元件對外送出的單筆結果 */
export interface FieldDecision {
  field: string
  action: FieldAction
  before: unknown
  after: unknown
}

/** 元件內部的欄位列狀態 */
export interface ConfirmationRow {
  field: string
  /** 使用者可編輯的目前值 */
  value: string
  /** 進入畫面時的原始值,供 9.2 產生 before/after 差異 */
  original: string
  confidence: number | null
  /** 低於門檻,需使用者確認 */
  low: boolean
  /** 多引擎判讀不一致(僅共識可用時才有意義) */
  disagreed: boolean
  engineValues: Record<string, unknown>
  action: FieldAction | null
  expanded: boolean
}

/**
 * structured_data 中不屬於「欄位」的鍵。
 * 與後端 field_consensus._META_KEYS 對齊,兩邊都攤平一層巢狀區塊。
 */
export const META_KEYS: ReadonlySet<string> = new Set([
  'field_confidences',
  'needs_confirmation',
  'extraction_confidence',
  'llm_used_for_extraction',
])

/**
 * 把後端的 structured_data 攤平成 { 欄位名: 值 }。
 *
 * 謄本/帳單本來就是扁平的;合約是巢狀的(contract_metadata / parties /
 * financial_terms),需攤平一層才能與共識明細的欄位名對得起來
 * ——後端 field_candidate_from_extraction 用的是同一套規則。
 */
export function flattenFields(
  structuredData: Record<string, unknown> | null | undefined
): Record<string, unknown> {
  const fields: Record<string, unknown> = {}
  if (!structuredData) return fields

  for (const [key, value] of Object.entries(structuredData)) {
    if (META_KEYS.has(key)) continue
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      Object.assign(fields, value as Record<string, unknown>)
    } else {
      fields[key] = value
    }
  }
  return fields
}
