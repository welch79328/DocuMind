<script setup lang="ts">
import { ref, computed } from 'vue'

const file = ref<File | null>(null)
const testing = ref(false)
const result = ref<any>(null)
const groundTruth = ref('')
const enableLlm = ref(true)
const currentPageIndex = ref(0)  // 當前查看的頁面索引（0-based）
const documentType = ref<'transcript' | 'contract'>('transcript')  // 文件類型選擇

// 合併所有頁面的最終文字
const mergedText = computed(() => {
  if (!result.value || !result.value.pages) return ''

  return result.value.pages.map((page: any) => {
    // 優先使用 LLM 修正結果，否則使用規則後處理結果
    let text = ''
    if (page.llm_postprocessed && page.llm_postprocessed.used && page.llm_postprocessed.text) {
      text = page.llm_postprocessed.text
    } else if (page.rule_postprocessed && page.rule_postprocessed.text) {
      text = page.rule_postprocessed.text
    } else if (page.ocr_raw && page.ocr_raw.text) {
      text = page.ocr_raw.text
    }

    return `========== 第 ${page.page_number} 頁 ==========\n\n${text}\n\n`
  }).join('')
})

// 計算總體統計
const totalStats = computed(() => {
  if (!result.value || !result.value.pages) return null

  let totalCost = 0
  let llmUsedCount = 0
  let totalTypoFixes = 0
  let totalFormatCorrections = 0

  result.value.pages.forEach((page: any) => {
    // 檢查 OCR 後處理 LLM 使用
    let llmUsedForThisPage = false

    if (page.llm_postprocessed && page.llm_postprocessed.used) {
      llmUsedForThisPage = true
      if (page.llm_postprocessed.stats && page.llm_postprocessed.stats.llm_cost) {
        totalCost += page.llm_postprocessed.stats.llm_cost
      }
    }

    // 檢查合約欄位提取 LLM 使用
    if (page.structured_data && page.structured_data.llm_used_for_extraction) {
      llmUsedForThisPage = true
      // 欄位提取 LLM 成本（若有的話，目前未實作）
    }

    if (llmUsedForThisPage) {
      llmUsedCount++
    }

    if (page.rule_postprocessed && page.rule_postprocessed.stats) {
      totalTypoFixes += page.rule_postprocessed.stats.typo_fixes || 0
      totalFormatCorrections += page.rule_postprocessed.stats.format_corrections || 0
    }
  })

  return {
    totalCost,
    llmUsedCount,
    totalTypoFixes,
    totalFormatCorrections
  }
})

const handleFileChange = (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files && target.files[0]) {
    file.value = target.files[0]
    // 重置結果和當前頁
    result.value = null
    currentPageIndex.value = 0
  }
}

const testOcr = async () => {
  if (!file.value) return

  testing.value = true

  try {
    const formData = new FormData()
    formData.append('file', file.value)
    if (groundTruth.value.trim()) {
      formData.append('ground_truth', groundTruth.value.trim())
    }

    // enable_llm 和 document_type 必須通過 URL 查詢參數傳遞
    const queryParams = new URLSearchParams({
      enable_llm: enableLlm.value.toString(),
      document_type: documentType.value
    })

    const response = await fetch(`/api/v1/ocr/test?${queryParams}`, {
      method: 'POST',
      body: formData
    })

    if (!response.ok) throw new Error('OCR test failed')

    const data = await response.json()
    result.value = data
    currentPageIndex.value = 0  // 重置到第一頁
  } catch (error) {
    console.error('OCR test error:', error)
    alert('OCR 測試失敗，請稍後再試')
  } finally {
    testing.value = false
  }
}

