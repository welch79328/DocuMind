# AI Document Intelligence Demo - 前端設計文檔

## 1. 前端技術棧

### 1.1 核心框架

| 技術 | 版本 | 用途 |
|------|------|------|
| Vue | 3.4+ | UI 框架 |
| Vite | 5+ | 建構工具 |
| TypeScript | 5+ | 型別安全 |
| Tailwind CSS | 3+ | CSS 框架 |
| Vue Router | 4+ | 路由管理 |
| Pinia | 2+ | 狀態管理 |

### 1.2 工具庫

| 工具 | 用途 |
|------|------|
| `@tanstack/vue-query` | 資料快取與伺服器狀態管理 |
| `axios` | API 請求 |
| `@vueuse/core` | Vue 組合式函數工具庫 |
| `lucide-vue-next` | Icon 圖示 |
| `marked` | Markdown 渲染（摘要顯示） |
| `date-fns` | 日期格式化 |

---

## 2. 頁面架構

### 2.1 路由結構（Vue Router）

```
/                        # 首頁 - 文件列表
/upload                  # 上傳頁面
/document/:id            # 文件詳情頁（結果頁）
/record/:id              # 建立的記錄詳情頁（P2）
```

**路由配置：**
```typescript
// src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import UploadView from '@/views/UploadView.vue'
import DocumentView from '@/views/DocumentView.vue'
import RecordView from '@/views/RecordView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/upload', name: 'upload', component: UploadView },
    { path: '/document/:id', name: 'document', component: DocumentView },
    { path: '/record/:id', name: 'record', component: RecordView }
  ]
})

export default router
```

### 2.2 元件結構（Vue 3）

```
src/
├── main.ts                        # 應用入口
├── App.vue                        # 根元件
├── router/
│   └── index.ts                   # 路由配置
│
├── views/                         # 頁面元件
│   ├── HomeView.vue               # 首頁（文件列表）
│   ├── UploadView.vue             # 上傳頁面
│   ├── DocumentView.vue           # 文件詳情頁
│   └── RecordView.vue             # 記錄詳情頁
│
├── components/
│   ├── common/                    # 通用 UI 元件
│   │   ├── Button.vue
│   │   ├── Card.vue
│   │   ├── Input.vue
│   │   ├── Badge.vue
│   │   ├── Modal.vue
│   │   └── ...
│   │
│   ├── upload/
│   │   ├── FileUploader.vue       # 檔案上傳元件
│   │   └── UploadProgress.vue     # 上傳進度條
│   │
│   ├── document/
│   │   ├── DocumentCard.vue       # 文件卡片
│   │   ├── DocumentTypeBadge.vue  # 文件類型標籤
│   │   ├── StatusBadge.vue        # 狀態標籤
│   │   ├── ProcessingLoader.vue   # 處理中動畫
│   │   └── DocumentList.vue       # 文件列表
│   │
│   ├── result/
│   │   ├── ExtractedFields.vue    # 抽取欄位表單
│   │   ├── AISummary.vue          # AI 摘要卡片
│   │   ├── RiskAlerts.vue         # 風險提醒
│   │   └── ConfidenceScore.vue    # 信心度顯示
│   │
│   ├── chat/
│   │   ├── ChatInterface.vue      # 問答介面
│   │   ├── MessageBubble.vue      # 訊息氣泡
│   │   └── SuggestedQuestions.vue # 建議問題
│   │
│   └── layout/
│       ├── AppHeader.vue          # 頁首
│       ├── AppSidebar.vue         # 側邊欄（可選）
│       └── AppFooter.vue          # 頁尾
│
├── services/
│   └── api.ts                     # API 呼叫函式
│
├── composables/                   # 組合式函數
│   ├── useDocument.ts             # 文件相關邏輯
│   ├── useUpload.ts               # 上傳相關邏輯
│   └── useChat.ts                 # 問答相關邏輯
│
├── stores/                        # Pinia 狀態管理
│   └── document.ts                # 文件狀態
│
├── types/
│   └── index.ts                   # TypeScript 型別定義
│
└── assets/
    └── main.css                   # 全域樣式
```

