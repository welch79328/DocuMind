<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const goToOcrTest = () => {
  router.push('/ocr-test')
}
</script>

<template>
  <div class="text-center">
    <h2 class="text-3xl font-bold text-gray-900 mb-4">
      AI Document Intelligence
    </h2>
    <p class="text-lg text-gray-600 mb-8">
      AI 文件智能處理系統
    </p>

    <button
      @click="goToOcrTest"
      class="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
    >
      OCR 測試
    </button>
  </div>
</template>
