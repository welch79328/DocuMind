<script setup lang="ts">
/**
 * 欄位確認介面元件(ocr-vlm-consensus 任務 9.1,需求 4.4)
 *
 * 低信心欄位由使用者當場確認,而非等待後台複核——使用者即文件當事人,
 * 是最適合的確認者。高信心欄位直接可用,不打擾使用者。
 *
 * 本元件只負責呈現與收集決定;把修正寫回回饋學習是任務 9.2 的職責,
 * 因此這裡只 emit,不直接呼叫 API。
 */
import { computed, ref, watch } from 'vue'
import type {
  ConfirmationRow,
  ConsensusDetail,
  FieldDecision,
} from '@/types/confirmation'
import { flattenFields } from '@/types/confirmation'

const props = withDefaults(
  defineProps<{
    /** 後端 PageResult.structured_data */
    structuredData?: Record<string, unknown> | null
    /** 後端 PageResult.field_confidences */
    fieldConfidences?: Record<string, number>
    /** 後端 PageResult.consensus;共識模式關閉時為 undefined */
    consensus?: ConsensusDetail | null
    /** 低信心門檻,與後端 OCR_QUALITY_THRESHOLD 一致 */
    threshold?: number
  }>(),
  {
    structuredData: null,
    fieldConfidences: () => ({}),
    consensus: null,
    threshold: 0.8,
  }
)

const emit = defineEmits<{
  (e: 'decide', decision: FieldDecision): void
  (e: 'change', decisions: FieldDecision[]): void
}>()

const rows = ref<ConfirmationRow[]>([])

function toDisplay(value: unknown): string {
  if (value === null || value === undefined) return ''
  return String(value)
}

function buildRows(): ConfirmationRow[] {
  const fields = flattenFields(props.structuredData)
  const confidences = props.fieldConfidences || {}
  const agreements = props.consensus?.agreements || {}
  // 共識不可用(單一候選)時,不得宣稱任何欄位「不一致」
  const consensusUsable = props.consensus?.available === true

  const names = new Set<string>([
    ...Object.keys(fields),
    ...Object.keys(confidences),
    ...Object.keys(agreements),
  ])

  return [...names].sort().map((field) => {
    const agreement = agreements[field]
    // 欄位值以共識明細為準;沒有共識時退回攤平後的抽取結果
    const raw = agreement ? agreement.value : fields[field]
    const value = toDisplay(raw)
    const confidence =
      typeof confidences[field] === 'number'
        ? confidences[field]
        : agreement
          ? agreement.confidence
          : null

    return {
      field,
      value,
      original: value,
      confidence,
      low: confidence !== null && confidence < props.threshold,
      disagreed: consensusUsable && agreement ? agreement.agreed === false : false,
      engineValues: agreement?.engine_values || {},
      action: null,
      expanded: false,
    }
  })
}

watch(
  () => [props.structuredData, props.fieldConfidences, props.consensus],
  () => {
    rows.value = buildRows()
  },
  { immediate: true, deep: true }
)

/** 需使用者處理的欄位:低信心或多引擎判讀不一致 */
const needsAttention = computed(() => rows.value.filter((r) => r.low || r.disagreed))
/** 高信心且一致的欄位:直接可用,不需操作 */
const settled = computed(() => rows.value.filter((r) => !r.low && !r.disagreed))

const pendingCount = computed(
  () => needsAttention.value.filter((r) => r.action === null).length
)

/** 目前已做出的所有決定,供父層(任務 9.2)回灌 */
const decisions = computed<FieldDecision[]>(() =>
  rows.value
    .filter((r) => r.action !== null)
    .map((r) => ({
      field: r.field,
      action: r.action as FieldDecision['action'],
      before: r.original,
      after: r.value,
    }))
)

function settle(row: ConfirmationRow) {
  // 值被改過就算修正,沒改就算確認——由實際內容決定,不由按了哪顆鈕決定
  row.action = row.value === row.original ? 'confirmed' : 'corrected'
  emit('decide', {
    field: row.field,
    action: row.action,
    before: row.original,
    after: row.value,
  })
  emit('change', decisions.value)
}

function reopen(row: ConfirmationRow) {
  row.action = null
  emit('change', decisions.value)
}

function toggleEngines(row: ConfirmationRow) {
  row.expanded = !row.expanded
}

function percent(confidence: number | null): string {
  return confidence === null ? '—' : `${Math.round(confidence * 100)}%`
}

