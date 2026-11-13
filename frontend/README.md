# AI Document Intelligence - Frontend (Vue 3)

Vue 3 + Vite + TypeScript frontend for AI-powered document processing.

## 🚀 Quick Start

### Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev
```

Access: http://localhost:3000 (Vite proxies `/api` to `http://localhost:8000`, see `vite.config.ts`)

### Build for Production

```bash
# Build
npm run build

# Preview build
npm run preview
```

## 📦 Tech Stack

- **Framework**: Vue 3
- **Build Tool**: Vite 5
- **Language**: TypeScript
- **Routing**: Vue Router 4
- **State**: Pinia
- **HTTP Client**: Axios
- **Data Fetching**: TanStack Query (Vue Query)
- **Styling**: Tailwind CSS 3
- **Utils**: VueUse

## 📂 Project Structure

```
frontend/
├── src/
│   ├── assets/          # CSS, images
│   ├── components/      # Vue components
│   ├── views/           # Page components
│   ├── composables/     # Composition functions
│   ├── router/          # Vue Router config
│   ├── services/        # API services (axios, baseURL `/api`)
│   ├── types/           # TypeScript types
│   ├── App.vue          # Root component
│   └── main.ts          # Entry point
├── index.html
├── vite.config.ts
├── tailwind.config.js
└── package.json
```

## 🔧 Configuration

### Vite Config

See `vite.config.ts` for:
- Path aliases (@)
- Proxy configuration
- Build settings

## 🐳 Docker

### Build Image

```bash
docker build -t ai-doc-frontend .
```

### Run

The image's nginx proxies `/api/` to `http://backend:8000`, so run it with the repo-root
`docker-compose.yml` (served through the `nginx` service on http://localhost:8085).

## 📝 Pages

- **Home** (`/`) - Landing page
- **Upload** (`/upload`) - Document upload
- **Document** (`/document/:id`) - Document details & AI results
- **OCR Test** (`/ocr-test`) - OCR result comparison and field confirmation (see `OCR_VALIDATION_UI_GUIDE.md`)
- **Review Queue** (`/review`) - Human review queue
- **Review Correct** (`/review/:id`) - Correct one review item

## 🧪 Tests

```bash
npm test   # vitest run (src/**/*.spec.ts)
```

## 🎨 Styling

Using Tailwind CSS utility-first approach.

Edit `tailwind.config.js` to customize theme.

## 📚 Learn More

- [Vue 3](https://vuejs.org/)
- [Vite](https://vitejs.dev/)
- [Vue Router](https://router.vuejs.org/)
- [Pinia](https://pinia.vuejs.org/)
- [Tailwind CSS](https://tailwindcss.com/)

## 📄 License

Internal use only.
