<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { reviewApi } from '@/services/api'
import type { ReviewItem, SubmitDiff } from '@/types/review'

const route = useRoute()
const router = useRouter()
const itemId = route.params.id as string

const reviewer = ref<string>(localStorage.getItem('reviewer_name') || '')
const item = ref<ReviewItem | null>(null)
const loading = ref(true)
const submitting = ref(false)
const loadError = ref('')
const message = ref<{ type: 'error' | 'success'; text: string } | null>(null)
const resultDiff = ref<SubmitDiff | null>(null)

const LOW_CONFIDENCE = 0.8

interface FieldRow {
  key: string
  value: string
  confidence: number | null
}

const rows = ref<FieldRow[]>([])

const docTypeLabels: Record<string, string> = {
  transcript: '建物土地謄本',
  bill: '帳單',
  contract: '合約',
  repair_photo: '修繕照片',
}

// 原始 OCR 文字(供對照)
const originalText = computed<string>(() => {
  const orig = item.value?.original_result as Record<string, unknown> | undefined
  const pages = orig?.pages
  if (Array.isArray(pages)) {
    return pages
      .map((p) => (p as { ocr_raw?: { text?: string } })?.ocr_raw?.text || '')
      .filter(Boolean)
      .join('\n\n——\n\n')
  }
  return orig ? JSON.stringify(orig, null, 2) : ''
})

function buildRows(orig: Record<string, unknown> | undefined): FieldRow[] {
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
  return [...keys].map((k) => ({
    key: k,
    value: fields[k] != null ? String(fields[k]) : '',
    confidence: fc[k] ?? null,
  }))
}

function addField() {
  rows.value.push({ key: '', value: '', confidence: null })
}

function removeField(index: number) {
  rows.value.splice(index, 1)
}

function isLow(row: FieldRow): boolean {
  return row.confidence !== null && row.confidence < LOW_CONFIDENCE
}

async function load() {
  loading.value = true
  try {
    const resp = await reviewApi.getItem(itemId)
    item.value = resp.data
    rows.value = buildRows(resp.data.original_result as Record<string, unknown>)
  } catch (err: unknown) {
    const status = (err as { response?: { status?: number } })?.response?.status
    loadError.value = status === 404 ? '找不到此複核項目' : '載入失敗，請稍後再試'
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (!reviewer.value.trim()) {
    message.value = { type: 'error', text: '請先於複核佇列頁輸入複核者名稱' }
    return
  }
  const corrected: Record<string, unknown> = {}
  for (const row of rows.value) {
    if (row.key.trim()) corrected[row.key.trim()] = row.value
  }
  submitting.value = true
  try {
    const resp = await reviewApi.submit(itemId, reviewer.value.trim(), corrected)
    resultDiff.value = resp.data.diff
    message.value = { type: 'success', text: '校正已提交，狀態已更新為「已完成」' }
  } catch (err: unknown) {
    const status = (err as { response?: { status?: number } })?.response?.status
    if (status === 403) {
      message.value = { type: 'error', text: '僅認領者可提交校正' }
    } else if (status === 404) {
      message.value = { type: 'error', text: '找不到此複核項目' }
    } else {
      message.value = { type: 'error', text: '提交失敗，請稍後再試' }
    }
  } finally {
    submitting.value = false
  }
}

function backToQueue() {
  router.push({ name: 'review' })
}

onMounted(load)
</script>

<template>
  <div class="max-w-6xl mx-auto p-6">
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-2xl font-bold text-gray-800">✏️ 校正文件</h1>
      <button @click="backToQueue" class="text-sm text-gray-600 hover:text-gray-900">
        ← 返回佇列
      </button>
    </div>

    <div v-if="loading" class="text-gray-500 py-8 text-center">載入中…</div>
    <div v-else-if="loadError" class="bg-red-50 text-red-700 px-4 py-3 rounded">
      {{ loadError }}
    </div>

    <template v-else-if="item">
      <p class="text-sm text-gray-500 mb-4">
        文件類型：{{ docTypeLabels[item.document_type] || item.document_type }}
        ｜ 狀態：{{ item.status }} ｜ 認領者：{{ item.reviewer || '—' }}
      </p>

      <div
        v-if="message"
        :class="[
          'mb-4 px-4 py-2 rounded text-sm',
          message.type === 'error' ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700',
        ]"
      >
        {{ message.text }}
      </div>

      <!-- 原文 ↔ 欄位並列 -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- 左:原始 OCR 文字 -->
        <div>
          <h2 class="text-sm font-semibold text-gray-600 mb-2">原始辨識文字（對照）</h2>
          <pre
            class="bg-gray-50 border rounded p-3 text-sm text-gray-800 whitespace-pre-wrap h-[28rem] overflow-auto"
            >{{ originalText || '（無原始文字）' }}</pre
          >
        </div>

        <!-- 右:可編輯欄位 -->
        <div>
          <h2 class="text-sm font-semibold text-gray-600 mb-2">
            校正欄位<span class="text-xs text-amber-600 ml-2">（黃底為低信心，需確認）</span>
          </h2>
          <div class="space-y-2 h-[28rem] overflow-auto pr-1">
            <div
              v-for="(row, index) in rows"
              :key="index"
              :class="['flex gap-2 items-center p-2 rounded', isLow(row) ? 'bg-amber-50' : '']"
            >
              <input
                v-model="row.key"
                placeholder="欄位名稱"
                class="border rounded px-2 py-1 w-40 text-sm"
              />
              <input
                v-model="row.value"
                placeholder="校正後的值"
                class="border rounded px-2 py-1 flex-1 text-sm"
              />
              <span v-if="row.confidence !== null" class="text-xs text-gray-400 w-12">
                {{ Math.round(row.confidence * 100) }}%
              </span>
              <button
                @click="removeField(index)"
                class="text-gray-400 hover:text-red-600 text-sm px-1"
                title="移除"
              >
                ✕
              </button>
            </div>
            <button
              @click="addField"
              class="text-sm text-blue-600 hover:text-blue-800 mt-2"
            >
              ＋ 新增欄位
            </button>
          </div>

          <div class="mt-4 flex items-center gap-3">
            <button
              @click="submit"
              :disabled="submitting"
              class="bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded px-5 py-2"
            >
              {{ submitting ? '提交中…' : '提交校正' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 提交後差異 -->
      <div v-if="resultDiff" class="mt-6">
        <h2 class="text-sm font-semibold text-gray-600 mb-2">本次校正差異</h2>
        <table class="text-sm border-collapse">
          <thead>
            <tr class="text-left text-gray-500 border-b">
              <th class="py-1 pr-6">欄位</th>
              <th class="py-1 pr-6">校正前</th>
              <th class="py-1">校正後</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(change, field) in resultDiff" :key="field" class="border-b">
              <td class="py-1 pr-6 font-medium">{{ field }}</td>
              <td class="py-1 pr-6 text-red-600">{{ change.before ?? '（空）' }}</td>
              <td class="py-1 text-green-700">{{ change.after ?? '（空）' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>
