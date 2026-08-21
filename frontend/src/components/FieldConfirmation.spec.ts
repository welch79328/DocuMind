/**
 * 欄位確認介面元件測試(ocr-vlm-consensus 任務 9.1)
 *
 * 驗收標準:
 * - 低信心欄位有明確視覺標示
 * - 不一致欄位可展開檢視各引擎原始值
 * - 使用者可逐欄位確認或修正
 * - 高信心欄位不需使用者操作
 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import FieldConfirmation from './FieldConfirmation.vue'
import { flattenFields } from '@/types/confirmation'

const STRUCTURED = {
  land_number: '0221-0000',
  owner: '黃水木',
  area: '153.00',
  extraction_confidence: 0.9,
  field_confidences: { land_number: 0.42, owner: 0.95, area: 0.88 },
}

const CONFIDENCES = { land_number: 0.42, owner: 0.95, area: 0.88 }

const CONSENSUS = {
  available: true,
  agreements: {
    land_number: {
      value: '0221-0000',
      confidence: 0.3,
      agreed: false,
      engine_values: { paddleocr: '0221-0000', tesseract: 'O221-OOOO' },
    },
    owner: {
      value: '黃水木',
      confidence: 0.95,
      agreed: true,
      engine_values: { paddleocr: '黃水木', tesseract: '黃水木' },
    },
    area: {
      value: '153.00',
      confidence: 0.88,
      agreed: true,
      engine_values: { paddleocr: '153.00', tesseract: '153.00' },
    },
  },
}

function mountComponent(props: Record<string, unknown> = {}) {
  return mount(FieldConfirmation, {
    props: {
      structuredData: STRUCTURED,
      fieldConfidences: CONFIDENCES,
      consensus: CONSENSUS,
      ...props,
    },
  })
}

describe('攤平欄位', () => {
  it('略過 meta 鍵並攤平巢狀區塊(合約形狀)', () => {
    const flat = flattenFields({
      contract_metadata: { contract_number: 'A-001', signing_date: '2026-01-01' },
      parties: { party_a: '甲公司' },
      extraction_confidence: 0.9,
      field_confidences: { contract_number: 0.5 },
    })
    expect(flat).toEqual({
      contract_number: 'A-001',
      signing_date: '2026-01-01',
      party_a: '甲公司',
    })
  })

  it('扁平形狀(謄本/帳單)原樣保留', () => {
    expect(flattenFields({ land_number: '0221-0000' })).toEqual({
      land_number: '0221-0000',
    })
  })

  it('空輸入回傳空物件而非拋錯', () => {
    expect(flattenFields(null)).toEqual({})
    expect(flattenFields(undefined)).toEqual({})
  })
})

describe('低信心欄位有明確視覺標示', () => {
  it('低於門檻的欄位進入待確認區,高於門檻的不進去', () => {
    const wrapper = mountComponent()
    const attention = wrapper.findAll('[data-testid="attention-row"]')
    const fields = attention.map((row) => row.text())

    expect(fields.some((t) => t.includes('land_number'))).toBe(true)
    expect(fields.some((t) => t.includes('owner'))).toBe(false)
  })

  it('待確認列帶有 amber 底色與待確認計數', () => {
    const wrapper = mountComponent()
    const row = wrapper.find('[data-testid="attention-row"]')
    expect(row.classes().join(' ')).toContain('bg-amber-50')
    expect(wrapper.text()).toContain('尚待確認 1 項')
  })

  it('門檻可調整;調高後原本合格的欄位也需確認', () => {
    const wrapper = mountComponent({ threshold: 0.9 })
    const fields = wrapper
      .findAll('[data-testid="attention-row"]')
      .map((row) => row.text())
    // area 0.88 < 0.9,改為需確認
    expect(fields.some((t) => t.includes('area'))).toBe(true)
  })
})

describe('高信心欄位不需使用者操作', () => {
  it('一致且高信心的欄位落在唯讀區,不提供確認按鈕', () => {
    const wrapper = mountComponent()
    const settled = wrapper.findAll('[data-testid="settled-row"]')
    const text = settled.map((row) => row.text()).join(' ')

    expect(text).toContain('owner')
    expect(text).toContain('黃水木')
    expect(wrapper.text()).toContain('以下欄位辨識信心良好，無須確認')
    // 唯讀區內不含任何輸入框
    settled.forEach((row) => expect(row.find('input').exists()).toBe(false))
  })

  it('全部欄位皆高信心時完全不顯示待確認區', () => {
    const wrapper = mountComponent({
      fieldConfidences: { land_number: 0.95, owner: 0.95, area: 0.95 },
      consensus: {
        available: true,
        agreements: {
          land_number: { ...CONSENSUS.agreements.land_number, agreed: true },
          owner: CONSENSUS.agreements.owner,
          area: CONSENSUS.agreements.area,
        },
      },
    })
    expect(wrapper.findAll('[data-testid="attention-row"]')).toHaveLength(0)
    expect(wrapper.text()).not.toContain('請確認以下欄位')
  })
})

describe('不一致欄位可展開檢視各引擎原始值', () => {
  it('預設收合,點擊後列出各引擎判讀', async () => {
    const wrapper = mountComponent()
    expect(wrapper.find('[data-testid="engine-table"]').exists()).toBe(false)

    await wrapper.find('[data-testid="toggle-engines"]').trigger('click')

    const table = wrapper.find('[data-testid="engine-table"]')
    expect(table.exists()).toBe(true)
    expect(table.text()).toContain('paddleocr')
    expect(table.text()).toContain('0221-0000')
    expect(table.text()).toContain('tesseract')
    expect(table.text()).toContain('O221-OOOO')
  })

  it('不一致欄位標示為「引擎判讀不一致」', () => {
    const wrapper = mountComponent()
    expect(wrapper.find('[data-testid="disagree-badge"]').exists()).toBe(true)
  })

  it('共識不可用(單一引擎)時不得宣稱任何欄位不一致', () => {
    const wrapper = mountComponent({
      consensus: { available: false, agreements: CONSENSUS.agreements },
    })
    expect(wrapper.find('[data-testid="disagree-badge"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="toggle-engines"]').exists()).toBe(false)
    // 低信心標示仍在——共識不可用不代表信心度就合格
    expect(wrapper.find('[data-testid="low-badge"]').exists()).toBe(true)
  })

  it('完全沒有共識明細時元件仍可運作', () => {
    const wrapper = mountComponent({ consensus: null })
    expect(wrapper.findAll('[data-testid="attention-row"]')).toHaveLength(1)
    expect(wrapper.find('[data-testid="disagree-badge"]').exists()).toBe(false)
  })
})

describe('使用者可逐欄位確認或修正', () => {
  it('未改值即按確認 → 記為 confirmed', async () => {
    const wrapper = mountComponent()
    await wrapper.find('[data-testid="settle-button"]').trigger('click')

    const decided = wrapper.emitted('decide')?.[0]?.[0] as Record<string, unknown>
    expect(decided).toEqual({
      field: 'land_number',
      action: 'confirmed',
      before: '0221-0000',
      after: '0221-0000',
    })
  })

  it('改值後按確認 → 記為 corrected,並帶出前後值', async () => {
    const wrapper = mountComponent()
    await wrapper.find('[data-testid="attention-row"] input').setValue('0221-0001')
    await wrapper.find('[data-testid="settle-button"]').trigger('click')

    const decided = wrapper.emitted('decide')?.[0]?.[0] as Record<string, unknown>
    expect(decided).toEqual({
      field: 'land_number',
      action: 'corrected',
      before: '0221-0000',
      after: '0221-0001',
    })
  })

  it('change 事件累積所有已決定欄位,供回饋學習取用', async () => {
    const wrapper = mountComponent({ threshold: 0.9 })
    const buttons = wrapper.findAll('[data-testid="settle-button"]')
    for (const button of buttons) await button.trigger('click')

    const emitted = wrapper.emitted('change')
    const latest = emitted?.[emitted.length - 1]?.[0] as Array<{ field: string }>
    expect(latest.map((d) => d.field).sort()).toEqual(['area', 'land_number'])
  })

  it('確認後欄位轉唯讀,可重新編輯撤回決定', async () => {
    const wrapper = mountComponent()
    await wrapper.find('[data-testid="settle-button"]').trigger('click')

    expect(
      wrapper.find('[data-testid="attention-row"] input').attributes('disabled')
    ).toBeDefined()
    expect(wrapper.text()).toContain('尚待確認 0 項')

    await wrapper.find('[data-testid="reopen-button"]').trigger('click')
    expect(
      wrapper.find('[data-testid="attention-row"] input').attributes('disabled')
    ).toBeUndefined()
    expect(wrapper.text()).toContain('尚待確認 1 項')
  })

  it('逐欄位獨立:確認其中一個不影響另一個', async () => {
    const wrapper = mountComponent({ threshold: 0.9 })
    expect(wrapper.findAll('[data-testid="attention-row"]')).toHaveLength(2)

    await wrapper.findAll('[data-testid="settle-button"]')[0].trigger('click')
    expect(wrapper.findAll('[data-testid="settle-button"]')).toHaveLength(1)
    expect(wrapper.text()).toContain('尚待確認 1 項')
  })
})

describe('邊界情況', () => {
  it('無結構化欄位時給出明確說明,不顯示空表', () => {
    const wrapper = mount(FieldConfirmation, {
      props: { structuredData: null, fieldConfidences: {}, consensus: null },
    })
    expect(wrapper.text()).toContain('本頁未取得結構化欄位')
  })

  it('欄位值為 null 時顯示為空字串而非字面 null', () => {
    const wrapper = mount(FieldConfirmation, {
      props: {
        structuredData: { owner: null },
        fieldConfidences: { owner: 0.95 },
        consensus: null,
      },
    })
    const settled = wrapper.find('[data-testid="settled-row"]')
    expect(settled.text()).toContain('（未提取）')
    expect(settled.text()).not.toContain('null')
  })

  it('僅有信心度、沒有欄位值時仍列出該欄位', () => {
    const wrapper = mount(FieldConfirmation, {
      props: {
        structuredData: {},
        fieldConfidences: { land_number: 0.2 },
        consensus: null,
      },
    })
    expect(wrapper.find('[data-testid="attention-row"]').text()).toContain('land_number')
  })
})
