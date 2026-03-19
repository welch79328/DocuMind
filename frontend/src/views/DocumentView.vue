<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const documentId = route.params.id as string

const document = ref<any>(null)
const aiResult = ref<any>(null)
const loading = ref(true)

const fetchDocument = async () => {
  try {
    const response = await fetch(`/api/v1/documents/${documentId}`)
    document.value = await response.json()

    // Fetch AI result
    const aiResponse = await fetch(`/api/v1/documents/${documentId}/ai-result`)
    if (aiResponse.ok) {
      aiResult.value = await aiResponse.json()
    }
  } catch (error) {
    console.error('Fetch error:', error)
  } finally {
    loading.value = false
  }
}

const processDocument = async () => {
  try {
    await fetch(`/api/v1/documents/${documentId}/process`, {
      method: 'POST'
    })

    // Polling for result
    const pollInterval = setInterval(async () => {
      await fetchDocument()
      if (document.value?.status === 'completed') {
        clearInterval(pollInterval)
      }
    }, 2000)
  } catch (error) {
    console.error('Process error:', error)
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
      <div class="bg-white rounded-lg shadow p-6 mb-6">
        <h3 class="text-lg font-semibold mb-4">基本資訊</h3>
        <dl class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <dt class="text-sm font-medium text-gray-500">檔案名稱</dt>
            <dd class="mt-1 text-sm text-gray-900">{{ document.file_name }}</dd>
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
                {{ document.status }}
              </span>
            </dd>
          </div>
        </dl>

        <button
          v-if="document.status === 'uploaded'"
          @click="processDocument"
          class="mt-4 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700"
        >
          開始處理
        </button>
      </div>

      <!-- AI Result -->
      <div v-if="aiResult" class="bg-white rounded-lg shadow p-6">
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
