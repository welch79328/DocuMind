<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const file = ref<File | null>(null)
const uploading = ref(false)

const handleFileChange = (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files && target.files[0]) {
    file.value = target.files[0]
  }
}

const uploadFile = async () => {
  if (!file.value) return

  uploading.value = true

  try {
    const formData = new FormData()
    formData.append('file', file.value)

    const response = await fetch('/api/v1/documents/upload', {
      method: 'POST',
      body: formData
    })

    if (!response.ok) throw new Error('Upload failed')

    const data = await response.json()
    router.push(`/document/${data.id}`)
  } catch (error) {
    console.error('Upload error:', error)
    alert('上傳失敗，請稍後再試')
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto">
    <h2 class="text-2xl font-bold text-gray-900 mb-6">上傳文件</h2>

    <!-- 拍照建議提示框 -->
    <div class="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6 w-full">
      <div class="flex">
        <div class="flex-shrink-0">
          <svg class="h-5 w-5 text-amber-400" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
          </svg>
        </div>
        <div class="ml-3">
          <h3 class="text-sm font-medium text-amber-800">拍照建議（提高辨識準確度）</h3>
          <div class="mt-2 text-sm text-amber-700">
            <ul class="list-disc list-inside space-y-1">
              <li><strong>身分證請從塑膠套中取出</strong>（塑膠套反光會嚴重影響辨識）</li>
              <li>平放在桌面上，確保文件與相機平行</li>
              <li>光線充足，避免陰影和反光</li>
              <li>文字清晰可見，不要模糊或傾斜</li>
              <li>避免使用閃光燈（容易造成反光）</li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <div class="bg-white rounded-lg shadow p-6 w-full">
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 mb-2">
          選擇文件
        </label>
        <input
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          @change="handleFileChange"
          class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
        />
        <p class="mt-2 text-sm text-gray-500">
          支援格式：PDF, JPG, PNG（最大 10MB）
        </p>
      </div>

      <div v-if="file" class="mb-4 p-3 bg-gray-50 rounded">
        <p class="text-sm text-gray-700">
          <strong>選中的文件：</strong> {{ file.name }}
        </p>
        <p class="text-sm text-gray-500">
          大小：{{ (file.size / 1024 / 1024).toFixed(2) }} MB
        </p>
      </div>

      <button
        @click="uploadFile"
        :disabled="!file || uploading"
        class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <span v-if="uploading">上傳中...</span>
        <span v-else>開始上傳</span>
      </button>
    </div>
  </div>
</template>
