import { META_KEYS } from '@/types/confirmation'

export interface FieldRow {
  key: string
  value: string
  confidence: number | null
}

/**
 * 把複核項目的原始結果攤成「一欄一列」供人工更正。
 *
 * 只收欄位,跳過 META_KEYS(信心度、待確認清單、旗標、清單明細)。
 * 原本沒跳過:中繼資料被列成可編輯的一列,而清單明細(owners 等)經 String()
 * 會變成「[object Object]」,更正送出時還會把這串字當成欄位值寫回去。
 */
export function buildRows(orig: Record<string, unknown> | undefined): FieldRow[] {
  const fc = (orig?.field_confidences as Record<string, number>) || {}
  const fields: Record<string, unknown> = {}
  const pages = orig?.pages
  if (Array.isArray(pages)) {
    pages.forEach((p) => {
      const sd = (p as { structured_data?: Record<string, unknown> })?.structured_data
      if (sd && typeof sd === 'object') Object.assign(fields, sd)
    })
  }
  const keys = new Set<string>([...Object.keys(fc), ...Object.keys(fields)])
  return [...keys]
    .filter((k) => !META_KEYS.has(k))
    .map((k) => ({
      key: k,
      value: fields[k] != null ? String(fields[k]) : '',
      confidence: fc[k] ?? null,
    }))
}
