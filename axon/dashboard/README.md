# Axon Bridge Dashboard

This is the React-based Observability Dashboard for Axon Bridge. It visualizes real-time metrics, cache contents, and agentic token compression savings.

## Development Setup

The dashboard is built with [Vite](https://vitejs.dev/) and React.

1. **Install Dependencies**
   ```bash
   cd dashboard
   npm ci
   ```

2. **Start the Development Server**
   ```bash
   npm run dev
   ```
   *Note: Ensure the main Axon Bridge Python server is running concurrently so the dashboard can fetch live metrics via the API.*

3. **Build for Production**
   ```bash
   npm run build
   ```
   This will generate static assets in `dashboard/dist`. The Axon FastAPI application is configured to serve these assets directly when you visit `http://localhost:8080/dashboard`.

## UI Components

If you are developing new UI components, we use Storybook (optional) for component-driven development:
```bash
npm run storybook
```