const copyToClipboard = async () => {
  try {
    await navigator.clipboard.writeText(mergedText.value)
    alert('✅ 已複製到剪貼板')
  } catch (err) {
    console.error('複製失敗:', err)
    alert('❌ 複製失敗，請手動選取文字複製')
  }
}
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <h2 class="text-3xl font-bold text-gray-900 mb-2">OCR 辨識測試</h2>
    <p class="text-gray-600 mb-8">上傳 PDF 或圖片，對比原始 OCR、規則後處理和 LLM 智能修正的效果</p>

    <!-- 上傳區塊 -->
    <div class="bg-white rounded-lg shadow p-6 mb-8">
      <h3 class="text-lg font-semibold mb-4">上傳測試檔案</h3>

      <!-- 文件類型選擇 -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 mb-2">
          文件類型
        </label>
        <select
          v-model="documentType"
          class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
        >
          <option value="transcript">謄本</option>
          <option value="contract">合約</option>
        </select>
        <p class="mt-1 text-xs text-gray-500">
          💡 不同文件類型會使用對應的處理器與欄位提取
        </p>
      </div>

      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 mb-2">
          選擇檔案
        </label>
        <input
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          @change="handleFileChange"
          class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
        />
      </div>

      <div v-if="file" class="mb-4 p-3 bg-gray-50 rounded">
        <p class="text-sm text-gray-700">
          <strong>檔案：</strong> {{ file.name }}
          ({{ (file.size / 1024 / 1024).toFixed(2) }} MB)
        </p>
        <p class="text-xs text-gray-500 mt-1">
          ℹ️ 系統將自動處理所有頁面
        </p>
      </div>

      <!-- Ground Truth (可選) -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 mb-2">
          標準答案（可選，用於計算準確率）
        </label>
        <textarea
          v-model="groundTruth"
          rows="4"
          class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
          placeholder="貼上正確的文字內容，用於計算準確率..."
        ></textarea>
      </div>

      <!-- LLM 選項 -->
      <div class="mb-4">
        <label class="flex items-center">
          <input
            type="checkbox"
            v-model="enableLlm"
            class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <span class="ml-2 text-sm text-gray-700">
            啟用 LLM 智能修正（GPT-4o，成本約 $0.01/份）
          </span>
        </label>
      </div>

      <button
        @click="testOcr"
        :disabled="!file || testing"
        class="w-full flex justify-center py-2.5 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <svg v-if="testing" class="animate-spin mr-2 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span v-if="testing">測試中...</span>
        <span v-else>開始測試</span>
      </button>
    </div>

    <!-- 測試結果 -->
    <div v-if="result && result.pages && result.pages.length > 0" class="space-y-6">
      <!-- 合約結構化欄位顯示 -->
      <div v-if="result.document_type === 'contract'" class="bg-white rounded-lg shadow p-6">
        <h3 class="text-xl font-semibold mb-4">📋 合約欄位提取結果</h3>

        <div v-for="(page, index) in result.pages" :key="index" class="mb-6 last:mb-0">
          <div v-if="page.structured_data" class="border border-gray-200 rounded-lg p-4">
            <div class="flex items-center justify-between mb-4">
              <h4 class="text-lg font-medium text-gray-900">第 {{ page.page_number }} 頁</h4>
              <div class="flex items-center">
                <span class="text-sm text-gray-600 mr-2">提取信心度:</span>
                <span
                  :class="{
                    'text-green-600 font-semibold': page.structured_data.extraction_confidence >= 0.7,
                    'text-yellow-600 font-semibold': page.structured_data.extraction_confidence >= 0.5 && page.structured_data.extraction_confidence < 0.7,
                    'text-red-600 font-semibold': page.structured_data.extraction_confidence < 0.5
                  }"
                >
                  {{ (page.structured_data.extraction_confidence * 100).toFixed(1) }}%
                </span>
              </div>
            </div>

            <!-- 合約元資訊 -->
            <div class="mb-4">
              <h5 class="text-sm font-semibold text-gray-700 mb-2 border-b pb-1">合約元資訊</h5>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <div class="text-xs text-gray-500">合約編號</div>
                  <div class="text-sm font-medium mt-1">
                    {{ page.structured_data.contract_metadata?.contract_number || '未提取' }}
                  </div>
                </div>
                <div>
                  <div class="text-xs text-gray-500">簽訂日期</div>
                  <div class="text-sm font-medium mt-1">
                    {{ page.structured_data.contract_metadata?.signing_date || '未提取' }}
                  </div>
                </div>
                <div>
                  <div class="text-xs text-gray-500">生效日期</div>
                  <div class="text-sm font-medium mt-1">
                    {{ page.structured_data.contract_metadata?.effective_date || '未提取' }}
                  </div>
                </div>
              </div>
            </div>

            <!-- 雙方資訊 -->
            <div class="mb-4">
              <h5 class="text-sm font-semibold text-gray-700 mb-2 border-b pb-1">雙方資訊</h5>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <div class="text-xs text-gray-500">甲方</div>
                  <div class="text-sm font-medium mt-1">
                    {{ page.structured_data.parties?.party_a || '未提取' }}
                  </div>
                  <div v-if="page.structured_data.parties?.party_a_address" class="text-xs text-gray-500 mt-1">
                    地址: {{ page.structured_data.parties.party_a_address }}
                  </div>
                </div>
                <div>
                  <div class="text-xs text-gray-500">乙方</div>
                  <div class="text-sm font-medium mt-1">
                    {{ page.structured_data.parties?.party_b || '未提取' }}
                  </div>
                  <div v-if="page.structured_data.parties?.party_b_address" class="text-xs text-gray-500 mt-1">
                    地址: {{ page.structured_data.parties.party_b_address }}
                  </div>
                </div>
              </div>
            </div>

            <!-- 財務條款 -->
            <div>
              <h5 class="text-sm font-semibold text-gray-700 mb-2 border-b pb-1">財務條款</h5>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <div class="text-xs text-gray-500">合約金額</div>
                  <div class="text-sm font-medium mt-1">
                    <span v-if="page.structured_data.financial_terms?.contract_amount">
                      {{ page.structured_data.financial_terms.currency || 'TWD' }}
                      {{ Number(page.structured_data.financial_terms.contract_amount).toLocaleString() }}
                    </span>
                    <span v-else>未提取</span>
                  </div>
                </div>
                <div>
                  <div class="text-xs text-gray-500">付款方式</div>
                  <div class="text-sm font-medium mt-1">
                    {{ page.structured_data.financial_terms?.payment_method || '未提取' }}
                  </div>
                </div>
                <div>
                  <div class="text-xs text-gray-500">付款期限</div>
                  <div class="text-sm font-medium mt-1">
                    {{ page.structured_data.financial_terms?.payment_deadline || '未提取' }}
                  </div>
                </div>
              </div>
            </div>

            <!-- 低信心度警告 -->
            <div v-if="page.structured_data.extraction_confidence < 0.7" class="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded">
              <div class="flex items-start">
                <svg class="h-5 w-5 text-yellow-600 mr-2 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
                </svg>
                <div class="text-sm text-yellow-800">
                  <strong>提取信心度較低</strong> - 建議啟用 LLM 輔助提升準確率
                </div>
              </div>
            </div>
          </div>

          <!-- 無結構化資料時顯示 -->
          <div v-else class="border border-gray-200 rounded-lg p-4 text-center text-gray-500">
            <p>第 {{ page.page_number }} 頁未提取到結構化欄位</p>
          </div>
        </div>
      </div>

      <!-- 總覽資訊 -->
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-xl font-semibold">
            📄 已處理 {{ result.total_pages }} 頁，以下顯示所有結果
          </h3>
          <button
            @click="copyToClipboard"
            class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            📋 複製全文
          </button>
        </div>

        <!-- 統計資訊 -->
        <div v-if="totalStats" class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          <div class="bg-gray-50 p-3 rounded">
            <div class="text-xs text-gray-600 mb-1">錯別字修正</div>
            <div class="text-lg font-semibold">{{ totalStats.totalTypoFixes }} 次</div>
          </div>
          <div class="bg-gray-50 p-3 rounded">
            <div class="text-xs text-gray-600 mb-1">格式校正</div>
            <div class="text-lg font-semibold">{{ totalStats.totalFormatCorrections }} 次</div>
          </div>
          <div class="bg-gray-50 p-3 rounded">
            <div class="text-xs text-gray-600 mb-1">LLM 使用</div>
            <div class="text-lg font-semibold">{{ totalStats.llmUsedCount }} / {{ result.total_pages }} 頁</div>
          </div>
          <div class="bg-gray-50 p-3 rounded">
            <div class="text-xs text-gray-600 mb-1">總成本</div>
            <div class="text-lg font-semibold">${{ totalStats.totalCost.toFixed(6) }}</div>
          </div>
        </div>

        <!-- 合併文字顯示 -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">
            🤖 最終辨識結果（優先顯示 LLM 智能修正）
          </label>
          <textarea
            :value="mergedText"
            readonly
            rows="30"
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm font-mono"
            style="resize: vertical;"
          ></textarea>
        </div>
      </div>
    </div>
  </div>
</template>