---

## 3. 頁面設計

### 3.1 首頁 - 文件列表（/）

**功能：**
- 顯示所有已上傳文件
- 快速查看狀態
- 跳轉至上傳頁面
- 過濾/搜尋文件

**UI 元件：**

```vue
<!-- src/views/HomeView.vue -->
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { getDocuments } from '@/services/api'
import DocumentList from '@/components/document/DocumentList.vue'

const router = useRouter()
const statusFilter = ref('all')
const typeFilter = ref('all')

// 使用 Vue Query 獲取文件列表
const { data: documents, isLoading } = useQuery({
  queryKey: ['documents', statusFilter, typeFilter],
  queryFn: () => getDocuments({
    status: statusFilter.value,
    docType: typeFilter.value
  })
})

const goToUpload = () => {
  router.push('/upload')
}
</script>

<template>
  <div class="container mx-auto py-8">
    <!-- Header -->
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-3xl font-bold">AI 文件智能處理</h1>
      <button
        class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        @click="goToUpload"
      >
        上傳文件
      </button>
    </div>

    <!-- Filter -->
    <div class="flex gap-4 mb-6">
      <select
        v-model="statusFilter"
        class="px-3 py-2 border rounded"
      >
        <option value="all">全部</option>
        <option value="completed">已完成</option>
        <option value="processing">處理中</option>
        <option value="failed">失敗</option>
      </select>

      <select
        v-model="typeFilter"
        class="px-3 py-2 border rounded"
      >
        <option value="all">全部</option>
        <option value="lease_contract">租賃合約</option>
        <option value="repair_quote">報價單</option>
        <option value="id_card">身分證</option>
      </select>
    </div>

    <!-- Document List -->
    <DocumentList
      :documents="documents"
      :loading="isLoading"
    />
  </div>
</template>
```

**DocumentCard 元件：**

```vue
<!-- src/components/document/DocumentCard.vue -->
<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { format } from 'date-fns'
import StatusBadge from './StatusBadge.vue'
import DocumentTypeBadge from './DocumentTypeBadge.vue'

interface Props {
  document: {
    id: string
    file_name: string
    status: string
    doc_type?: string
    created_at: string
  }
}

const props = defineProps<Props>()
const router = useRouter()

const formattedDate = computed(() =>
  format(new Date(props.document.created_at), 'yyyy-MM-dd HH:mm')
)

const viewDetails = () => {
  router.push(`/document/${props.document.id}`)
}
</script>

<template>
  <div class="border rounded-lg p-4 hover:shadow-lg transition-shadow">
    <div class="flex justify-between items-start mb-3">
      <div>
        <h3 class="text-lg font-semibold">{{ document.file_name }}</h3>
        <p class="text-sm text-gray-500">
          上傳時間：{{ formattedDate }}
        </p>
      </div>
      <StatusBadge :status="document.status" />
    </div>

    <div class="mb-4">
      <DocumentTypeBadge
        v-if="document.doc_type"
        :type="document.doc_type"
      />
    </div>

    <button
      class="w-full px-4 py-2 border rounded hover:bg-gray-50"
      @click="viewDetails"
    >
      查看詳情
    </button>
  </div>
</template>
```

---

### 3.2 上傳頁面（/upload）

**功能：**
- 拖拽上傳
- 點擊選擇檔案
- 檔案驗證提示
- 上傳進度顯示
- 上傳完成後自動跳轉

**UI 設計：**

