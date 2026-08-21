/**
 * 當場確認回灌的前後端契約測試(ocr-vlm-consensus 任務 9.3)
 *
 * 驗證前端送出的請求形狀與後端 POST /api/v1/samples/{type}/confirm 相符
 * ——欄位名錯了不會有型別錯誤,只會靜默寫不進樣本,所以要測。
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, confirmationApi } from './api'
import type { FieldDecision } from '@/types/confirmation'

const DECISIONS: FieldDecision[] = [
  { field: 'land_number', action: 'corrected', before: 'O221-OOOO', after: '0221-0000' },
  { field: 'owner', action: 'confirmed', before: '黃水木', after: '黃水木' },
]

afterEach(() => {
  vi.restoreAllMocks()
})

describe('confirmationApi.submit', () => {
  it('打到帶文件類型的 confirm 端點', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: {} } as never)

    await confirmationApi.submit('transcript', '謄本文字', DECISIONS)

    expect(post.mock.calls[0][0]).toBe('/v1/samples/transcript/confirm')
  })

  it('請求主體使用後端的 snake_case 欄位名', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: {} } as never)

    await confirmationApi.submit('contract', '合約文字', DECISIONS)

    const body = post.mock.calls[0][1] as Record<string, unknown>
    expect(Object.keys(body).sort()).toEqual(['decisions', 'page_text'])
    expect(body.page_text).toBe('合約文字')
  })

  it('決定原樣送出,含 action 與 before/after', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: {} } as never)

    await confirmationApi.submit('transcript', '謄本文字', DECISIONS)

    const body = post.mock.calls[0][1] as { decisions: FieldDecision[] }
    expect(body.decisions).toHaveLength(2)
    expect(body.decisions[0]).toEqual({
      field: 'land_number',
      action: 'corrected',
      before: 'O221-OOOO',
      after: '0221-0000',
    })
    // confirmed 也一起送——經人確認的低信心欄位同樣是有效的人工驗證
    expect(body.decisions[1].action).toBe('confirmed')
  })

  it('文件類型會被編進路徑,不同類型不會互相污染樣本庫', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: {} } as never)

    await confirmationApi.submit('bill', '帳單文字', DECISIONS)

    expect(post.mock.calls[0][0]).toBe('/v1/samples/bill/confirm')
  })

  it('回傳後端的回灌結果供畫面回報', async () => {
    vi.spyOn(api, 'post').mockResolvedValue({
      data: {
        document_type: 'transcript',
        created: true,
        sample_id: 'abc',
        fields_written: 2,
        skipped: [],
      },
    } as never)

    const resp = await confirmationApi.submit('transcript', '謄本文字', DECISIONS)
    expect(resp.data.fields_written).toBe(2)
    expect(resp.data.created).toBe(true)
  })
})
