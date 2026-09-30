import { describe, it, expect } from 'vitest'
import { buildRows } from './reviewRows'

describe('buildRows', () => {
  const orig = {
    field_confidences: { owner: 0.9, land_number: 0.9 },
    pages: [
      {
        structured_data: {
          owner: '王**',
          land_number: '0931-0000',
          needs_confirmation: ['rights_scope'],
          extraction_confidence: 0.6,
          has_building_evidence: true,
          owners: [{ part: 'building', order: '0003', name: '王**', rights_scope: '3分之1' }],
          land_numbers: [{ section: '文化北段', number: '0931-0000' }],
        },
      },
    ],
  }

  it('只列欄位,不列中繼資料與清單明細', () => {
    const keys = buildRows(orig).map((r) => r.key).sort()
    expect(keys).toEqual(['land_number', 'owner'])
  })

  it('不會產生 [object Object] 的列', () => {
    expect(buildRows(orig).some((r) => r.value.includes('[object Object]'))).toBe(false)
  })

  it('欄位值與信心度照舊', () => {
    const owner = buildRows(orig).find((r) => r.key === 'owner')
    expect(owner).toEqual({ key: 'owner', value: '王**', confidence: 0.9 })
  })
})
