<script setup lang="ts">
import { RouterView, RouterLink } from 'vue-router'
</script>

<template>
  <div id="app" class="min-h-screen bg-gray-50">
    <header class="bg-white shadow-sm">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div class="flex items-center justify-between">
          <h1 class="text-2xl font-bold text-gray-900">
            🤖 AI Document Intelligence
          </h1>
          <nav class="flex space-x-4">
            <RouterLink
              to="/"
              class="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
            >
              首頁
            </RouterLink>
            <a
              href="/api/docs"
              target="_blank"
              class="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
            >
              API 文件
            </a>
            <RouterLink
              to="/ocr-test"
              class="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium bg-blue-50 text-blue-700 hover:bg-blue-100"
            >
              🔬 OCR 測試
            </RouterLink>
          </nav>
        </div>
      </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <RouterView />
    </main>

    <footer class="bg-white border-t border-gray-200 mt-auto">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <p class="text-center text-sm text-gray-500">
          AI Document Intelligence Demo - Vue 3 + FastAPI
        </p>
      </div>
    </footer>
  </div>
</template>

<style>
#app {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}
</style>