```tsx
// app/upload/page.tsx
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { FileUploader } from '@/components/upload/FileUploader';
import { uploadDocument, processDocument } from '@/lib/api';

export default function UploadPage() {
  const router = useRouter();
  const [uploading, setUploading] = useState(false);

  const handleUpload = async (file: File) => {
    setUploading(true);

    try {
      // 1. 上傳檔案
      const { data } = await uploadDocument(file);
      const documentId = data.id;

      // 2. 觸發處理
      await processDocument(documentId);

      // 3. 跳轉至詳情頁
      router.push(`/documents/${documentId}`);
    } catch (error) {
      console.error('Upload failed:', error);
      // 顯示錯誤訊息
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="container mx-auto py-12">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold mb-2">上傳文件</h1>
        <p className="text-muted-foreground mb-8">
          支援 PDF、JPG、PNG 格式，最大 10MB
        </p>

        <FileUploader onUpload={handleUpload} uploading={uploading} />

        {/* 說明區 */}
        <div className="mt-8 p-6 bg-muted rounded-lg">
          <h3 className="font-semibold mb-3">支援的文件類型：</h3>
          <ul className="space-y-2 text-sm">
            <li>📄 租賃合約 - 自動抽取租金、租期、承租人等資訊</li>
            <li>💰 修繕報價單 - 自動抽取廠商、金額、項目等資訊</li>
            <li>🪪 身分證 - 自動抽取姓名、證號、生日等資訊</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
```

**FileUploader 元件：**