defineExpose({ rows, decisions })
</script>

<template>
  <div class="field-confirmation">
    <!-- 需要使用者處理的欄位 -->
    <section v-if="needsAttention.length > 0">
      <div class="flex items-center justify-between mb-2">
        <h3 class="text-sm font-semibold text-gray-700">
          請確認以下欄位
          <span class="text-xs font-normal text-gray-500 ml-1">
            (辨識信心較低或多引擎判讀不一致)
          </span>
        </h3>
        <span class="text-xs text-amber-700">尚待確認 {{ pendingCount }} 項</span>
      </div>

      <ul class="space-y-2">
        <li
          v-for="row in needsAttention"
          :key="row.field"
          :class="[
            'border rounded-lg p-3',
            row.action !== null
              ? 'border-emerald-200 bg-emerald-50'
              : 'border-amber-300 bg-amber-50',
          ]"
          data-testid="attention-row"
        >
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-sm font-medium text-gray-800 w-40 shrink-0">
              {{ row.field }}
            </span>

            <input
              v-model="row.value"
              :disabled="row.action !== null"
              class="border rounded px-2 py-1 text-sm flex-1 min-w-[12rem] disabled:bg-gray-50 disabled:text-gray-500"
              :aria-label="`${row.field} 欄位值`"
            />

            <span class="text-xs text-gray-500 w-12 text-right">
              {{ percent(row.confidence) }}
            </span>

            <span
              v-if="row.disagreed"
              class="text-xs px-2 py-0.5 rounded bg-orange-100 text-orange-800"
              data-testid="disagree-badge"
            >
              引擎判讀不一致
            </span>
            <span
              v-else-if="row.low"
              class="text-xs px-2 py-0.5 rounded bg-amber-100 text-amber-800"
              data-testid="low-badge"
            >
              信心度偏低
            </span>

            <button
              v-if="row.disagreed"
              type="button"
              class="text-xs text-blue-600 hover:text-blue-800 underline"
              data-testid="toggle-engines"
              @click="toggleEngines(row)"
            >
              {{ row.expanded ? '收合各引擎判讀' : '檢視各引擎判讀' }}
            </button>

            <button
              v-if="row.action === null"
              type="button"
              class="text-sm bg-emerald-600 hover:bg-emerald-700 text-white rounded px-3 py-1"
              data-testid="settle-button"
              @click="settle(row)"
            >
              確認
            </button>
            <button
              v-else
              type="button"
              class="text-xs text-gray-500 hover:text-gray-800 underline"
              data-testid="reopen-button"
              @click="reopen(row)"
            >
              重新編輯（{{ row.action === 'corrected' ? '已修正' : '已確認' }}）
            </button>
          </div>

          <!-- 各引擎原始判讀對照 -->
          <table
            v-if="row.expanded"
            class="mt-2 ml-40 text-xs border-collapse"
            data-testid="engine-table"
          >
            <thead>
              <tr class="text-left text-gray-500 border-b">
                <th class="py-1 pr-6">引擎</th>
                <th class="py-1">判讀結果</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(engineValue, engine) in row.engineValues"
                :key="engine"
                class="border-b last:border-0"
              >
                <td class="py-1 pr-6 text-gray-600">{{ engine }}</td>
                <td class="py-1 font-mono">
                  {{ engineValue === null || engineValue === undefined ? '（未取得）' : engineValue }}
                </td>
              </tr>
            </tbody>
          </table>
        </li>
      </ul>
    </section>

    <!-- 高信心欄位:直接可用,不需操作 -->
    <section v-if="settled.length > 0" class="mt-4">
      <h3 class="text-sm font-semibold text-gray-700 mb-2">
        以下欄位辨識信心良好，無須確認
      </h3>
      <dl class="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-sm">
        <div
          v-for="row in settled"
          :key="row.field"
          class="flex justify-between border-b border-gray-100 py-1"
          data-testid="settled-row"
        >
          <dt class="text-gray-600">{{ row.field }}</dt>
          <dd class="text-gray-900 font-medium">
            {{ row.value || '（未提取）' }}
            <span class="text-xs text-gray-400 ml-1">{{ percent(row.confidence) }}</span>
          </dd>
        </div>
      </dl>
    </section>

    <p v-if="rows.length === 0" class="text-sm text-gray-500">
      本頁未取得結構化欄位。
    </p>
  </div>
</template>
