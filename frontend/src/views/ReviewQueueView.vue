<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { reviewApi } from '@/services/api'
import type { ReviewItem, ReviewStatus } from '@/types/review'

const router = useRouter()

// 複核者身分(無認證,以名稱識別,記憶於 localStorage)
const reviewer = ref<string>(localStorage.getItem('reviewer_name') || '')
const statusFilter = ref<ReviewStatus | ''>('')
const items = ref<ReviewItem[]>([])
const loading = ref(false)
const message = ref<{ type: 'error' | 'success'; text: string } | null>(null)

const docTypeLabels: Record<string, string> = {
  transcript: '建物土地謄本',
  bill: '帳單',
  contract: '合約',
  repair_photo: '修繕照片',
}

const statusLabels: Record<ReviewStatus, string> = {
  pending: '待複核',
  in_review: '複核中',
  completed: '已完成',
}

function saveReviewer() {
  localStorage.setItem('reviewer_name', reviewer.value)
}

function showMessage(type: 'error' | 'success', text: string) {
  message.value = { type, text }
  setTimeout(() => (message.value = null), 4000)
}

function confidencePercent(item: ReviewItem): string {
  if (item.overall_confidence === null) return '—'
  return `${Math.round(item.overall_confidence * 100)}%`
}

const hasReviewer = computed(() => reviewer.value.trim().length > 0)

async function loadQueue() {
  loading.value = true
  try {
    const resp = await reviewApi.getQueue(statusFilter.value || undefined)
    items.value = resp.data.items
  } catch {
    showMessage('error', '載入複核佇列失敗，請稍後再試')
  } finally {
    loading.value = false
  }
}

async function claim(item: ReviewItem) {
  if (!hasReviewer.value) {
    showMessage('error', '請先輸入複核者名稱')
    return
  }
  try {
    await reviewApi.claim(item.id, reviewer.value.trim())
    showMessage('success', '認領成功')
    await loadQueue()
  } catch (err: unknown) {
    // 409 衝突:已被他人認領
    const status = (err as { response?: { status?: number } })?.response?.status
    if (status === 409) {
      showMessage('error', '此項目已被他人認領，佇列已更新')
      await loadQueue()
    } else {
      showMessage('error', '認領失敗，請稍後再試')
    }
  }
}

async function release(item: ReviewItem) {
  try {
    await reviewApi.release(item.id, reviewer.value.trim())
    showMessage('success', '已釋出')
    await loadQueue()
  } catch {
    showMessage('error', '釋出失敗（僅認領者可釋出）')
  }
}

function correct(item: ReviewItem) {
  router.push({ name: 'review-correct', params: { id: item.id } })
}

function isOwner(item: ReviewItem): boolean {
  return item.reviewer !== null && item.reviewer === reviewer.value.trim()
}

onMounted(loadQueue)
</script>

<template>
  <div class="max-w-5xl mx-auto p-6">
    <h1 class="text-2xl font-bold text-gray-800 mb-4">📝 人工複核佇列</h1>

    <!-- 複核者與過濾 -->
    <div class="flex flex-wrap items-end gap-4 mb-4">
      <div>
        <label class="block text-sm text-gray-600 mb-1">複核者名稱</label>
        <input
          v-model="reviewer"
          @blur="saveReviewer"
          type="text"
          placeholder="輸入你的名稱"
          class="border rounded px-3 py-2 w-48"
        />
      </div>
      <div>
        <label class="block text-sm text-gray-600 mb-1">狀態過濾</label>
        <select
          v-model="statusFilter"
          @change="loadQueue"
          class="border rounded px-3 py-2 w-40"
        >
          <option value="">全部</option>
          <option value="pending">待複核</option>
          <option value="in_review">複核中</option>
          <option value="completed">已完成</option>
        </select>
      </div>
      <button
        @click="loadQueue"
        class="bg-gray-100 hover:bg-gray-200 border rounded px-4 py-2"
      >
        重新整理
      </button>
    </div>

    <!-- 訊息 -->
    <div
      v-if="message"
      :class="[
        'mb-4 px-4 py-2 rounded text-sm',
        message.type === 'error' ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700',
      ]"
    >
      {{ message.text }}
    </div>

    <!-- 列表 -->
    <div v-if="loading" class="text-gray-500 py-8 text-center">載入中…</div>
    <div v-else-if="items.length === 0" class="text-gray-500 py-8 text-center">
      目前佇列中沒有項目
    </div>
    <table v-else class="w-full border-collapse">
      <thead>
        <tr class="text-left text-sm text-gray-500 border-b">
          <th class="py-2">文件類型</th>
          <th class="py-2">整體信心度</th>
          <th class="py-2">狀態</th>
          <th class="py-2">認領者</th>
          <th class="py-2 text-right">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id" class="border-b hover:bg-gray-50">
          <td class="py-3">{{ docTypeLabels[item.document_type] || item.document_type }}</td>
          <td class="py-3">
            <span
              :class="[
                'px-2 py-0.5 rounded text-sm',
                (item.overall_confidence ?? 1) < 0.8
                  ? 'bg-amber-100 text-amber-700'
                  : 'bg-green-100 text-green-700',
              ]"
            >
              {{ confidencePercent(item) }}
            </span>
          </td>
          <td class="py-3">{{ statusLabels[item.status] }}</td>
          <td class="py-3 text-gray-600">{{ item.reviewer || '—' }}</td>
          <td class="py-3 text-right space-x-2">
            <button
              v-if="item.status === 'pending'"
              @click="claim(item)"
              class="bg-blue-600 hover:bg-blue-700 text-white text-sm rounded px-3 py-1"
            >
              認領
            </button>
            <template v-if="item.status === 'in_review' && isOwner(item)">
              <button
                @click="correct(item)"
                class="bg-emerald-600 hover:bg-emerald-700 text-white text-sm rounded px-3 py-1"
              >
                校正
              </button>
              <button
                @click="release(item)"
                class="bg-gray-100 hover:bg-gray-200 border text-sm rounded px-3 py-1"
              >
                釋出
              </button>
            </template>
            <span
              v-else-if="item.status === 'in_review'"
              class="text-xs text-gray-400"
            >
              複核中（他人）
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
