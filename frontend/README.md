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

Access: http://localhost:3000

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
├── public/              # Static assets
├── src/
│   ├── assets/          # CSS, images
│   ├── components/      # Vue components
│   ├── views/           # Page components
│   ├── router/          # Vue Router config
│   ├── stores/          # Pinia stores
│   ├── services/        # API services
│   ├── types/           # TypeScript types
│   ├── App.vue          # Root component
│   └── main.ts          # Entry point
├── index.html
├── vite.config.ts
├── tailwind.config.js
└── package.json
```

## 🔧 Configuration

### Environment Variables

Create `.env.local`:

```bash
VITE_API_URL=http://localhost:8000
VITE_APP_TITLE=AI Document Intelligence
```

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

### Run Container

```bash
docker run -p 80:80 ai-doc-frontend
```

## 📝 Pages

- **Home** (`/`) - Landing page
- **Upload** (`/upload`) - Document upload
- **Document** (`/document/:id`) - Document details & AI results

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
