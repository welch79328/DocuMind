/**
 * 當場確認送出流程(ocr-vlm-consensus 任務 9.2 / 9.3)
 *
 * 從結果頁抽出來,讓「逐頁彙整 → 送出 → 成功後清空」這條流程可被測試。
 * 留在 view 裡的話,要測就得連檔案上傳與 fetch 一起搬進來。
 */
import { computed, ref } from 'vue'
import { confirmationApi } from '@/services/api'
import type { FieldDecision } from '@/types/confirmation'

export type ConfirmMessage = { type: 'error' | 'success'; text: string }

export function useFieldConfirmation(
  documentType: () => string,
  pageTextOf: (pageIndex: number) => string
) {
  const pageDecisions = ref<Record<number, FieldDecision[]>>({})
  const submitting = ref(false)
  const message = ref<ConfirmMessage | null>(null)

  const allDecisions = computed<FieldDecision[]>(() =>
    Object.values(pageDecisions.value).flat()
  )

  function onDecisionsChange(pageIndex: number, decisions: FieldDecision[]) {
    pageDecisions.value = { ...pageDecisions.value, [pageIndex]: decisions }
  }

  async function submit() {
    if (allDecisions.value.length === 0) return
    submitting.value = true
    message.value = null
    try {
      let written = 0
      // 逐頁送出:版型指紋與 input_ref 都以該頁文字為準,混頁會讓兩者失真
      for (const [index, decisions] of Object.entries(pageDecisions.value)) {
        if (!decisions.length) continue
        const resp = await confirmationApi.submit(
          documentType(),
          pageTextOf(Number(index)),
          decisions
        )
        written += resp.data.fields_written
      }
      // 成功即清空,避免重複點擊把同一組確認重覆沉澱、在 few-shot 被加權
      pageDecisions.value = {}
      message.value = {
        type: 'success',
        text: `已回饋 ${written} 個欄位，將用於改善後續辨識`,
      }
    } catch {
      // 失敗不清空,使用者可原地重試,不必重新逐欄確認一次
      message.value = { type: 'error', text: '回饋失敗，請稍後再試' }
    } finally {
      submitting.value = false
    }
  }

  function reset() {
    pageDecisions.value = {}
    message.value = null
  }

  return { pageDecisions, submitting, message, allDecisions, onDecisionsChange, submit, reset }
}
