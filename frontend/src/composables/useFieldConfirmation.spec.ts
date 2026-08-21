/**
 * 當場確認送出流程測試(ocr-vlm-consensus 任務 9.3)
 *
 * 涵蓋:逐頁彙整、逐頁送出、成功後清空(避免重複沉澱)、失敗後保留。
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { confirmationApi } from '@/services/api'
import { useFieldConfirmation } from './useFieldConfirmation'
import type { FieldDecision } from '@/types/confirmation'

const D1: FieldDecision = {
  field: 'land_number', action: 'corrected', before: 'O221', after: '0221-0000',
}
const D2: FieldDecision = {
  field: 'owner', action: 'confirmed', before: '黃水木', after: '黃水木',
}

const PAGE_TEXTS = ['第一頁文字', '第二頁文字']

function setup() {
  return useFieldConfirmation(
    () => 'transcript',
    (index: number) => PAGE_TEXTS[index] ?? ''
  )
}

function mockSubmit(fieldsWritten = 1) {
  return vi.spyOn(confirmationApi, 'submit').mockResolvedValue({
    data: {
      document_type: 'transcript',
      created: true,
      sample_id: 'x',
      fields_written: fieldsWritten,
      skipped: [],
    },
  } as never)
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('逐頁彙整', () => {
  it('多頁決定合併計數', () => {
    const c = setup()
    c.onDecisionsChange(0, [D1])
    c.onDecisionsChange(1, [D2])
    expect(c.allDecisions.value).toHaveLength(2)
  })

  it('同一頁再次變更會覆蓋而非累加', () => {
    const c = setup()
    c.onDecisionsChange(0, [D1])
    c.onDecisionsChange(0, [D1, D2])
    expect(c.allDecisions.value).toHaveLength(2)
  })
})

describe('送出', () => {
  it('沒有任何決定時完全不呼叫 API', async () => {
    const submit = mockSubmit()
    const c = setup()
    await c.submit()
    expect(submit).not.toHaveBeenCalled()
  })

  it('逐頁分別送出,各自帶該頁文字', async () => {
    const submit = mockSubmit()
    const c = setup()
    c.onDecisionsChange(0, [D1])
    c.onDecisionsChange(1, [D2])

    await c.submit()

    expect(submit).toHaveBeenCalledTimes(2)
    expect(submit.mock.calls[0][1]).toBe('第一頁文字')
    expect(submit.mock.calls[1][1]).toBe('第二頁文字')
  })

  it('空決定的頁面不送出', async () => {
    const submit = mockSubmit()
    const c = setup()
    c.onDecisionsChange(0, [D1])
    c.onDecisionsChange(1, [])

    await c.submit()
    expect(submit).toHaveBeenCalledTimes(1)
  })

  it('回報後端實際寫入的欄位數', async () => {
    mockSubmit(2)
    const c = setup()
    c.onDecisionsChange(0, [D1, D2])

    await c.submit()
    expect(c.message.value).toEqual({ type: 'success', text: '已回饋 2 個欄位，將用於改善後續辨識' })
  })
})

describe('成功後清空,避免重複沉澱', () => {
  it('送出成功即清空決定', async () => {
    mockSubmit()
    const c = setup()
    c.onDecisionsChange(0, [D1])

    await c.submit()
    expect(c.allDecisions.value).toHaveLength(0)
  })

  it('連按兩次只會真的送出一次', async () => {
    const submit = mockSubmit()
    const c = setup()
    c.onDecisionsChange(0, [D1])

    await c.submit()
    await c.submit()

    expect(submit).toHaveBeenCalledTimes(1)
  })
})

describe('失敗處理', () => {
  it('送出失敗時保留決定,使用者可原地重試', async () => {
    vi.spyOn(confirmationApi, 'submit').mockRejectedValue(new Error('boom'))
    const c = setup()
    c.onDecisionsChange(0, [D1])

    await c.submit()

    expect(c.message.value?.type).toBe('error')
    expect(c.allDecisions.value).toHaveLength(1)
  })

  it('失敗後重試成功即清空', async () => {
    const spy = vi
      .spyOn(confirmationApi, 'submit')
      .mockRejectedValueOnce(new Error('boom'))
    const c = setup()
    c.onDecisionsChange(0, [D1])
    await c.submit()

    spy.mockResolvedValue({
      data: { document_type: 'transcript', created: true, sample_id: 'x', fields_written: 1, skipped: [] },
    } as never)
    await c.submit()

    expect(c.message.value?.type).toBe('success')
    expect(c.allDecisions.value).toHaveLength(0)
  })

  it('送出過程中 submitting 為真,結束後歸位', async () => {
    mockSubmit()
    const c = setup()
    c.onDecisionsChange(0, [D1])

    const pending = c.submit()
    expect(c.submitting.value).toBe(true)
    await pending
    expect(c.submitting.value).toBe(false)
  })
})
