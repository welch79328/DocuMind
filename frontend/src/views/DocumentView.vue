<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const documentId = route.params.id as string

const document = ref<any>(null)
const aiResult = ref<any>(null)
const ocrResult = ref<any>(null)
const loading = ref(true)
const processing = ref(false)

const fetchDocument = async () => {
  try {
    const response = await fetch(`/api/v1/documents/${documentId}`)
    document.value = await response.json()

    // Fetch AI result
    const aiResponse = await fetch(`/api/v1/documents/${documentId}/ai-result`)
    if (aiResponse.ok) {
      aiResult.value = await aiResponse.json()
    }

    // Fetch OCR result
    const ocrResponse = await fetch(`/api/v1/documents/${documentId}/ocr-result`)
    if (ocrResponse.ok) {
      ocrResult.value = await ocrResponse.json()
    }
  } catch (error) {
    console.error('Fetch error:', error)
  } finally {
    loading.value = false
  }
}

const processDocument = async () => {
  try {
    processing.value = true
    await fetch(`/api/v1/documents/${documentId}/process`, {
      method: 'POST'
    })

    // Polling for result
    const pollInterval = setInterval(async () => {
      await fetchDocument()
      if (document.value?.status === 'completed' || document.value?.status === 'failed') {
        clearInterval(pollInterval)
        processing.value = false
      }
    }, 2000)
  } catch (error) {
    console.error('Process error:', error)
    processing.value = false
  }
}

onMounted(() => {
  fetchDocument()
})
</script>

<template>
  <div class="max-w-4xl mx-auto">
    <div v-if="loading" class="text-center py-12">
      <p class="text-gray-500">載入中...</p>
    </div>

    <div v-else-if="document">
      <h2 class="text-2xl font-bold text-gray-900 mb-6">
        文件詳情
      </h2>

      <!-- Document Info -->
      <div class="bg-white rounded-lg shadow p-6 mb-6" style="width: 896px; max-width: 100%;">
        <h3 class="text-lg font-semibold mb-4">基本資訊</h3>
        <dl class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <dt class="text-sm font-medium text-gray-500">檔案名稱</dt>
            <dd class="mt-1 text-sm text-gray-900">{{ document.file_name }}</dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500">檔案大小</dt>
            <dd class="mt-1 text-sm text-gray-900">{{ (document.file_size / 1024 / 1024).toFixed(2) }} MB</dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500">狀態</dt>
            <dd class="mt-1">
              <span
                :class="{
                  'px-2 inline-flex text-xs leading-5 font-semibold rounded-full': true,
                  'bg-green-100 text-green-800': document.status === 'completed',
                  'bg-yellow-100 text-yellow-800': document.status === 'processing',
                  'bg-gray-100 text-gray-800': document.status === 'uploaded',
                  'bg-red-100 text-red-800': document.status === 'failed'
                }"
              >
                {{ document.status === 'uploaded' ? '已上傳' :
                   document.status === 'processing' ? '處理中' :
                   document.status === 'completed' ? '已完成' :
                   document.status === 'failed' ? '處理失敗' : document.status }}
              </span>
            </dd>
          </div>
          <div v-if="ocrResult">
            <dt class="text-sm font-medium text-gray-500">頁數</dt>
            <dd class="mt-1 text-sm text-gray-900">{{ ocrResult.page_count }} 頁</dd>
          </div>
        </dl>

        <!-- Processing Button -->
        <button
          v-if="document.status === 'uploaded'"
          @click="processDocument"
          :disabled="processing"
          class="mt-6 w-full flex items-center justify-center px-4 py-2.5 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-none"
        >
          <svg v-if="processing" class="animate-spin mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span>{{ processing ? '處理中...' : '開始處理' }}</span>
        </button>

        <!-- Processing Status -->
        <div v-if="document.status === 'processing' || processing" class="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-md" style="max-width: 100%; overflow: hidden;">
          <div class="flex items-center">
            <svg class="animate-spin h-5 w-5 text-yellow-600 mr-3" style="flex-shrink: 0;" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <div style="min-width: 0; flex: 1; overflow: hidden; text-overflow: ellipsis;">
              <p class="text-sm font-medium text-yellow-800">正在處理文件...</p>
              <p class="text-xs text-yellow-600 mt-1">包括 OCR 文字識別和 AI 分析，預計需要 30-60 秒</p>
            </div>
          </div>
        </div>
      </div>

      <!-- AI Result -->
      <div v-if="aiResult" class="bg-white rounded-lg shadow p-6" style="width: 100%; max-width: 896px;">
        <h3 class="text-lg font-semibold mb-4">AI 分析結果</h3>

        <div class="mb-4">
          <h4 class="text-sm font-medium text-gray-500 mb-2">文件類型</h4>
          <p class="text-sm text-gray-900">{{ aiResult.doc_type }}</p>
        </div>

        <div class="mb-4">
          <h4 class="text-sm font-medium text-gray-500 mb-2">信心度</h4>
          <p class="text-sm text-gray-900">{{ aiResult.confidence }}%</p>
        </div>

        <div v-if="aiResult.summary" class="mb-4">
          <h4 class="text-sm font-medium text-gray-500 mb-2">摘要</h4>
          <p class="text-sm text-gray-900">{{ aiResult.summary }}</p>
        </div>

        <div v-if="aiResult.extracted_data">
          <h4 class="text-sm font-medium text-gray-500 mb-2">抽取欄位</h4>
          <pre class="text-sm bg-gray-50 p-3 rounded overflow-auto">{{
            JSON.stringify(aiResult.extracted_data, null, 2)
          }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>