```tsx
// components/upload/FileUploader.tsx
'use client';

import { useDropzone } from 'react-dropzone';
import { Upload, FileCheck, AlertCircle } from 'lucide-react';

interface FileUploaderProps {
  onUpload: (file: File) => void;
  uploading: boolean;
}

export function FileUploader({ onUpload, uploading }: FileUploaderProps) {
  const { getRootProps, getInputProps, isDragActive, fileRejections } =
    useDropzone({
      accept: {
        'application/pdf': ['.pdf'],
        'image/jpeg': ['.jpg', '.jpeg'],
        'image/png': ['.png'],
      },
      maxSize: 10 * 1024 * 1024, // 10MB
      multiple: false,
      onDrop: (acceptedFiles) => {
        if (acceptedFiles.length > 0) {
          onUpload(acceptedFiles[0]);
        }
      },
    });

  return (
    <div>
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-lg p-12 text-center
          transition-colors cursor-pointer
          ${isDragActive ? 'border-primary bg-primary/5' : 'border-muted-foreground/25'}
          ${uploading ? 'opacity-50 pointer-events-none' : 'hover:border-primary'}
        `}
      >
        <input {...getInputProps()} />

        <div className="flex flex-col items-center gap-4">
          {uploading ? (
            <>
              <FileCheck className="w-12 h-12 text-primary animate-pulse" />
              <p className="text-lg font-medium">上傳中...</p>
            </>
          ) : (
            <>
              <Upload className="w-12 h-12 text-muted-foreground" />
              <div>
                <p className="text-lg font-medium mb-1">
                  拖曳檔案至此，或點擊選擇檔案
                </p>
                <p className="text-sm text-muted-foreground">
                  支援 PDF、JPG、PNG（最大 10MB）
                </p>
              </div>
            </>
          )}
        </div>
      </div>

      {/* 錯誤提示 */}
      {fileRejections.length > 0 && (
        <div className="mt-4 p-4 bg-destructive/10 text-destructive rounded-lg flex items-start gap-3">
          <AlertCircle className="w-5 h-5 mt-0.5 flex-shrink-0" />
          <div>
            <p className="font-medium mb-1">檔案無效</p>
            {fileRejections[0].errors.map((error) => (
              <p key={error.code} className="text-sm">
                {error.message}
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

---

### 3.3 文件詳情頁（/documents/[id]）

**功能：**
- 顯示處理狀態
- 顯示文件類型與信心度
- 顯示 AI 摘要
- 顯示抽取欄位（可編輯）
- 顯示風險提醒（P2）
- 問答入口
- 建立記錄按鈕（P2）

**UI 設計：**

```tsx
// app/documents/[id]/page.tsx
'use client';

import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { getDocument } from '@/lib/api';
import { ProcessingLoader } from '@/components/document/ProcessingLoader';
import { ExtractedFields } from '@/components/result/ExtractedFields';
import { AISummary } from '@/components/result/AISummary';
import { RiskAlerts } from '@/components/result/RiskAlerts';
import { ChatInterface } from '@/components/chat/ChatInterface';

export default function DocumentPage() {
  const params = useParams();
  const documentId = params.id as string;

  const { data, isLoading, error } = useQuery({
    queryKey: ['document', documentId],
    queryFn: () => getDocument(documentId),
    refetchInterval: (data) => {
      // 處理中時每 2 秒輪詢
      return data?.status === 'processing' ? 2000 : false;
    },
  });

  if (isLoading) {
    return <ProcessingLoader />;
  }

  if (error || !data) {
    return <div>載入失敗</div>;
  }

  const document = data.data;

  return (
    <div className="container mx-auto py-8">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">{document.fileName}</h1>
        <div className="flex gap-3 items-center">
          <StatusBadge status={document.status} />
          {document.aiResult && (
            <DocumentTypeBadge type={document.aiResult.docType} />
          )}
          {document.aiResult && (
            <ConfidenceScore score={document.aiResult.confidence} />
          )}
        </div>
      </div>

      {/* Processing State */}
      {document.status === 'processing' && (
        <div className="mb-8">
          <Card>
            <CardContent className="pt-6">
              <ProcessingLoader message="AI 正在分析文件，請稍候..." />
            </CardContent>
          </Card>
        </div>
      )}

      {/* Results */}
      {document.status === 'completed' && document.aiResult && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* AI Summary */}
            <AISummary summary={document.aiResult.summary} />

            {/* Extracted Fields */}
            <ExtractedFields
              docType={document.aiResult.docType}
              data={document.aiResult.extractedData}
              onSave={(updatedData) => {
                // 更新欄位
                console.log('Updated:', updatedData);
              }}
            />

            {/* Risk Alerts (P2) */}
            {document.aiResult.risks && (
              <RiskAlerts risks={document.aiResult.risks} />
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Chat Interface */}
            <ChatInterface documentId={documentId} />

            {/* Actions */}
            <Card>
              <CardHeader>
                <CardTitle>操作</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <Button className="w-full" variant="default">
                  建立系統記錄
                </Button>
                <Button className="w-full" variant="outline">
                  下載原始檔案
                </Button>
                <Button className="w-full" variant="outline">
                  重新處理
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* Failed State */}
      {document.status === 'failed' && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-destructive mt-0.5" />
              <div>
                <p className="font-medium text-destructive mb-1">處理失敗</p>
                <p className="text-sm text-muted-foreground">
                  {document.errorMessage}
                </p>
                <Button className="mt-4" variant="outline">
                  重新處理
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

**ExtractedFields 元件：**

```tsx
// components/result/ExtractedFields.tsx
interface ExtractedFieldsProps {
  docType: string;
  data: Record<string, any>;
  onSave: (data: Record<string, any>) => void;
}

export function ExtractedFields({ docType, data, onSave }: ExtractedFieldsProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState(data);

  const fieldLabels = {
    lease_contract: {
      landlord_name: '出租人姓名',
      tenant_name: '承租人姓名',
      address: '租賃地址',
      rent: '月租金',
      deposit: '押金',
      lease_start: '租期開始',
      lease_end: '租期結束',
      contract_date: '合約日期',
    },
    repair_quote: {
      vendor_name: '廠商名稱',
      quote_date: '報價日期',
      amount: '報價金額',
      item_summary: '項目摘要',
    },
    id_card: {
      name: '姓名',
      national_id: '身分證字號',
      birth_date: '出生日期',
    },
  };

  const labels = fieldLabels[docType as keyof typeof fieldLabels] || {};

  return (
    <Card>
      <CardHeader>
        <div className="flex justify-between items-center">
          <CardTitle>抽取欄位</CardTitle>
          <Button
            variant={isEditing ? 'default' : 'outline'}
            size="sm"
            onClick={() => {
              if (isEditing) {
                onSave(formData);
              }
              setIsEditing(!isEditing);
            }}
          >
            {isEditing ? '儲存' : '編輯'}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Object.entries(data).map(([key, value]) => (
            <div key={key}>
              <label className="text-sm font-medium text-muted-foreground block mb-1">
                {labels[key as keyof typeof labels] || key}
              </label>
              {isEditing ? (
                <Input
                  value={formData[key] || ''}
                  onChange={(e) =>
                    setFormData({ ...formData, [key]: e.target.value })
                  }
                />
              ) : (
                <p className="text-base font-medium">{value || '-'}</p>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
```

**AISummary 元件：**

```tsx
// components/result/AISummary.tsx
interface AISummaryProps {
  summary: string;
}

export function AISummary({ summary }: AISummaryProps) {
  return (
    <Card className="bg-primary/5 border-primary/20">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-primary" />
          AI 摘要
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-base leading-relaxed">{summary}</p>
      </CardContent>
    </Card>
  );
}
```

---

### 3.4 問答介面（ChatInterface 元件）

**UI 設計：**

```tsx
// components/chat/ChatInterface.tsx
'use client';

import { useState } from 'react';
import { chatWithDocument } from '@/lib/api';
import { Send } from 'lucide-react';

interface ChatInterfaceProps {
  documentId: string;
}

export function ChatInterface({ documentId }: ChatInterfaceProps) {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<
    Array<{ role: 'user' | 'assistant'; content: string }>
  >([]);
  const [loading, setLoading] = useState(false);

  const suggestedQuestions = [
    '這份文件的重點是什麼？',
    '租金是多少？',
    '租期到什麼時候？',
  ];

  const handleSubmit = async (q?: string) => {
    const questionToAsk = q || question;
    if (!questionToAsk.trim()) return;

    setMessages((prev) => [...prev, { role: 'user', content: questionToAsk }]);
    setQuestion('');
    setLoading(true);

    try {
      const { data } = await chatWithDocument(documentId, questionToAsk);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: data.answer },
      ]);
    } catch (error) {
      console.error('Chat failed:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MessageSquare className="w-5 h-5" />
          AI 問答
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Messages */}
        <div className="space-y-3 max-h-80 overflow-y-auto">
          {messages.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              針對此文件提問，AI 會幫您解答
            </p>
          ) : (
            messages.map((msg, idx) => (
              <div
                key={idx}
                className={`p-3 rounded-lg ${
                  msg.role === 'user'
                    ? 'bg-primary text-primary-foreground ml-8'
                    : 'bg-muted mr-8'
                }`}
              >
                <p className="text-sm">{msg.content}</p>
              </div>
            ))
          )}
          {loading && (
            <div className="bg-muted p-3 rounded-lg mr-8">
              <p className="text-sm text-muted-foreground animate-pulse">
                AI 思考中...
              </p>
            </div>
          )}
        </div>

        {/* Suggested Questions */}
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">建議問題：</p>
            <div className="flex flex-wrap gap-2">
              {suggestedQuestions.map((q) => (
                <button
                  key={q}
                  onClick={() => handleSubmit(q)}
                  className="text-xs px-3 py-1 bg-muted hover:bg-muted/80 rounded-full transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input */}
        <div className="flex gap-2">
          <Input
            placeholder="輸入問題..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
          />
          <Button size="icon" onClick={() => handleSubmit()} disabled={loading}>
            <Send className="w-4 h-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
```

---

## 4. 通用元件

### 4.1 StatusBadge（狀態標籤）

```tsx
// components/document/StatusBadge.tsx
interface StatusBadgeProps {
  status: string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const statusConfig = {
    uploaded: { label: '待處理', variant: 'secondary' },
    processing: { label: '處理中', variant: 'default' },
    completed: { label: '已完成', variant: 'success' },
    failed: { label: '失敗', variant: 'destructive' },
  };

  const config = statusConfig[status as keyof typeof statusConfig];

  return (
    <Badge variant={config?.variant || 'secondary'}>{config?.label || status}</Badge>
  );
}
```

### 4.2 DocumentTypeB adge（文件類型標籤）

```tsx
// components/document/DocumentTypeBadge.tsx
interface DocumentTypeBadgeProps {
  type: string;
}

export function DocumentTypeBadge({ type }: DocumentTypeBadgeProps) {
  const typeConfig = {
    lease_contract: { label: '租賃合約', icon: '📄' },
    repair_quote: { label: '報價單', icon: '💰' },
    id_card: { label: '身分證', icon: '🪪' },
    unknown: { label: '未知', icon: '❓' },
  };

  const config = typeConfig[type as keyof typeof typeConfig];

  return (
    <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-muted rounded-full text-sm">
      <span>{config?.icon}</span>
      <span>{config?.label || type}</span>
    </div>
  );
}
```

---

## 5. API 整合

### 5.1 API Client

```typescript
// lib/api.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const uploadDocument = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);

  return apiClient.post('/documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};

export const processDocument = (documentId: string) => {
  return apiClient.post(`/documents/${documentId}/process`);
};

export const getDocument = (documentId: string) => {
  return apiClient.get(`/documents/${documentId}`);
};

export const getDocuments = (params?: {
  page?: number;
  limit?: number;
  status?: string;
  docType?: string;
}) => {
  return apiClient.get('/documents', { params });
};

export const chatWithDocument = (documentId: string, question: string) => {
  return apiClient.post(`/documents/${documentId}/chat`, { question });
};

export const createRecord = (documentId: string, confirmedData?: any) => {
  return apiClient.post(`/documents/${documentId}/create-record`, {
    confirmedData,
  });
};
```

---

## 6. 型別定義

```typescript
// types/index.ts
export interface Document {
  id: string;
  fileName: string;
  fileUrl: string;
  mimeType: string;
  fileSize: number;
  status: 'uploaded' | 'processing' | 'completed' | 'failed';
  errorMessage?: string;
  createdAt: string;
  updatedAt: string;
  ocrResult?: OcrResult;
  aiResult?: AiResult;
}

export interface OcrResult {
  rawText: string;
  pageCount: number;
  ocrConfidence: number;
  ocrService: string;
}

export interface AiResult {
  docType: 'lease_contract' | 'repair_quote' | 'id_card' | 'unknown';
  confidence: number;
  summary: string;
  extractedData: Record<string, any>;
  risks?: Risk[];
  aiModel: string;
  processingTime: number;
}

export interface Risk {
  type: string;
  field?: string;
  severity: 'info' | 'warning' | 'error';
  message: string;
}

export interface CreatedRecord {
  id: string;
  sourceDocumentId: string;
  recordType: 'lease' | 'repair_quote' | 'tenant';
  payload: Record<string, any>;
  createdAt: string;
}
```

---

## 7. 樣式設計

### 7.1 顏色系統（Tailwind 配置）

```js
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#3b82f6', // Blue 500
          foreground: '#ffffff',
        },
        success: {
          DEFAULT: '#10b981', // Green 500
          foreground: '#ffffff',
        },
        warning: {
          DEFAULT: '#f59e0b', // Amber 500
          foreground: '#ffffff',
        },
        destructive: {
          DEFAULT: '#ef4444', // Red 500
          foreground: '#ffffff',
        },
      },
    },
  },
};
```

### 7.2 響應式設計

- **桌面（lg+）**: 3 欄布局
- **平板（md）**: 2 欄布局
- **手機（< md）**: 單欄布局

---

## 8. 開發檢查清單

### 8.1 基礎功能（P0）

- [ ] 上傳頁面
- [ ] 文件列表頁
- [ ] 文件詳情頁
- [ ] 狀態輪詢機制
- [ ] 錯誤處理 UI

### 8.2 AI 功能（P1）

- [ ] AI 摘要顯示
- [ ] 問答介面
- [ ] 建議問題

### 8.3 進階功能（P2）

- [ ] 風險提醒顯示
- [ ] 欄位編輯功能
- [ ] 建立記錄功能
- [ ] 記錄詳情頁

---

**文檔版本**: v1.0
**最後更新**: 2026-03-17
**負責人**: Frontend Team
