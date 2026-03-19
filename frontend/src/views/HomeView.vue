<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const goToUpload = () => {
  router.push('/upload')
}
</script>

<template>
  <div class="text-center">
    <h2 class="text-3xl font-bold text-gray-900 mb-4">
      歡迎使用 AI 文件智能處理系統
    </h2>
    <p class="text-lg text-gray-600 mb-8">
      上傳您的文件，讓 AI 自動辨識、分類、抽取資訊
    </p>

    <button
      @click="goToUpload"
      class="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
    >
      🚀 開始上傳文件
    </button>

    <div class="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-3">
      <div class="bg-white p-6 rounded-lg shadow">
        <div class="text-3xl mb-2">📤</div>
        <h3 class="text-lg font-semibold mb-2">文件上傳</h3>
        <p class="text-gray-600">支援 PDF/JPG/PNG 格式</p>
      </div>

      <div class="bg-white p-6 rounded-lg shadow">
        <div class="text-3xl mb-2">🤖</div>
        <h3 class="text-lg font-semibold mb-2">AI 分類</h3>
        <p class="text-gray-600">自動識別文件類型</p>
      </div>

      <div class="bg-white p-6 rounded-lg shadow">
        <div class="text-3xl mb-2">📋</div>
        <h3 class="text-lg font-semibold mb-2">欄位抽取</h3>
        <p class="text-gray-600">AI 自動抽取關鍵資訊</p>
      </div>
    </div>
  </div>
</template>
