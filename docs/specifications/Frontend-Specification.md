# Frontend Specification

**Version**: 1.0.0 | **Status**: Approved | **Last Updated**: 2026-07-10

**Cross-References**:
- [API-Specification.md](API-Specification.md) — All backend endpoints consumed by frontend
- [AI-Agent-Specification.md](AI-Agent-Specification.md) — Query pipeline behavior exposed via UI
- [Security-Specification.md](Security-Specification.md) — Auth flows, CORS, CSRF
- [Observability-Specification.md](Observability-Specification.md) — RUM tracing, error reporting
- [Performance-Budgets.md](Performance-Budgets.md) — Frontend performance targets
- [Database-Specification.md](Database-Specification.md) — Caching store schemas
- [Deployment-Specification.md](Deployment-Specification.md) — CDN, SSR, static export configs

---

## Table of Contents

1. [Overview & Application Architecture](#1-overview--application-architecture)
2. [Tech Stack & Rationale](#2-tech-stack--rationale)
3. [Route Structure & Navigation](#3-route-structure--navigation)
4. [State Management](#4-state-management)
5. [Caching Strategy](#5-caching-strategy)
6. [Authentication & Session Management](#6-authentication--session-management)
7. [Design System](#7-design-system)
8. [Accessibility](#8-accessibility)
9. [Dark Mode](#9-dark-mode)
10. [Internationalization](#10-internationalization)
11. [Responsive Design](#11-responsive-design)
12. [Real-Time Updates](#12-real-time-updates)
13. [Component Hierarchy](#13-component-hierarchy)
14. [User Flows](#14-user-flows)
15. [Wireframes / Layout Specifications](#15-wireframes--layout-specifications)
16. [Permissions & RBAC (UI Enforcement)](#16-permissions--rbac-ui-enforcement)
17. [Error Handling](#17-error-handling)
18. [Loading States](#18-loading-states)
19. [Empty States](#19-empty-states)
20. [Future Extensibility](#20-future-extensibility)
21. [Implementation Guidelines](#21-implementation-guidelines)
22. [Testing Strategy](#22-testing-strategy)

---

## 1. Overview & Application Architecture

### 1.1 Application Type

Single-page application (SPA) with server-side rendering (SSR) via Next.js 15 App Router. Deployed as a containerized Node.js server behind CDN. Supports static export for air-gapped deployments.

### 1.2 Architecture Layers

```
+-------------------------------------------------------+
|                   Browser (Client)                     |
|  +-------------------------------------------------+  |
|  |           React 19 / Next.js 15 App              |  |
|  |  +---------+ +----------+ +-------------------+  |  |
|  |  |  Pages  | | Zustand  | | React Query       |  |  |
|  |  | (Server | | Stores   | | (Server State)    |  |  |
|  |  |  & RSC) | |          | |                   |  |  |
|  |  +---------+ +----------+ +--------+----------+  |  |
|  |  +-----------------------------------+--------+  |  |
|  |  |       API Client (fetch + WS)              |  |  |
|  |  +--------------------------------------------+  |  |
|  +-------------------------------------------------+  |
|                           |                            |
|                    CDN / Edge                           |
|                           |                            |
|  +-------------------------------------------------+  |
|  |           Backend API (Port 8100)               |  |
|  +-------------------------------------------------+  |
|                           |                            |
|  +-------------------------------------------------+  |
|  |         WebSocket Gateway (Port 8300)           |  |
|  +-------------------------------------------------+  |
+-------------------------------------------------------+
```

### 1.3 Rendering Strategy

| Route Pattern | Rendering | Rationale |
|---------------|-----------|-----------|
| /login | Static + Client hydration | No dynamic data |
| /dashboard/chat | Server-rendered shell + Client-side streaming | Chat state is user-specific, real-time |
| /dashboard/schema | SSR with data prefetch | Schema data is relatively static |
| /dashboard/history | SSR with paginated data | Initial load fast, client handles pagination |
| /dashboard/settings | Server-rendered shell + Client form | Form state is client-side |
| /dashboard/admin | SSR (admin-only) | Data-dense pages benefit from server rendering |

### 1.4 Deployment Targets

| Target | Build Mode | Notes |
|--------|-----------|-------|
| Cloud SaaS | next build (SSR) | Docker container, K8s deployment |
| Dedicated | next build (SSR) | Per-tenant container |
| Customer VPC | next build (SSR) | Same as SaaS, isolated infra |
| On-prem K8s | next build (SSR) | Customer-managed K8s |
| Air-gapped | next export (static) | No Node.js server needed; static files behind any HTTP server |

---

## 2. Tech Stack & Rationale

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| React | 19.x | UI framework | Server components, concurrent features, improved hydration |
| Next.js | 15.x | Meta-framework | App Router, SSR, RSC, middleware, image optimization |
| TypeScript | 5.x | Language | Type safety across frontend |
| Zustand | 5.x | Client state | Minimal boilerplate, no provider wrapper, middleware support |
| TanStack React Query | 5.x | Server state | Caching, dedup, refetch, pagination, optimistic updates |
| Tailwind CSS | 4.x | Styling | Utility-first, JIT compilation, small bundles |
| shadcn/ui | latest | Component primitives | Accessible, unstyled base, Tailwind integration |
| Framer Motion | 11.x | Animations | Declarative, layout animations, gesture support |
| React Hook Form | 7.x | Forms | Performant, minimal re-renders, Zod integration |
| Zod | 3.x | Validation | Schema validation shared with backend |
| openapi-typescript | latest | API client types | Generated types from OpenAPI spec |
| i18next | 24.x | Internationalization | Lazy loading, plural rules, React integration |
| Vitest + Testing Library | latest | Testing | Fast, Vite-native, component tests |
| Playwright | latest | E2E testing | Cross-browser, visual regression |
| MSW | 2.x | API mocking | Service worker-based, works in tests and dev |
| Lucide React | latest | Icons | Tree-shakeable, consistent style |
| sonner | latest | Toasts | Lightweight, accessible toast notifications |
| next-themes | latest | Theme switching | System/manual dark mode, no flash |

### 2.1 Rejected Alternatives

| Alternative | Rejected Because |
|-------------|-----------------|
| Redux Toolkit | Overkill for this app's state complexity; Zustand + React Query covers all needs |
| Vue/Svelte/Solid | Team expertise is React; Next.js SSR ecosystem is mature for this use case |
| Chakra UI / MUI | Bundle size; shadcn/ui is headless, composable, tree-shakeable |
| SWR | React Query has better devtools, mutation support, and pagination patterns |
| CSS Modules | Tailwind's design token system maps directly to our design system tokens |
| tRPC | Our API is REST-based; adding tRPC would require backend changes |

---

## 3. Route Structure & Navigation

### 3.1 Route Table

| Route | Page Component | Auth | Layout | Permissions |
|-------|---------------|------|--------|-------------|
| /login | LoginPage | Public | Minimal (no nav) | None |
| /logout | LogoutPage | Public | Minimal | None |
| /invite/[token] | AcceptInvitePage | Public (token) | Minimal | None |
| /dashboard | DashboardPage | Private | AppLayout | All authenticated |
| /dashboard/chat | ChatPage | Private | AppLayout | All authenticated |
| /dashboard/chat/[id] | ChatConversationPage | Private | AppLayout | All authenticated |
| /dashboard/schema | SchemaPage | Private | AppLayout | All authenticated |
| /dashboard/history | HistoryPage | Private | AppLayout | All authenticated |
| /dashboard/history/[id] | HistoryDetailPage | Private | AppLayout | All authenticated |
| /dashboard/settings | SettingsPage | Private | AppLayout | All authenticated |
| /dashboard/settings/profile | ProfileSettingsPage | Private | AppLayout | All authenticated |
| /dashboard/settings/team | TeamSettingsPage | Private | AppLayout | manage_team |
| /dashboard/settings/databases | DatabaseSettingsPage | Private | AppLayout | manage_databases |
| /dashboard/settings/billing | BillingSettingsPage | Private | AppLayout | view_billing |
| /dashboard/admin | AdminPage | Private | AppLayout | admin |
| /dashboard/admin/teams | AdminTeamsPage | Private | AppLayout | admin |
| /dashboard/admin/billing | AdminBillingPage | Private | AppLayout | admin |
| /dashboard/admin/logs | AdminLogsPage | Private | AppLayout | admin |
| /404 | NotFoundPage | Public | Minimal | None |
| /500 | ErrorPage | Public | Minimal | None |

### 3.2 Navigation Structure

```
Primary Navigation (Sidebar):
+-- Chat             /dashboard/chat           icon: MessageSquare
+-- Schema           /dashboard/schema         icon: Database
+-- History          /dashboard/history        icon: Clock
+-- Settings         /dashboard/settings       icon: Settings

Secondary Navigation (Top bar):
+-- Search (global command palette)
+-- Database selector dropdown
+-- Notification bell
+-- User avatar menu
    +-- Profile
    +-- Settings
    +-- Theme toggle
    +-- Logout

Admin Navigation (within Sidebar, admin only):
+-- Admin            /dashboard/admin          icon: Shield
    +-- Teams
    +-- Billing
    +-- Logs
```

### 3.3 Navigation Behavior

- **Active state**: Current route highlighted in sidebar
- **Collapsed sidebar**: Icons only, expandable on hover (140px expanded)
- **Breadcrumbs**: Shown in page header for nested routes (e.g., Settings > Databases)
- **Keyboard shortcuts**: Cmd+K command palette, Cmd+1-4 for nav items
- **Mobile**: Bottom tab bar replaces sidebar; top bar has hamburger for full nav

---

## 4. State Management

### 4.1 State Architecture

```
+-------------------------------------------------------+
|                   Zustand Stores                        |
|  (Client state -- UI, session, cached preferences)     |
|  +----------+ +----------+ +----------+ +--------+    |
|  |   Auth   | |   UI     | | Settings | | Schema |    |
|  |  Store   | |  Store   | |  Store   | |  Cache |    |
|  +----------+ +----------+ +----------+ +--------+    |
|  +----------+ +----------+ +------------------+       |
|  |  Query   | |  Toast   | |   Notification   |       |
|  |  Store   | |  Store   | |     Store        |       |
|  +----------+ +----------+ +------------------+       |
+-------------------------------------------------------+
                                |
+-------------------------------------------------------+
|               TanStack React Query                      |
|  (Server state -- cached API responses)                |
|  +----------+ +----------+ +----------+ +--------+    |
|  | Queries  | | History  | | Schemas  | | Teams  |    |
|  | (chat)   | | (list)   | | (tree)   | | (admin)|    |
|  +----------+ +----------+ +----------+ +--------+    |
|  +----------+ +-----------------------------------+   |
|  | Feedback | |      Infinite / Paginated          |   |
|  |  Mutate  | |      Query Utilities               |   |
|  +----------+ +-----------------------------------+   |
+-------------------------------------------------------+
```

### 4.2 Zustand Store Specifications

#### 4.2.1 Auth Store

```
stores/auth-store.ts

interface AuthState {
  user: User | null;
  token: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isInitialized: boolean;
  loginInProgress: boolean;
  loginError: string | null;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshSession: () => Promise<void>;
  handleTokenRefresh: () => Promise<string | null>;
  setUser: (user: User) => void;
  initialize: () => Promise<void>;
}

interface User {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  role: 'admin' | 'member' | 'viewer';
  team_id: string;
  permissions: string[];
  mfa_enabled: boolean;
}
```

**Persistence**: Token stored in httpOnly cookie (set by backend on login). refreshToken stored in memory only. user object persisted in localStorage via Zustand persist middleware for hydration on page reload.

**Initialization**: On app mount, initialize() calls GET /v1/auth/me with the cookie. If 401, redirects to /login. If valid, hydrates user state.

#### 4.2.2 UI Store

```
stores/ui-store.ts

interface UIState {
  sidebarOpen: boolean;
  sidebarCollapsed: boolean;
  activeModal: string | null;
  modalData: Record<string, unknown> | null;
  commandPaletteOpen: boolean;
  mobileNavOpen: boolean;

  // Actions
  toggleSidebar: () => void;
  toggleSidebarCollapse: () => void;
  openModal: (name: string, data?: Record<string, unknown>) => void;
  closeModal: () => void;
  toggleCommandPalette: () => void;
  setMobileNavOpen: (open: boolean) => void;
}
```

**Persistence**: sidebarCollapsed persisted in localStorage. All other state is ephemeral.

#### 4.2.3 Query Store

```
stores/query-store.ts

interface QueryState {
  conversations: Map<string, Conversation>;
  activeConversationId: string | null;
  streamingMessageId: string | null;
  streamingContent: string;
  isStreaming: boolean;
  currentAbortController: AbortController | null;

  // Actions
  createConversation: () => string;
  selectConversation: (id: string) => void;
  deleteConversation: (id: string) => void;
  sendQuery: (query: string, databaseId: string, options?: QueryOptions) => Promise<void>;
  cancelQuery: () => void;
  appendStreamingChunk: (chunk: string) => void;
  finalizeMessage: (messageId: string, result: QueryResult) => void;
  setStreamingError: (error: QueryError) => void;
}

interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  created_at: string;
  updated_at: string;
  database_id: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'error';
  content: string;
  sql?: string;
  result?: QueryResult;
  error?: QueryError;
  timestamp: string;
  feedback?: 'positive' | 'negative' | null;
}
```

**Persistence**: Conversation list (titles only) persisted in localStorage. Full message history fetched from API on conversation select.

#### 4.2.4 Settings Store

```
stores/settings-store.ts

interface SettingsState {
  theme: 'system' | 'dark' | 'light';
  defaultModel: string;
  defaultDatabaseId: string | null;
  notifications: {
    email: boolean;
    inApp: boolean;
    queryComplete: boolean;
    weeklyDigest: boolean;
  };
  timezone: string;
  locale: string;

  // Actions
  updateSettings: (settings: Partial<UserSettings>) => Promise<void>;
  fetchSettings: () => Promise<void>;
  resetToDefaults: () => void;
}
```

**Persistence**: All fields persisted in localStorage and synced to backend via PUT /v1/settings.

#### 4.2.5 Schema Cache Store

```
stores/schema-cache-store.ts

interface SchemaCacheState {
  databases: DatabaseInfo[];
  selectedDatabaseId: string | null;
  expandedTables: Set<string>;
  tableCache: Map<string, TableDetail>;
  lastFetchTimestamps: Map<string, number>;

  // Actions
  setDatabases: (dbs: DatabaseInfo[]) => void;
  selectDatabase: (id: string) => void;
  toggleTableExpansion: (tableId: string) => void;
  cacheTableDetail: (tableId: string, detail: TableDetail) => void;
  getTableDetail: (tableId: string) => TableDetail | undefined;
  isStale: (key: string, ttlMs?: number) => boolean;
}
```

**Persistence**: selectedDatabaseId and expandedTables persisted in localStorage. tableCache is ephemeral (fetched on demand via React Query).

#### 4.2.6 Notification Store

```
stores/notification-store.ts

interface NotificationState {
  notifications: Notification[];
  unreadCount: number;
  wsConnected: boolean;

  // Actions
  addNotification: (n: Notification) => void;
  markRead: (id: string) => void;
  markAllRead: () => void;
  setWsConnected: (connected: boolean) => void;
}

interface Notification {
  id: string;
  type: 'query_complete' | 'schema_sync_done' | 'invite' | 'alert' | 'billing';
  title: string;
  body: string;
  read: boolean;
  created_at: string;
  action_url?: string;
}
```

**Persistence**: Notifications persisted in localStorage, synced with backend via API.

#### 4.2.7 Toast Store

```
stores/toast-store.ts

interface ToastState {
  toasts: Toast[];

  // Actions
  success: (title: string, description?: string) => void;
  error: (title: string, description?: string) => void;
  warning: (title: string, description?: string) => void;
  info: (title: string, description?: string) => void;
  dismiss: (id: string) => void;
}

interface Toast {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  description?: string;
  duration?: number; // ms, 0 = persistent
  action?: { label: string; onClick: () => void };
}
```

### 4.3 React Query Configuration

```
lib/react-query.ts

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,        // 30s before refetch
      gcTime: 5 * 60_000,       // Keep in cache 5min after unmount
      retry: 2,
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10_000),
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
    },
    mutations: {
      retry: 0,
    },
  },
});
```

### 4.4 Cross-Store Communication

Stores communicate via React component effects, not direct store-to-store calls:

```
// Example: When auth store initializes, trigger settings fetch
function AuthGate({ children }: { children: React.ReactNode }) {
  const { isInitialized, isAuthenticated, user } = useAuthStore();

  useEffect(() => {
    if (isAuthenticated && user) {
      // Triggers React Query to fetch settings
      // No direct store call
    }
  }, [isAuthenticated, user]);

  if (!isInitialized) return <SplashScreen />;
  if (!isAuthenticated) return <LoginPage />;
  return children;
}
```

### 4.5 State Serialization Rules

| Data Type | Storage Location | Serialization | Maximum Size |
|-----------|-----------------|---------------|-------------|
| Auth user | Zustand + localStorage | JSON | 10KB |
| Auth token | httpOnly cookie | JWT string | 2KB |
| Schema cache | Zustand (memory) | Map serialized | 5MB |
| Conversation titles | Zustand + localStorage | JSON array | 50KB |
| Full messages | React Query cache | Normalized | 20MB (LRU) |
| Settings | Zustand + localStorage | JSON | 5KB |
| Notifications | Zustand + localStorage | JSON | 100KB |
| Theme preference | localStorage | String | 100B |

---

## 5. Caching Strategy

### 5.1 Cache Layers

```
Layer 1: Browser HTTP Cache (CDN + Service Worker)
Layer 2: React Query In-Memory Cache (server state)
Layer 3: Zustand Persistence (localStorage -- client state)
Layer 4: IndexedDB (large data -- schema full exports)
Layer 5: Service Worker Cache (offline support, static assets)
```

### 5.2 Per-Endpoint Cache Configuration

| API Endpoint | staleTime | gcTime | Cache Key | Invalidation Trigger |
|-------------|-----------|--------|-----------|---------------------|
| GET /v1/query/{id}/status | 0 (polls) | 0 | queryId | -- |
| GET /v1/schema/databases | 60s | 5min | ['schema', 'databases'] | Schema sync event |
| GET /v1/schema/database/{id} | 60s | 5min | ['schema', 'database', id] | Schema sync event |
| GET /v1/schema/table/{id} | 120s | 10min | ['schema', 'table', id] | Schema sync event |
| GET /v1/history | 30s | 2min | ['history', filters] | New query completed |
| GET /v1/history/{id} | 60s | 5min | ['history', 'detail', id] | -- |
| GET /v1/settings | 5min | 30min | ['settings'] | Settings updated |
| GET /v1/admin/teams | 30s | 2min | ['admin', 'teams'] | Invite accepted |
| GET /v1/admin/usage | 60s | 5min | ['admin', 'usage', period] | -- |
| GET /v1/conversations | 30s | 5min | ['conversations'] | New/delete conversation |
| GET /v1/conversation/{id} | 60s | 10min | ['conversation', id] | New message sent |

### 5.3 Optimistic Updates

| Mutation | Optimistic Update Strategy | Rollback Strategy |
|----------|---------------------------|-------------------|
| Send query | Append user message immediately | Remove on error + toast |
| Delete conversation | Remove from list immediately | Re-add on error |
| Give feedback | Update message UI immediately | Revert on error |
| Update settings | Apply locally immediately | Revert on error + toast |
| Add database | Add to list as "connecting" | Remove on error |

### 5.4 Service Worker Cache Strategy

```
service-worker.ts

const CACHE_STRATEGIES = {
  // Cache-first: static assets, fonts, icons
  staticAssets: new CacheFirst({
    cacheName: 'static-assets-v1',
    maxAgeSeconds: 30 * 24 * 60 * 60, // 30 days
  }),

  // Network-first: API calls
  apiCalls: new NetworkFirst({
    cacheName: 'api-cache-v1',
    networkTimeoutSeconds: 5,
    maxAgeSeconds: 60, // 1 minute fallback
  }),

  // Network-only: mutations, auth
  mutations: new NetworkOnly(),

  // Stale-while-revalidate: non-critical assets
  nonCritical: new StaleWhileRevalidate({
    cacheName: 'non-critical-v1',
    maxAgeSeconds: 24 * 60 * 60, // 1 day
  }),
};
```

### 5.5 Cache Invalidation

| Event | Invalidation Action |
|-------|-------------------|
| WebSocket: query.completed | Invalidate ['history'] query |
| WebSocket: schema.synced | Invalidate all ['schema', ...] queries |
| WebSocket: settings.updated | Invalidate ['settings'] |
| WebSocket: team.updated | Invalidate ['admin', 'teams'] |
| Manual pull-to-refresh | Invalidate all active queries |
| Visibility change (tab focus) | Refetch stale queries |

---

## 6. Authentication & Session Management

### 6.1 Auth Flow

```
Login Flow:
  1. User submits email + password
  2. POST /v1/auth/login
  3. Backend validates credentials
  4. Backend sets httpOnly cookie with access token (JWT, 15min TTL)
  5. Backend returns { user, expires_in, mfa_required }
  6. If MFA required: show MFA challenge screen
  7. If MFA passed or not required: redirect to /dashboard

Token Refresh Flow:
  1. API client detects 401 response
  2. POST /v1/auth/refresh (sends httpOnly refresh cookie)
  3. Backend validates refresh token (7-day TTL, rotating)
  4. Backend sets new access token cookie
  5. API client retries original request
  6. If refresh fails (401): redirect to /login

Logout Flow:
  1. User clicks logout
  2. POST /v1/auth/logout
  3. Backend invalidates refresh token
  4. Backend clears both cookies
  5. Client clears all Zustand state
  6. Redirect to /login
```

### 6.2 API Client Interceptor

```
lib/api-client.ts

const apiClient = createClient({
  baseUrl: process.env.NEXT_PUBLIC_API_URL!,
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include', // Send cookies
});

// Response interceptor for token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && !error.config._retry) {
      error.config._retry = true;
      try {
        await apiClient.post('/v1/auth/refresh');
        return apiClient(error.config); // Retry original request
      } catch {
        useAuthStore.getState().logout();
        window.location.href = '/login';
        return Promise.reject(error);
      }
    }
    return Promise.reject(error);
  }
);
```

### 6.3 Session Validation

| Check | Location | Action |
|-------|----------|--------|
| Cookie present | Next.js middleware | Pass through; if absent, redirect to /login |
| Token expiry | API response interceptor | Trigger refresh; if refresh fails, logout |
| User fetch on mount | AuthStore.initialize() | GET /v1/auth/me; if 401, redirect to login |
| Periodic refresh | setInterval(15min) | Silent token refresh every 14 minutes |
| Tab sync | storage event listener | If another tab logs out, this tab logs out too |

### 6.4 MFA Support

```
MFA Challenge Flow:
  1. Login returns mfa_required: true, mfa_token: string
  2. Show MFA input screen (TOTP 6-digit code)
  3. POST /v1/auth/mfa/verify { mfa_token, code }
  4. On success: backend sets auth cookies, redirect to /dashboard
  5. On failure: show error, allow retry (max 5 attempts)

MFA Setup Flow:
  1. POST /v1/auth/mfa/setup -> returns { qr_code_url, secret }
  2. Display QR code for authenticator app
  3. User scans and enters code from app
  4. POST /v1/auth/mfa/confirm { code }
  5. On success: MFA enabled, show recovery codes
```

### 6.5 Session Timeout Behavior

| Condition | Action |
|-----------|--------|
| Refresh token expired (>7d inactivity) | Redirect to /login with session expired message |
| Idle for 30min | Show idle timeout warning modal (2min countdown) |
| No response within countdown | Auto-logout |
| User clicks "Stay signed in" | Reset idle timer, refresh token |

---

## 7. Design System

### 7.1 Design Tokens

```
/* tokens.css - Generated from design-tokens.json */

:root {
  /* Colors - Light Mode */
  --background: 0 0% 100%;
  --foreground: 222 47% 11%;
  --card: 0 0% 100%;
  --card-foreground: 222 47% 11%;
  --popover: 0 0% 100%;
  --popover-foreground: 222 47% 11%;
  --primary: 221 83% 53%;
  --primary-foreground: 210 40% 98%;
  --secondary: 210 40% 96%;
  --secondary-foreground: 222 47% 11%;
  --muted: 210 40% 96%;
  --muted-foreground: 215 16% 47%;
  --accent: 210 40% 96%;
  --accent-foreground: 222 47% 11%;
  --destructive: 0 84% 60%;
  --destructive-foreground: 210 40% 98%;
  --success: 142 76% 36%;
  --success-foreground: 210 40% 98%;
  --warning: 38 92% 50%;
  --warning-foreground: 210 40% 98%;
  --border: 214 32% 91%;
  --input: 214 32% 91%;
  --ring: 221 83% 53%;
  --radius: 0.5rem;
}

.dark {
  --background: 222 47% 11%;
  --foreground: 210 40% 98%;
  --card: 223 47% 15%;
  --card-foreground: 210 40% 98%;
  --popover: 223 47% 15%;
  --popover-foreground: 210 40% 98%;
  --primary: 217 91% 60%;
  --primary-foreground: 222 47% 11%;
  --secondary: 215 25% 27%;
  --secondary-foreground: 210 40% 98%;
  --muted: 215 25% 27%;
  --muted-foreground: 215 20% 65%;
  --accent: 215 25% 27%;
  --accent-foreground: 210 40% 98%;
  --destructive: 0 62% 50%;
  --destructive-foreground: 210 40% 98%;
  --success: 142 50% 40%;
  --success-foreground: 210 40% 98%;
  --warning: 38 62% 50%;
  --warning-foreground: 210 40% 98%;
  --border: 215 25% 27%;
  --input: 215 25% 27%;
  --ring: 224 76% 48%;
}
```

### 7.2 Typography Scale

```
--font-sans: 'Inter', system-ui, -apple-system, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', monospace;

--text-xs:   0.75rem;   /* 12px */
--text-sm:   0.875rem;  /* 14px */
--text-base: 1rem;      /* 16px */
--text-lg:   1.125rem;  /* 18px */
--text-xl:   1.25rem;   /* 20px */
--text-2xl:  1.5rem;    /* 24px */
--text-3xl:  1.875rem;  /* 30px */
--text-4xl:  2.25rem;   /* 36px */

--leading-tight: 1.25;
--leading-normal: 1.5;
--leading-relaxed: 1.625;
--leading-loose: 2;
```

### 7.3 Spacing Scale

```
--spacing-0:  0;
--spacing-1:  0.25rem;  /* 4px */
--spacing-2:  0.5rem;   /* 8px */
--spacing-3:  0.75rem;  /* 12px */
--spacing-4:  1rem;     /* 16px */
--spacing-5:  1.25rem;  /* 20px */
--spacing-6:  1.5rem;   /* 24px */
--spacing-8:  2rem;     /* 32px */
--spacing-10: 2.5rem;   /* 40px */
--spacing-12: 3rem;     /* 48px */
--spacing-16: 4rem;     /* 64px */
--spacing-20: 5rem;     /* 80px */
--spacing-24: 6rem;     /* 96px */
```

### 7.4 Shadow Scale

```
--shadow-sm:   0 1px 2px 0 rgb(0 0 0 / 0.05);
--shadow-md:   0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
--shadow-lg:   0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
--shadow-xl:   0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1);
--shadow-2xl:  0 25px 50px -12px rgb(0 0 0 / 0.25);

.dark {
  --shadow-sm:  0 1px 2px 0 rgb(0 0 0 / 0.3);
  --shadow-md:  0 4px 6px -1px rgb(0 0 0 / 0.4), 0 2px 4px -2px rgb(0 0 0 / 0.3);
  --shadow-lg:  0 10px 15px -3px rgb(0 0 0 / 0.4), 0 4px 6px -4px rgb(0 0 0 / 0.3);
  --shadow-xl:  0 20px 25px -5px rgb(0 0 0 / 0.5), 0 8px 10px -6px rgb(0 0 0 / 0.4);
  --shadow-2xl: 0 25px 50px -12px rgb(0 0 0 / 0.5);
}
```

### 7.5 Animation Tokens

```
--duration-fast:   150ms;
--duration-normal: 200ms;
--duration-slow:   300ms;
--ease-out: cubic-bezier(0.16, 1, 0.3, 1);
--ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
--ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
```

### 7.6 Component Library Usage

| shadcn/ui Component | Usage | Customizations |
|--------------------|-------|---------------|
| Button | All clickable actions | Extended variants: primary, secondary, ghost, destructive, link |
| Input | Text inputs, search | Added withIcon, error state |
| Select | Dropdowns | Added loading state, grouped options |
| Dialog | Modals | Added size prop (sm, md, lg, xl, fullscreen) |
| Sheet | Side panels, mobile nav | Added position (left, right) |
| DropdownMenu | User menu, actions | Added withIcon option |
| Tabs | Settings, schema detail | Added vertical variant |
| Table | Data display | Added sortable headers, row selection, empty state |
| Card | Content containers | Added interactive variant (hoverable) |
| Badge | Status indicators | Added color variants matching semantic colors |
| Toast | Notifications | Using sonner for toast system |
| Skeleton | Loading states | Added variant (text, card, table-row, avatar) |
| Tooltip | Icon explanations | Added delay prop |
| Popover | Contextual menus | Standard implementation |
| Command | Command palette | Using cmdk |
| Separator | Dividers | Standard implementation |
| Switch | Toggle settings | Standard implementation |
| Checkbox | Multi-select | Standard implementation |
| RadioGroup | Single select | Standard implementation |
| ProgressBar | Loading progress | Added size prop, determinate/indeterminate |
| Avatar | User avatars | Added fallback initials, status dot |
| Alert | Inline messages | Added info, success, warning, error variants |

### 7.7 Icons

- **Library**: Lucide React (tree-shakeable, consistent 24px stroke style)
- **Convention**: Import individual icons only, never the whole set
- **Size**: Default 16px for inline, 20px for nav, 24px for empty states
- **Custom icons**: SVG components in /components/icons/ for product-specific icons (e.g., Logo, Database types)

---

## 8. Accessibility

### 8.1 Compliance Target

**WCAG 2.2 Level AA** -- Minimum. Level AAA targeted for core chat flow.

### 8.2 Color Contrast

| Token Pair | Light Mode Ratio | Dark Mode Ratio | WCAG Level |
|-----------|-----------------|-----------------|------------|
| --foreground on --background | 12.5:1 | 13.2:1 | AAA |
| --primary on --background | 4.8:1 | 5.2:1 | AA |
| --muted-foreground on --background | 4.2:1 | 4.5:1 | AA |
| --destructive on --background | 3.8:1 | 4.1:1 | AA (border/icon only) |
| --success on --background | 3.5:1 | 3.8:1 | AA (border/icon only) |

### 8.3 Keyboard Navigation

| Feature | Implementation |
|---------|---------------|
| Tab order | Logical DOM order; tabIndex={0} on interactive containers |
| Focus ring | :focus-visible only (not :focus); 2px solid --ring offset 2px |
| Focus trap | Modals, drawers, command palette use focus-trap-react |
| Skip link | Visible on first Tab press: "Skip to main content" |
| Arrow navigation | Chat list (up/down), table rows (up/down), tabs (left/right) |
| Escape | Closes modals, drawers, dropdowns, command palette |
| Enter/Space | Activates focused item |
| Cmd+K | Opens command palette |

### 8.4 ARIA Patterns

| Component | ARIA Role | ARIA Attributes |
|-----------|-----------|----------------|
| Sidebar nav | navigation | aria-label="Main navigation" |
| Chat messages | log | aria-live="polite" for streaming |
| SQL display | region | aria-label="Generated SQL" |
| Result table | table | aria-label="Query results", aria-sort on headers |
| Toast notifications | status | aria-live="polite", role="alert" for errors |
| Modals | dialog | aria-modal="true", aria-labelledby |
| Command palette | combobox | aria-expanded, aria-activedescendant |
| Tabs | tablist + tab + tabpanel | aria-selected, aria-controls, aria-labelledby |
| Progress indicator | progressbar | aria-valuenow, aria-valuemin, aria-valuemax |
| Error summary | alert | aria-live="assertive" |

### 8.5 Screen Reader Support

- **SQL results**: Table announced with row/column counts; pagination announced
- **Streaming responses**: Content announced incrementally (debounced every 500ms, not on every chunk)
- **Loading states**: Skeleton elements have aria-hidden="true"; loading container has aria-busy="true"
- **Error states**: Inline errors linked to inputs via aria-describedby
- **Charts**: Data table provided alongside chart; chart element has role="img" with aria-label describing the visualization
- **Drag-and-drop**: Replaced with buttons for keyboard users (move up/down, move to position)

### 8.6 Reduced Motion

```
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

All animations that convey meaning (e.g., loading spinner, progress bar) use prefers-reduced-motion: no-preference as a media query wrapper. Meaningful animations must not be removed entirely -- provide a static alternative (e.g., determinate progress bar instead of indeterminate spinner).

---

## 9. Dark Mode

### 9.1 Strategy

- **Default**: System preference (prefers-color-scheme)
- **Override**: User toggle via settings menu (three states: System / Light / Dark)
- **Persistence**: Stored in localStorage, synced to backend via user settings
- **SSR**: Cookie-based detection -- server reads cookie to apply correct class before hydration (prevents flash)

### 9.2 Implementation

```
lib/theme-provider.tsx
Uses next-themes internally

"use client";
import { ThemeProvider as NextThemesProvider } from "next-themes";
import { type ThemeProviderProps } from "next-themes/dist/types";

export function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
      {...props}
    >
      {children}
    </NextThemesProvider>
  );
}
```

```
middleware.ts

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const theme = request.cookies.get("theme")?.value;
  const response = NextResponse.next();

  if (theme === "dark" || theme === "light") {
    response.cookies.set("resolved-theme", theme, {
      path: "/",
      maxAge: 60 * 60 * 24 * 365,
    });
  }

  return response;
}
```

### 9.3 Dark Mode Asset Strategy

| Asset Type | Light | Dark |
|-----------|-------|------|
| Logos | Full color | Inverted/white version |
| Illustrations | Light background variants | Dark background variants |
| Charts | Light theme (white bg) | Dark theme (dark bg) |
| SQL syntax colors | Light theme highlighting | Dark theme highlighting |
| Code block backgrounds | --muted light | --muted dark |

### 9.4 Dark Mode Transition

```
html {
  transition: background-color 200ms ease, color 200ms ease;
}

html[data-theme-transition="disabled"] {
  transition: none !important;
}
```

On initial page load, a blocking script in <head> reads the cookie or localStorage and applies the class before rendering to prevent flash of wrong theme.

---

## 10. Internationalization

### 10.1 Strategy

- **Library**: i18next + react-i18next
- **Backend**: i18next-http-backend (lazy-load locale files)
- **Detection**: i18next-browser-languageDetector
- **Default locale**: en-US
- **Phase 1 locales**: en-US, ja-JP, zh-CN
- **Future locales**: de-DE, fr-FR, es-ES, pt-BR, ko-KR

### 10.2 Locale Loading

```
lib/i18n.ts

import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import HttpApi from "i18next-http-backend";
import LanguageDetector from "i18next-browser-languageDetector";

i18n
  .use(HttpApi)
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: "en-US",
    debug: process.env.NODE_ENV === "development",
    interpolation: {
      escapeValue: false,
    },
    backend: {
      loadPath: "/locales/{{lng}}/{{ns}}.json",
    },
    ns: ["common", "chat", "schema", "settings", "admin", "errors"],
    defaultNS: "common",
    detection: {
      order: ["cookie", "localStorage", "navigator", "htmlTag"],
      caches: ["cookie"],
    },
  });
```

### 10.3 Translation File Structure

```
/public/locales/
+-- en-US/
|   +-- common.json      # General UI strings
|   +-- chat.json         # Chat interface
|   +-- schema.json       # Schema browser
|   +-- settings.json     # Settings pages
|   +-- admin.json        # Admin pages
|   +-- errors.json       # Error messages
+-- ja-JP/
|   +-- ...
+-- zh-CN/
    +-- ...
```

### 10.4 RTL Support

- **Phase 1**: Not required (no Arabic/Hebrew locales)
- **Prepared for**: All layout components use logical CSS properties (margin-inline-start instead of margin-left, border-inline-end instead of border-right)
- **RTL toggle**: dir="rtl" on <html> element when RTL locale active

### 10.5 Number & Date Formatting

```
lib/format.ts

import { useCallback } from "react";
import { useTranslation } from "react-i18next";

export function useFormat() {
  const { i18n } = useTranslation();

  const formatNumber = useCallback(
    (value: number, options?: Intl.NumberFormatOptions) =>
      new Intl.NumberFormat(i18n.language, options).format(value),
    [i18n.language]
  );

  const formatCurrency = useCallback(
    (value: number, currency = "USD") =>
      new Intl.NumberFormat(i18n.language, {
        style: "currency",
        currency,
      }).format(value),
    [i18n.language]
  );

  const formatDate = useCallback(
    (date: Date, options?: Intl.DateTimeFormatOptions) =>
      new Intl.DateTimeFormat(i18n.language, options).format(date),
    [i18n.language]
  );

  const formatRelativeTime = useCallback(
    (date: Date) => {
      const now = Date.now();
      const diff = now - date.getTime();
      const units: [number, Intl.RelativeTimeFormatUnit][] = [
        [1000 * 60 * 60 * 24 * 365, "year"],
        [1000 * 60 * 60 * 24 * 30, "month"],
        [1000 * 60 * 60 * 24, "day"],
        [1000 * 60 * 60, "hour"],
        [1000 * 60, "minute"],
        [1000, "second"],
      ];
      for (const [unitMs, unit] of units) {
        if (Math.abs(diff) >= unitMs || unit === "second") {
          const value = -Math.round(diff / unitMs);
          const rtf = new Intl.RelativeTimeFormat(i18n.language, {
            numeric: "auto",
          });
          return rtf.format(value, unit);
        }
      }
    },
    [i18n.language]
  );

  return { formatNumber, formatCurrency, formatDate, formatRelativeTime };
}
```

### 10.6 Translation Coverage Requirements

| Feature | en-US | ja-JP | zh-CN |
|---------|-------|-------|-------|
| Common UI (buttons, labels, nav) | 100% | 100% | 100% |
| Chat interface | 100% | 100% | 100% |
| Schema browser | 100% | 100% | 100% |
| Settings | 100% | 100% | 100% |
| Admin | 100% | 80% | 80% |
| Error messages | 100% | 90% | 90% |
| Help text / tooltips | 100% | 70% | 70% |

---

## 11. Responsive Design

### 11.1 Breakpoints

| Breakpoint | Width | Target Devices | Layout Changes |
|-----------|-------|---------------|----------------|
| sm | 640px | Large phones | Single column, stacked nav |
| md | 768px | Tablets | Sidebar collapsible, two-column possible |
| lg | 1024px | Small laptops | Full sidebar, multi-column |
| xl | 1280px | Desktop | Max width content, side panels |
| 2xl | 1536px | Large screens | Centered content with max-width |

### 11.2 Responsive Layout Modes

```
Mobile (<768px):
+----------------------+
|    Top Bar (sticky)  |
| [Hamburger] [Title]  |
+----------------------+
|                      |
|    Main Content      |
|    (full width)      |
|                      |
+----------------------+
|   Bottom Tab Bar     |
| [Chat][Schema][Hist] |
+----------------------+

Tablet (768-1024px):
+--------------+-------+
| Sidebar      | Main  |
| (collapsible)|       |
| Icons + text |       |
|              |       |
|              |       |
+--------------+-------+

Desktop (>1024px):
+--+--------------+----+
|S |   Main       |RPan|
|i |   Content    |el  |
|d |              |    |
|e |              |    |
|b |              |    |
|a |              |    |
|r |              |    |
+--+--------------+----+
```

### 11.3 Component Responsive Behavior

| Component | Mobile (<768px) | Tablet (768-1024px) | Desktop (>1024px) |
|-----------|----------------|-------------------|-------------------|
| Sidebar | Hidden (overlay with hamburger) | Collapsible icon-only | Full-width (240px) |
| Chat input | Single line, expandable | Multi-line | Multi-line |
| SQL display | Full width, scrollable | Full width | Max 80ch width |
| Result table | Horizontal scroll | Horizontal scroll | Full width |
| Schema tree | Full width | 50% width | 33% width |
| History list | Full width, compact | 50% width | 33% width |
| Settings | Single column | Single column | Two column |
| Admin charts | Stacked vertically | 2-column grid | 3-column grid |
| Right panel | Always hidden | Toggleable | Persistent |
| Command palette | Full screen overlay | Centered modal | Centered modal |

### 11.4 Touch Targets

| Element | Minimum Size | Notes |
|---------|-------------|-------|
| Navigation items | 44x44px | Bottom tab bar icons |
| Buttons | 44x44px | Icon buttons need hit area even if icon is smaller |
| Input fields | 44px height | Comfortable for tapping |
| Dropdown options | 44px height | Easy to tap without zoom |
| Swipe actions | 80px minimum | Chat items, history items |
| Pull-to-refresh | 60px activation | History list |

---

## 12. Real-Time Updates

### 12.1 Architecture

```
+------------------+     WebSocket      +------------------+
|   Browser Client | <---------------> |  WS Gateway (8300)|
|   (useWebSocket) |                    |                   |
+------------------+                    +--------+---------+
                                                 |
                                        Internal Pub/Sub
                                                 |
                            +------------+-------+--------+
                            |            |                |
                      +-----v----+ +----v----+ +----v----+
                      |  Query   | | Schema  | | Learning|
                      |  Service | |  Sync   | |  Engine |
                      +----------+ +---------+ +---------+
```

### 12.2 WebSocket Connection

```
lib/websocket.ts

class WebSocketManager {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000; // doubles each attempt
  private subscriptions: Map<string, Set<(data: unknown) => void>> = new Map();
  private connectionListeners: Set<(connected: boolean) => void> = new Set();

  connect(token: string): void {
    const url = `${process.env.NEXT_PUBLIC_WS_URL}/ws?token=${token}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.connectionListeners.forEach((cb) => cb(true));
    };

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        const { type, payload } = message;
        const handlers = this.subscriptions.get(type);
        if (handlers) {
          handlers.forEach((handler) => handler(payload));
        }
      } catch {
        console.error("Failed to parse WebSocket message");
      }
    };

    this.ws.onclose = () => {
      this.connectionListeners.forEach((cb) => cb(false));
      this.reconnect();
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  private reconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
    setTimeout(() => {
      this.reconnectAttempts++;
      const token = useAuthStore.getState().token;
      if (token) this.connect(token);
    }, delay);
  }

  subscribe(eventType: string, handler: (data: unknown) => void): () => void {
    if (!this.subscriptions.has(eventType)) {
      this.subscriptions.set(eventType, new Set());
    }
    this.subscriptions.get(eventType)!.add(handler);
    return () => {
      this.subscriptions.get(eventType)?.delete(handler);
    };
  }

  onConnectionChange(handler: (connected: boolean) => void): () => void {
    this.connectionListeners.add(handler);
    return () => this.connectionListeners.delete(handler);
  }

  disconnect(): void {
    this.ws?.close();
    this.ws = null;
  }
}

export const wsManager = new WebSocketManager();
```

### 12.3 Event Types

| Event | Direction | Payload | Handler Action |
|-------|-----------|---------|---------------|
| query.status | Server -> Client | { query_id, status, progress? } | Update query status indicator |
| query.completed | Server -> Client | { query_id, result } | Render full result |
| query.error | Server -> Client | { query_id, error } | Show error state |
| query.stream | Server -> Client | { query_id, chunk, type } | Append to streaming content |
| schema.syncing | Server -> Client | { database_id, status } | Show sync progress |
| schema.synced | Server -> Client | { database_id, tables_count } | Invalidate schema cache, show toast |
| schema.error | Server -> Client | { database_id, error } | Show sync error |
| notification | Server -> Client | { notification } | Add to notification store, show toast |
| feedback.processed | Server -> Client | { feedback_id, status } | Update feedback UI state |
| team.updated | Server -> Client | { team_id, change_type } | Invalidate team queries |
| settings.updated | Server -> Client | { user_id, changed_keys } | Update settings store if applicable |
| connection.status | Client <-> Server | { connected, latency_ms } | Connection health monitoring |

### 12.4 Fallback Strategy

| Scenario | Fallback |
|----------|---------|
| WebSocket connection fails | HTTP polling (GET /v1/query/{id}/status every 500ms for active queries) |
| WebSocket reconnecting | Show connection indicator ("Reconnecting...") |
| WebSocket not supported | SSE fallback via EventSource API |
| SSE not supported | Full HTTP polling |
| All real-time methods fail | Manual refresh button; retry every 30s |

### 12.5 Connection Health

```
lib/websocket-health.ts

// Ping/pong every 30s to detect dead connections
setInterval(() => {
  if (wsManager.getState() === WebSocket.OPEN) {
    wsManager.send({ type: "ping", timestamp: Date.now() });
  }
}, 30_000);

// If no pong received within 10s of ping, reconnect
// Track latency from ping-pong timestamps
// Expose connection quality: 'good' (<100ms), 'degraded' (100-500ms), 'poor' (>500ms)
```

---

## 13. Component Hierarchy

### 13.1 Full Component Tree

```
<App>
+-- <ThemeProvider>
|   +-- <I18nextProvider>
|       +-- <QueryClientProvider>
|           +-- <Router>
|               +-- <AuthGate>
|               |   +-- <SplashScreen />
|               |   +-- <LoginPage>                      # /login
|               |   |   +-- <LoginForm>
|               |   |   |   +-- <Input label="Email" />
|               |   |   |   +-- <Input label="Password" type="password" />
|               |   |   |   +-- <Button variant="primary">Sign In</Button>
|               |   |   |   +-- <MfaChallenge />
|               |   |   +-- <SSOProviderList />
|               |   |
|               |   +-- <AppLayout>                       # Authenticated routes
|               |       +-- <Sidebar>
|               |       |   +-- <Logo />
|               |       |   +-- <SidebarNav>
|               |       |   |   +-- <NavItem icon={MessageSquare} label="Chat" href="/dashboard/chat" />
|               |       |   |   +-- <NavItem icon={Database} label="Schema" href="/dashboard/schema" />
|               |       |   |   +-- <NavItem icon={Clock} label="History" href="/dashboard/history" />
|               |       |   |   +-- <NavDivider />
|               |       |   |   +-- <NavItem icon={Settings} label="Settings" href="/dashboard/settings" />
|               |       |   |   +-- <AdminNavItems />
|               |       |   |       +-- <NavItem icon={Shield} label="Admin" href="/dashboard/admin" />
|               |       |   |       +-- <NavItem icon={FileText} label="Logs" href="/dashboard/admin/logs" />
|               |       |   +-- <DatabaseSelector>
|               |       |   |   +-- <Select options={databases} />
|               |       |   |   +-- <ConnectionStatusDot />
|               |       |   +-- <UserMenu>
|               |       |       +-- <Avatar user={user} />
|               |       |       +-- <UserInfo name, email />
|               |       |       +-- <DropdownMenu>
|               |       |       |   +-- <MenuItem>Profile</MenuItem>
|               |       |       |   +-- <MenuItem>Settings</MenuItem>
|               |       |       |   +-- <MenuItem>Theme</MenuItem>
|               |       |       |   +-- <MenuItem>Logout</MenuItem>
|               |       |       +-- </DropdownMenu>
|               |       |
|               |       +-- <TopBar>
|               |       |   +-- <HamburgerButton />
|               |       |   +-- <Breadcrumbs />
|               |       |   +-- <CommandPaletteTrigger />
|               |       |   +-- <NotificationBell>
|               |       |   |   +-- <Icon />
|               |       |   |   +-- <UnreadBadge count={unread} />
|               |       |   |   +-- <NotificationDropdown>
|               |       |   |       +-- <NotificationItem />
|               |       |   |       +-- <Button>View All</Button>
|               |       |   +-- <ConnectionStatusIndicator />
|               |       |
|               |       +-- <main>
|               |           +-- <ChatPage>               # /dashboard/chat
|               |           |   +-- <ChatLayout>
|               |           |       +-- <ConversationList>
|               |           |       |   +-- <SearchConversations />
|               |           |       |   +-- <NewConversationButton />
|               |           |       |   +-- <ConversationItem />
|               |           |       +-- <ChatArea>
|               |           |       |   +-- <ChatMessageList>
|               |           |       |   |   +-- <WelcomeMessage />
|               |           |       |   |   +-- <UserMessage>
|               |           |       |   |   |   +-- <MessageContent text />
|               |           |       |   |   +-- <AssistantMessage>
|               |           |       |   |   |   +-- <ThinkingIndicator />
|               |           |       |   |   |   +-- <SqlDisplay sql, copyable />
|               |           |       |   |   |   +-- <ResultTable data, paginated, sortable />
|               |           |       |   |   +-- <ErrorMessage error, policyDetails />
|               |           |       |   |   +-- <StreamingMessage content />
|               |           |       |   +-- <ChatInput>
|               |           |       |       +-- <Textarea autoResize />
|               |           |       |       +-- <ModelSelector />
|               |           |       |       +-- <SubmitButton />
|               |           |       |       +-- <CancelButton />
|               |           |       +-- <ChatHistoryPanel>
|               |           |           +-- <RelatedQueries />
|               |           |           +-- <QueryMetadata tokens, cost, time />
|               |           |
|               |           +-- <SchemaPage>             # /dashboard/schema
|               |           |   +-- <SchemaLayout>
|               |           |       +-- <SchemaSidebar>
|               |           |       |   +-- <DatabaseTree>
|               |           |       |   |   +-- <SchemaNode name>
|               |           |       |   |   |   +-- <TableNode name, expandable>
|               |           |       |   |   |       +-- <ColumnNode name, type, nullable>
|               |           |       |   +-- <SearchTables />
|               |           |       |   +-- <SchemaSyncButton />
|               |           |       +-- <TableDetailPanel>
|               |           |           +-- <TableHeader name, rowCount, description />
|               |           |           +-- <ColumnTable columns, types, descriptions />
|               |           |           +-- <RelationshipList foreignKeys, suggested />
|               |           |           +-- <IndexList indexes />
|               |           |           +-- <SampleDataPreview rows={20} />
|               |           |
|               |           +-- <HistoryPage>            # /dashboard/history
|               |           |   +-- <HistoryLayout>
|               |           |       +-- <HistoryFilters>
|               |           |       |   +-- <DateRangePicker />
|               |           |       |   +-- <Select label="Status" options={statuses} />
|               |           |       |   +-- <Select label="Database" options={databases} />
|               |           |       |   +-- <SearchInput placeholder="Search queries..." />
|               |           |       +-- <HistoryList>
|               |           |       |   +-- <HistoryItem>
|               |           |       |       +-- <QueryPreview text, truncated />
|               |           |       |       +-- <StatusBadge status />
|               |           |       |       +-- <Timestamp relative />
|               |           |       |       +-- <CostBadge cost />
|               |           |       |       +-- <ActionButtons view, share, delete />
|               |           |       +-- <Pagination />
|               |           |       +-- <HistoryDetailPanel>
|               |           |           +-- <QueryDetail />
|               |           |           +-- <SqlDisplay sql />
|               |           |           +-- <ResultTable data />
|               |           |           +-- <QueryMetadata />
|               |           |
|               |           +-- <SettingsPage>           # /dashboard/settings
|               |           |   +-- <SettingsLayout>
|               |           |       +-- <SettingsNav>
|               |           |       |   +-- <SettingsNavItem>Profile</SettingsNavItem>
|               |           |       |   +-- <SettingsNavItem>Team</SettingsNavItem>
|               |           |       |   +-- <SettingsNavItem>Databases</SettingsNavItem>
|               |           |       |   +-- <SettingsNavItem>Billing</SettingsNavItem>
|               |           |       +-- <ProfileSettings>
|               |           |       |   +-- <AvatarUpload />
|               |           |       |   +-- <FormField label="Name" />
|               |           |       |   +-- <FormField label="Email" disabled />
|               |           |       |   +-- <TimezoneSelect />
|               |           |       |   +-- <LocaleSelect />
|               |           |       |   +-- <ThemeToggle />
|               |           |       |   +-- <Button>Save</Button>
|               |           |       +-- <TeamSettings>
|               |           |       |   +-- <TeamMemberList>
|               |           |       |   |   +-- <TeamMemberRow avatar, name, role, actions />
|               |           |       |   +-- <InviteMemberForm email, role />
|               |           |       |   +-- <PendingInvitesList />
|               |           |       +-- <DatabaseSettings>
|               |           |       |   +-- <DatabaseConnectionList>
|               |           |       |   |   +-- <DatabaseConnectionCard name, type, status, actions />
|               |           |       |   +-- <AddDatabaseButton />
|               |           |       |   +-- <DatabaseConnectionForm>
|               |           |       |       +-- <FormField label="Name" />
|               |           |       |       +-- <Select label="Type" options={dbTypes} />
|               |           |       |       +-- <FormField label="Host" />
|               |           |       |       +-- <FormField label="Port" />
|               |           |       |       +-- <FormField label="Database name" />
|               |           |       |       +-- <FormField label="Username" />
|               |           |       |       +-- <PasswordField label="Password" />
|               |           |       |       +-- <SSLConfig />
|               |           |       |       +-- <TestConnectionButton />
|               |           |       |       +-- <Button>Save</Button>
|               |           |       +-- <BillingSettings>
|               |           |           +-- <CurrentPlanCard plan, usage, renewal />
|               |           |           +-- <UsageChart />
|               |           |           +-- <InvoiceHistory />
|               |           |           +-- <PaymentMethodForm />
|               |           |
|               |           +-- <AdminPage>              # /dashboard/admin
|               |           |   +-- <AdminLayout>
|               |           |       +-- <AdminOverview>
|               |           |       |   +-- <UsageMetricsGrid>
|               |           |       |       +-- <MetricCard label="Queries today" value trend />
|               |           |       |       +-- <MetricCard label="Active users" value trend />
|               |           |       |       +-- <MetricCard label="Avg latency" value trend />
|               |           |       |       +-- <MetricCard label="Cost today" value trend />
|               |           |       |   +-- <QueriesOverTimeChart />
|               |           |       |   +-- <LatencyHeatmap />
|               |           |       |   +-- <TopDatabasesTable />
|               |           |       |   +-- <ErrorRateChart />
|               |           |       +-- <AdminTeams>
|               |           |       |   +-- <AdminTeamTable search, filter, paginate>
|               |           |       +-- <AdminBilling>
|               |           |       |   +-- <AllInvoices />
|               |           |       |   +-- <SubscriptionManagement />
|               |           |       |   +-- <PlanChangeRequests />
|               |           |       +-- <AdminLogs>
|               |           |           +-- <LogFilters dateRange, level, source />
|               |           |           +-- <LogTable virtualized />
|               |           |
|               |           +-- <NotFoundPage />
|               |
|               +-- <CommandPalette>
|               |   +-- <SearchInput />
|               |   +-- <CommandGroup heading="Pages">
|               |   |   +-- <CommandItem />
|               |   +-- <CommandGroup heading="Actions">
|               |   |   +-- <CommandItem />
|               |   +-- <CommandGroup heading="Databases">
|               |       +-- <CommandItem />
|               |
|               +-- <ToastContainer />
|               +-- <GlobalErrorBoundary />
```

### 13.2 Component Responsibility Matrix

| Component | State Source | Data Dependencies | Re-render Triggers |
|-----------|-------------|-------------------|-------------------|
| Sidebar | auth-store, UI store | User, active route | Route change, auth state |
| ChatMessageList | query-store | Messages of active conversation | New message, streaming update |
| ChatInput | query-store | Selected database, model | Active conversation change |
| SqlDisplay | Props | SQL string | New result |
| ResultTable | Props | Data array | New result, sort/filter change |
| DatabaseTree | React Query | GET /v1/schema/databases | Schema sync event |
| TableDetailPanel | React Query | GET /v1/schema/table/{id} | Table selection |
| HistoryList | React Query | GET /v1/history | Filter change, new query |
| NotificationBell | notification-store | Notifications | WS event |
| UserMenu | auth-store | User | Auth state |
| AdminCharts | React Query | GET /v1/admin/usage | Period change |
| CommandPalette | UI store | All routes, recent queries | Toggle, search input |

---

## 14. User Flows

### 14.1 Query Flow (Detailed)

```
+----------+    +----------+    +----------+    +----------+
|  User    |    |  Chat    |    |  Client  |    |  API     |
|          |    |  Input   |    |  Logic   |    |          |
+----+-----+    +----+-----+    +----+-----+    +----+-----+
     |               |               |               |
     | Type query    |               |               |
     +-------------->|               |               |
     |               |               |               |
     |               | Validate      |               |
     |               | (non-empty,   |               |
     |               |  length<1000) |               |
     |               |               |               |
     |               | If valid:     |               |
     |               +-------------->|               |
     |               |               |               |
     |               |               | Append user   |
     |               |               | message to    |
     |               |               | conversation  |
     |               |               | (optimistic)  |
     |               |               |               |
     |               |               | POST /v1/query|
     |               |               +-------------->|
     |               |               |               |
     |               |               | Return        |
     |               |               | { query_id }  |
     |               |               |<--------------+
     |               |               |               |
     |               |               | Open WS       |
     |               |               | subscription  |
     |               |               | for query_id  |
     |               |               |               |
     |               |               | Show loading  |
     |               |               | state         |
     |               |               |               |
     | Show user msg |               |               |
     |<--------------+---------------+               |
     |               |               |               |
     |               |               |  +-- WS Event -+
     |               |               |  |  stream    |
     | Show thinking |               |  | (chunks)   |
     |<--------------+---------------+<-+------------+
     |               |               |  |            |
     |               |               |  | (multiple) |
     |               |               |  |            |
     | Show SQL      |               |  | stream:sql |
     |<--------------+---------------+<-+------------+
     |               |               |  |            |
     | Show results  |               |  | WS Event   |
     |<--------------+---------------+<-+ completed  |
     |               |               |  +------------+
     |               |               |               |
     | Give feedback |               |               |
     | (thumbs)      |               |               |
     +--------------------------------+>              |
     |               |               |               |
     |               |               | POST          |
     |               |               | /v1/feedback  |
     |               |               +-------------->|
```

### 14.2 Schema Sync Flow

```
+----------+    +----------+    +----------+    +----------+
|  User    |    |  Schema  |    |  Client  |    |  API     |
|          |    |  Page    |    |  Logic   |    |          |
+----+-----+    +----+-----+    +----+-----+    +----+-----+
     |               |               |               |
     | Click "Sync"  |               |               |
     +-------------->|               |               |
     |               |               |               |
     |               | POST           |               |
     |               | /v1/schema/    |               |
     |               | sync           |               |
     |               +-------------->+-------------->|
     |               |               |               |
     |               |               | Show progress |
     |               |               | bar           |
     |               |<--------------+               |
     |               |               |               |
     |               |               |  +-- WS Event -+
     |               |               |  |  syncing   |
     | Update        |               |  | (progress) |
     | progress      |               |<-+------------+
     |<--------------+---------------+  |            |
     |               |               |  |            |
     |               |               |  | WS Event   |
     | Sync complete |               |  | synced     |
     | + toast       |               |<-+------------+
     |<--------------+---------------+  +------------+
     |               |               |               |
     | Auto-refresh  |               |               |
     | schema tree   |               |               |
```

### 14.3 Invite Flow

```
+----------+    +----------+    +----------+    +----------+
|  Admin   |    | Settings |    |  API     |    | Invitee  |
|          |    |  Page    |    |          |    |          |
+----+-----+    +----+-----+    +----+-----+    +----+-----+
     |               |               |               |
     | Enter email   |               |               |
     | + select role |               |               |
     +-------------->|               |               |
     |               |               |               |
     |               | POST           |               |
     |               | /v1/team/      |               |
     |               | invite         |               |
     |               +-------------->|               |
     |               |               |               |
     |               |               | Send invite   |
     |               |               | email         |
     |               |               +-------------->|
     |               |               |               |
     | Show pending  |               |               |
     |<--------------+---------------+               |
     |               |               |               |
     |               |               |               | Open link
     |               |               |               |<---------
     |               |               |               |
     |               |               | GET            |
     |               |               | /invite/       |
     |               |               | {token}        |
     |               |               |<--------------+
     |               |               |               |
     |               |               | Show accept   |
     |               |               | page           |
     |               |               +-------------->|
     |               |               |               |
     |               |               | POST           |
     |               |               | /invite/       |
     |               |               | {token}/accept |
     |               |               |<--------------+
     |               |               |               |
     |               |               | Redirect to   |
     |               |               | /dashboard     |
     |               |               +-------------->|
```

### 14.4 Error Recovery Flow

```
+----------+    +----------+    +----------+    +----------+
|  User    |    |  UI      |    |  Client  |    |  API     |
|          |    |          |    |  Logic   |    |          |
+----+-----+    +----+-----+    +----+-----+    +----+-----+
     |               |               |               |
     | Submit query  |               |               |
     +-------------->|               |               |
     |               +-------------->+-------------->|
     |               |               |               |
     |               |               |    500 Error  |
     |               |               |<--------------+
     |               |               |               |
     |               | Show toast:   |               |
     |               | "Something    |               |
     |               |  went wrong"  |               |
     |               |<--------------+               |
     |               |               |               |
     | Click "Retry" |               |               |
     +-------------->+-------------->+-------------->|
     |               |               |               |
     |               |               |    200 OK     |
     |               |               |<--------------+
     |               |               |               |
     | Show results  |               |               |
     |<--------------+---------------+               |
```

### 14.5 Cold Start / First Visit Flow

```
1. User arrives at /login
2. Login form shown (no registration option -- invite-only)
3. User enters credentials
4. On success, redirect to /dashboard/chat
5. Chat page shows welcome message:
   "Welcome! Ask your first question or explore your schema."
6. If no databases connected -> banner: "No databases connected."
7. Schema page shows empty state if no databases
8. History page shows "No queries yet. Start by asking a question."
```

---

## 15. Wireframes / Layout Specifications

### 15.1 Login Page

```
+-----------------------------------------------------------+
|                                                           |
|                                                           |
|                    +----------------+                      |
|                    |    Logo        |                      |
|                    +----------------+                      |
|                                                           |
|                    Sign in to SchemaIntern                    |
|                                                           |
|                    +------------------+                    |
|                    | Email            |                    |
|                    +------------------+                    |
|                    +------------------+                    |
|                    | Password         |                    |
|                    +------------------+                    |
|                                                           |
|                    [Sign In]                               |
|                                                           |
|                    --- or continue with ---                |
|                                                           |
|                    [Google] [Microsoft] [SSO]              |
|                                                           |
|                    Forgot password?                        |
|                                                           |
|                    Need help? Contact support              |
|                                                           |
+-----------------------------------------------------------+

- Centered card, max-width 400px
- Background: subtle gradient or illustration
- Dark mode: same layout, dark variant colors
- Error state: inline error above form
- Loading state: disabled button with spinner
- MFA challenge: replaces password field with code input
```

### 15.2 Chat Page

```
+--------------------------------------------------------------------+
| +--------+  +------------------------------------+----------------+ |
| |        |  |   Chat                Database V   | Notif Bell     | |
| |  Logo  |  |   +----------------------------+   |  Avatar V      | |
| |        |  |   | Search conversations...     |   |                | |
| +--------+  |   +----------------------------+   +----------------+ |
| | Chat   |  |   +----------------------------+   |                | |
| | >Chat 1|  |   |                            |   |  Related       | |
| | Chat 2 |  |   |  Welcome! Ask a query.     |   |  Queries       | |
| | Chat 3 |  |   |                            |   |                | |
| |        |  |   | +------------------------+ |   |  +----------+  | |
| +--------+  |   | | "Show revenue by...    | |   |  | Query1   |  | |
| |Schema  |  |   | +------------------------+ |   |  +----------+  | |
| |History |  |   |                            |   |  +----------+  | |
| |Settings|  |   | +------------------------+ |   |  | Query2   |  | |
| |        |  |   | | SELECT c.name,         | |   |  +----------+  | |
| +--------+  |   | | SUM(o.amount)          | |   |                | |
| |        |  |   | | FROM customers c ...   | |   |  Metadata      | |
| |User    |  |   | +------------------------+ |   |  Tokens: 45    | |
| | Menu   |  |   |                            |   |  Cost: $0.00   | |
| |        |  |   | +------------------------+ |   |  Time: 1.2s    | |
| +--------+  |   | | Name    | Revenue      | |   |                | |
|             |   | +---------+--------------+ |   +----------------+ |
|             |   | | Acme    | $1,234,567   | |                      |
|             |   | | Beta    | $987,654     | |                      |
|             |   | +------------------------+ |                      |
|             |   |                            |                      |
|             |   | +------------------------+ |                      |
|             |   | | Ask anything...        |[A]                     |
|             |   | | [Model: Auto V]        |[Send]                 |
|             |   | +------------------------+ |                      |
|             |   +----------------------------+                      |
|             +------------------------------------------------------+

Layout:
- Sidebar: 240px (collapsible to 64px icons)
- Main area: flex-1 (min content width)
- Right panel: 300px (collapsible)
- Chat input: bottom of main area, fixed on scroll
```

### 15.3 Schema Page

```
+--------------------------------------------------------------------+
| +--------+  +----------------------------------------------------+ |
| |        |  |  Schema Browser            [Sync Schema] [Search]   | |
| | Sidebar|  |  +---------------+  +----------------------------+ | |
| |        |  |  | Database V    |  | Table: customers           | | |
| |        |  |  |               |  | Description: Customer      | | |
| |        |  |  | > my_db       |  | records with contact info  | | |
| |        |  |  |   +>public    |  +----------------------------+ | |
| |        |  |  |   | +>cust    |  Columns (12)                   | |
| |        |  |  |   | | + id    |  +------+------+---+--------+  | |
| |        |  |  |   | | + na    |  |Name  | Type |Key| Desc   |  | |
| |        |  |  |   | | + em    |  +------+------+---+--------+  | |
| |        |  |  |   | | + cr    |  |id    | UUID |PK |        |  | |
| |        |  |  |   | | + ph    |  |name  | text |   |        |  | |
| |        |  |  |   | +>orders  |  |email | text |   |        |  | |
| |        |  |  |   | +>invent  |  +------+------+---+--------+  | |
| |        |  |  |   +>analytics |                                 | |
| |        |  |  |               |  Relationships (2)              | |
| |        |  |  |               |  + orders.customer_id -> cust..| | |
| |        |  |  |               |                                 | |
| |        |  |  |               |  Sample Data (top 20)           | |
| |        |  |  |               |  +------+--------+-----------+  | |
| |        |  |  |               |  | id   | name   | email     |  | |
| |        |  |  |               |  +------+--------+-----------+  | |
| |        |  |  |               |  | 1    | Acme   | acme@...  |  | |
| |        |  |  |               |  +------+--------+-----------+  | |
| +--------+  |  +---------------+                                  | |
|             +----------------------------------------------------+ |
+--------------------------------------------------------------------+
```

### 15.4 History Page

```
+--------------------------------------------------------------------+
| +--------+  +----------------------------------------------------+ |
| |        |  |  Query History                                      | |
| | Sidebar|  |  +----------------------------------------------+ | |
| |        |  |  | [Date Range V] [Status V] [DB V] [Search...] | | |
| |        |  |  +----------------------------------------------+ | |
| |        |  |                                                    | |
| |        |  |  +----------------------------------------------+ | |
| |        |  |  | > "Show revenue by customer for 2024"         | | |
| |        |  |  |   V Completed - my_db - 2m ago - $0.01       | | |
| |        |  |  |   [View] [Share] [Delete]                    | | |
| |        |  |  +----------------------------------------------+ | |
| |        |  |  | > "How many orders shipped late?"             | | |
| |        |  |  |   X Error - my_db - 15m ago - $0.00          | | |
| |        |  |  |   [View] [Retry] [Delete]                    | | |
| |        |  |  +----------------------------------------------+ | |
| |        |  |  | > "List top 10 products by revenue"           | | |
| |        |  |  |   V Completed - my_db - 1h ago - $0.02       | | |
| |        |  |  |   [View] [Share] [Delete]                    | | |
| |        |  |  +----------------------------------------------+ | |
| |        |  |                                                    | |
| |        |  |  [<- Prev]  Page 1 of 24  [Next ->]               | |
| +--------+  +----------------------------------------------------+ |
+--------------------------------------------------------------------+
```

### 15.5 Settings Page

```
+--------------------------------------------------------------------+
| +--------+  +----------------------------------------------------+ |
| |        |  |  Settings                                    [Save]| |
| | Sidebar|  |  +------+---------------------------------------+ | |
| |        |  |  |Profile|  +---------------------------------+ | | |
| |        |  |  |Team   |  | Name: [_______________]        | | | |
| |        |  |  |Databas|  | Email: user@company.com        | | | |
| |        |  |  |Billing|  | Timezone: [V America/New_York] | | | |
| |        |  |  |       |  | Language: [V English]          | | | |
| |        |  |  |       |  |                                 | | | |
| |        |  |  |       |  | Theme:                          | | | |
| |        |  |  |       |  | O System  * Dark  O Light       | | | |
| |        |  |  |       |  +---------------------------------+ | | |
| |        |  |  +------+---------------------------------------+ | |
| +--------+  +----------------------------------------------------+ |
+--------------------------------------------------------------------+
```

### 15.6 Admin Page

```
+--------------------------------------------------------------------+
| +--------+  +----------------------------------------------------+ |
| |        |  |  Admin Dashboard        [Period: 7d V]            | |
| | Sidebar|  |  +------+ +------+ +------+ +------+              | |
| |        |  |  |Q:1.2K| |Users | |Latency| |Cost  |             | |
| | Admin  |  |  |+ 12% | | 45   | |1.2s  | |$45.20|             | |
| | >Overvi|  |  +------+ +------+ +------+ +------+              | |
| | Teams  |  |                                                    | |
| |Billing |  |  +----------------------------------------------+ | |
| | Logs   |  |  |  Queries Over Time                           | | |
| |        |  |  |  _-_--__--__--__--__--__ (chart)            | | |
| |        |  |  +----------------------------------------------+ | |
| |        |  |                                                    | |
| |        |  |  +----------------------------------------------+ | |
| |        |  |  |  Error Rate: 2.1%   |   99.9% uptime         | | |
| |        |  |  +----------------------------------------------+ | |
| +--------+  +----------------------------------------------------+ |
+--------------------------------------------------------------------+
```

---

## 16. Permissions & RBAC (UI Enforcement)

### 16.1 Role Definitions

| Role | Description | UI Visibility |
|------|-------------|--------------|
| admin | Full access, billing, team management | All UI elements visible |
| member | Can query, view schema, history, manage own settings | Admin nav hidden, limited settings |
| viewer | Read-only: can only query and view results via shared links | No settings, no schema editing |

### 16.2 Permission Matrix

| Action | admin | member | viewer |
|--------|-------|--------|--------|
| Access chat | Y | Y | Y |
| Access schema browser | Y | Y | Y (read-only) |
| Access history | Y | Y | Y (own only) |
| Access settings | Y | Y (limited) | N |
| Manage databases | Y | Y | N |
| Invite team members | Y | N | N |
| Manage billing | Y | N | N |
| View admin dashboard | Y | N | N |
| Delete queries from history | Y | Y (own) | N |
| Share query results | Y | Y | Y (public only) |

### 16.3 UI Enforcement Points

```
lib/permissions.ts

type Permission =
  | 'view_admin'
  | 'manage_team'
  | 'manage_databases'
  | 'view_billing'
  | 'manage_billing'
  | 'invite_members'
  | 'delete_own_history'
  | 'delete_any_history'
  | 'manage_settings'
  | 'view_settings';

const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  admin: ['view_admin', 'manage_team', 'manage_databases', 'view_billing',
          'manage_billing', 'invite_members', 'delete_own_history',
          'delete_any_history', 'manage_settings', 'view_settings'],
  member: ['manage_databases', 'view_billing', 'delete_own_history',
           'manage_settings', 'view_settings'],
  viewer: [],
};

export function usePermission() {
  const user = useAuthStore((s) => s.user);
  const permissions = user ? ROLE_PERMISSIONS[user.role] : [];

  function can(permission: Permission): boolean {
    return permissions.includes(permission);
  }

  return { can, permissions };
}
```

```
// Usage in components
function AdminNavItems() {
  const { can } = usePermission();
  if (!can('view_admin')) return null;
  return <NavItem icon={Shield} label="Admin" href="/dashboard/admin" />;
}
```

### 16.4 Server-Side Enforcement

Client-side permission checks are for UX only (hiding UI elements). All API calls enforce permissions server-side. If a user without view_admin accesses /dashboard/admin, the page makes an API call that returns 403, and the client shows an "Access denied" page.

```
// app/dashboard/admin/page.tsx (Server Component)
import { redirect } from 'next/navigation';
import { getServerSession } from '@/lib/auth-server';

export default async function AdminPage() {
  const session = await getServerSession();
  if (!session || session.user.role !== 'admin') {
    redirect('/dashboard');
  }
  return <AdminDashboard />;
}
```

---

## 17. Error Handling

### 17.1 Error Boundary Hierarchy

```
<GlobalErrorBoundary>           # Root level -- catches unhandled errors
+-- <AppErrorBoundary>          # App layout level
    +-- <ChatErrorBoundary>     # Chat page errors
    +-- <SchemaErrorBoundary>   # Schema page errors
    +-- <HistoryErrorBoundary>  # History page errors
    +-- <SettingsErrorBoundary> # Settings page errors
```

### 17.2 Error Boundary Component

```
components/ErrorBoundary.tsx

interface ErrorBoundaryProps {
  fallback?: React.ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
  children: React.ReactNode;
}

Renders:
- Production: "Something went wrong" + "Try again" button + "Contact support" link
- Development: Error stack trace + component stack
- Logs error to observability (POST /v1/logs/error)
- Resets when route changes
```

### 17.3 API Error Mapping

| HTTP Status | API Error Code | UI Treatment | User Message |
|------------|---------------|-------------|--------------|
| 400 | invalid_query | Inline error in chat | "That doesn't look like a valid question. Try rephrasing." |
| 400 | validation_error | Inline error on form field | Specific field error message |
| 401 | unauthenticated | Redirect to /login | "Your session expired. Please sign in again." |
| 403 | forbidden | Toast + redirect | "You don't have permission to do that." |
| 404 | not_found | Toast or 404 page | "This doesn't exist anymore." |
| 409 | conflict | Toast | "This was just updated. Please refresh and try again." |
| 422 | policy_blocked | Inline error in chat | "This query was blocked: {reason}. [View details]" |
| 429 | rate_limited | Inline timer | "Too many requests. Try again in {X} seconds." |
| 500 | internal_error | Toast + auto-retry (x3) | "Something went wrong on our end." |
| 502 | upstream_error | Toast + retry button | "The database is temporarily unavailable." |
| 503 | service_unavailable | Banner | "We're undergoing maintenance." |
| -- | network_error | Banner | "No internet connection. Retrying automatically..." |

### 17.4 Error Recovery Actions

| Error | Automatic Recovery | Manual Recovery |
|-------|-------------------|-----------------|
| 401 Token expired | Silent refresh (POST /v1/auth/refresh) | -- |
| 429 Rate limited | Backoff (exponential, max 30s) | Retry button after cooldown |
| 500 Server error | Retry x3 with 1s/2s/4s delay | "Try again" button |
| 502/503 Downstream | Retry x5 with 2s/4s/8s/16s/30s | "Check back later" link |
| Network offline | Auto-reconnect on online event | Manual "Retry" button |
| WS disconnect | Auto-reconnect (exponential backoff, max 10 attempts) | "Reconnect" button |

### 17.5 Network Status Detection

```
lib/network-status.ts

import { useEffect, useState } from 'react';

export function useNetworkStatus() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Also check via periodic fetch (for corporate proxies that swallow offline)
    const interval = setInterval(async () => {
      try {
        const controller = new AbortController();
        setTimeout(() => controller.abort(), 3000);
        await fetch('/api/health', {
          method: 'HEAD',
          signal: controller.signal,
          cache: 'no-store'
        });
        setIsOnline(true);
      } catch {
        setIsOnline(false);
      }
    }, 30_000);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      clearInterval(interval);
    };
  }, []);

  return isOnline;
}
```

---

## 18. Loading States

### 18.1 Loading State Matrix

| Page/Component | Initial Load | Action | Skeleton Type | Duration Target |
|---------------|-------------|--------|--------------|-----------------|
| Chat page | Conversation list | Page mount | List skeleton (5 items) | <500ms |
| Chat page | Messages | Select conversation | Message skeleton (3 items) | <1s |
| Chat stream | Response | Submit query | Streaming indicator | N/A (streaming) |
| Schema page | Database list | Page mount | List skeleton (8 items) | <1s |
| Schema page | Table detail | Click table | Card skeleton | <800ms |
| History page | History list | Page mount | Table skeleton (10 rows) | <800ms |
| History page | History detail | Click item | Card skeleton | <600ms |
| Settings | Form data | Page mount | Form skeleton (4 fields) | <500ms |
| Admin | Metrics | Page mount | Metric card skeleton (4) + chart skeleton | <1.5s |
| Result table | Query results | Submit query | Table skeleton (5 rows, 3 cols) | <1s |

### 18.2 Skeleton Variants

```
components/ui/skeleton.tsx

interface SkeletonProps {
  variant: 'text' | 'card' | 'table-row' | 'table-cell' | 'avatar' | 'chart' | 'metric';
  width?: string;
  height?: string;
  lines?: number;
  className?: string;
}
```

| Variant | Default Dimensions | Animation |
|---------|------------------|-----------|
| text | 100% x 1em | Shimmer (left to right) |
| card | 100% x 120px | Shimmer |
| table-row | 100% x 40px | Shimmer (staggered) |
| table-cell | 80px x 40px | Shimmer |
| avatar | 40x40px (circle) | Shimmer |
| chart | 100% x 200px | Shimmer with wave pattern |
| metric | 200px x 100px | Shimmer |

### 18.3 Loading State Patterns

```
// Pattern: Content with loading, error, empty states
function ChatMessageList({ conversationId }: { conversationId: string }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['conversation', conversationId],
    queryFn: () => api.getConversation(conversationId),
  });

  if (isLoading) return <MessageListSkeleton count={5} />;
  if (isError) return <ErrorMessage error={error} onRetry={() => refetch()} />;
  if (!data.messages.length) return <EmptyState type="chat" />;

  return <MessageList messages={data.messages} />;
}
```

### 18.4 Progressive Loading

For the admin dashboard with multiple charts:

```
// Load critical metrics first, charts second, tables third
function AdminDashboard() {
  return (
    <div>
      {/* Priority 1: Metrics (fast query) */}
      <Suspense fallback={<MetricsGridSkeleton />}>
        <MetricsGrid />
      </Suspense>

      {/* Priority 2: Charts (medium query) */}
      <Suspense fallback={<ChartsSkeleton />}>
        <Charts />
      </Suspense>

      {/* Priority 3: Tables (slow query, paginated) */}
      <Suspense fallback={<TableSkeleton />}>
        <DataTables />
      </Suspense>
    </div>
  );
}
```

### 18.5 Streaming Indicator (Chat)

```
+----------------------------------------+
|  Assistant is thinking...              |
|  +----------------------------------+  |
|  | ...........................      |  |
|  | Thinking through the schema...   |  |
|  +----------------------------------+  |
|                                        |
|  +----------------------------------+  |
|  | SELECT c.name,                  |  |
|  | _                               |  |  <- Blinking cursor
|  +----------------------------------+  |
|                                        |
|  .............____--------##########   |  <- Progress bar
|                                        |
|  [Cancel Query]                        |
+----------------------------------------+

- Thinking phase: animated dots "Thinking..."
- SQL generation: typewriter effect (char by char)
- Result loading: determinate progress bar (polls status)
- Cancel: AbortController signal
```

---

## 19. Empty States

### 19.1 Empty State Specifications

| Page/Location | Empty Condition | Illustration | Heading | Description | CTA |
|--------------|----------------|-------------|---------|-------------|-----|
| Chat page | No conversations | Chat bubble | "Start a conversation" | "Ask your first question about your database." | "Ask a question" |
| Chat page | No messages | Empty chat | "How can I help?" | "Ask a natural language question about your data." | (Input focused) |
| Schema page | No databases | Database | "No databases connected" | "Connect your first database to explore its schema." | "Connect Database" |
| Schema page | No tables | Table | "No tables found" | "This database appears to have no tables." | "Sync Schema" |
| History page | No queries | Clock | "No query history" | "Your past queries will appear here." | "Ask a question" |
| History page | No filter results | Filter | "No matches" | "Try adjusting your search filters." | "Clear Filters" |
| Settings > Team | No members | People | "Your team is empty" | "Invite team members to collaborate." | "Invite Members" |
| Settings > Databases | No databases | Database | "No databases connected" | "Connect your database to start querying." | "Add Database" |
| Admin > Teams | No teams | Building | "No teams yet" | "Teams will appear once users sign up." | -- |
| Admin > Logs | No logs | Document | "No logs found" | "Try adjusting the date range or filters." | "Clear Filters" |
| Notifications | None | Bell | "All caught up" | "Notifications will appear here." | -- |
| Search results | No results | Search | "No results found" | "Try a different search term." | "Clear Search" |

### 19.2 Empty State Component

```
components/EmptyState.tsx

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  action?: {
    label: string;
    onClick: () => void;
    variant?: 'primary' | 'secondary';
  };
  size?: 'sm' | 'md' | 'lg';
}

Renders:
- Centered container with illustration
- Heading (h2 or h3)
- Description text
- Optional CTA button
- Size controls padding and icon size
```

---

## 20. Future Extensibility

### 20.1 Plugin / Integration System

```
/dashboard/integrations          # Future: Integration marketplace
/dashboard/automations           # Future: Scheduled queries
/dashboard/alerts                # Future: Query result alerts
/dashboard/reports               # Future: Scheduled reports
/dashboard/insights              # Future: Proactive insights
```

### 20.2 Feature Flag Strategy

```
lib/feature-flags.ts

const FEATURE_FLAGS = {
  SCHEDULED_QUERIES: false,      // Phase 3 (Year 2)
  PROACTIVE_INSIGHTS: false,     // Phase 4 (Year 3)
  AUTONOMOUS_WORKFLOWS: false,   // Phase 5 (Year 4)
  INTEGRATION_MARKETPLACE: false,// Phase 2 (Year 2)
  EXPORT_DASHBOARDS: false,      // Phase 3 (Year 2)
  NATIVE_CHARTS: false,          // Phase 2 (Year 2)
};

Feature flags controlled by:
1. Environment variable (per-deployment)
2. Backend setting (per-tenant, admin-toggleable)
3. Launch darkly / similar (future)
```

### 20.3 Extensible Route Structure

```
/dashboard/
+-- chat/              # Core -- always present
+-- schema/            # Core -- always present
+-- history/           # Core -- always present
+-- settings/          # Core -- always present
+-- admin/             # Core -- always present
|
+-- integrations/      # Flag-gated: Year 2
+-- automations/       # Flag-gated: Year 2
+-- alerts/            # Flag-gated: Year 3
+-- reports/           # Flag-gated: Year 3
+-- insights/          # Flag-gated: Year 4
+-- workflows/         # Flag-gated: Year 5
```

### 20.4 Design System Extensibility

- All design tokens defined as CSS custom properties (easy to override)
- shadcn/ui components are locally editable copies (not npm dependency)
- New components follow the same pattern: components/ui/{name}.tsx
- Theme extensions via CSS variable overrides (white-label support for enterprise customers)
- Component variants extend via cva() (class-variance-authority)

### 20.5 Micro-Frontend Boundary

If the app grows large enough, the admin panel can be split into a separate micro-frontend:

```
/ (main app)          -> Chat, Schema, History, Settings
/admin/*              -> Separate Next.js app, same design tokens
```

Shared via:
- NPM package: @opencode/ui (shared components)
- NPM package: @opencode/tokens (design tokens)
- NPM package: @opencode/api-client (typed API client)
- NPM package: @opencode/stores (Zustand stores)

---

## 21. Implementation Guidelines

### 21.1 Directory Structure

```
frontend/
+-- public/
|   +-- locales/              # i18n JSON files
|   |   +-- en-US/
|   |   +-- ja-JP/
|   |   +-- zh-CN/
|   +-- icons/                # SVG icons
|   +-- images/               # Static images
|   +-- manifest.json
|
+-- src/
|   +-- app/                  # Next.js App Router pages
|   |   +-- (auth)/           # Auth route group
|   |   |   +-- login/
|   |   |   +-- logout/
|   |   |   +-- invite/
|   |   |       +-- [token]/
|   |   +-- (dashboard)/      # Dashboard route group
|   |   |   +-- dashboard/
|   |   |   |   +-- chat/
|   |   |   |   +-- schema/
|   |   |   |   +-- history/
|   |   |   |   +-- settings/
|   |   |   |   +-- admin/
|   |   |   +-- layout.tsx
|   |   +-- not-found.tsx
|   |   +-- error.tsx
|   |   +-- global-error.tsx
|   |   +-- layout.tsx        # Root layout
|   |
|   +-- components/
|   |   +-- ui/               # shadcn/ui + custom primitives
|   |   |   +-- button.tsx
|   |   |   +-- input.tsx
|   |   |   +-- skeleton.tsx
|   |   |   +-- ...
|   |   +-- layout/           # Layout components
|   |   |   +-- sidebar.tsx
|   |   |   +-- topbar.tsx
|   |   |   +-- app-layout.tsx
|   |   |   +-- ...
|   |   +-- chat/             # Chat-specific components
|   |   |   +-- chat-input.tsx
|   |   |   +-- chat-message-list.tsx
|   |   |   +-- assistant-message.tsx
|   |   |   +-- user-message.tsx
|   |   |   +-- sql-display.tsx
|   |   |   +-- result-table.tsx
|   |   |   +-- ...
|   |   +-- schema/           # Schema-specific components
|   |   +-- history/          # History-specific components
|   |   +-- settings/         # Settings-specific components
|   |   +-- admin/            # Admin-specific components
|   |   +-- shared/           # Shared components
|   |   |   +-- empty-state.tsx
|   |   |   +-- error-boundary.tsx
|   |   |   +-- command-palette.tsx
|   |   |   +-- notification-bell.tsx
|   |   |   +-- ...
|   |   +-- providers/        # React context providers
|   |       +-- theme-provider.tsx
|   |       +-- query-provider.tsx
|   |       +-- auth-gate.tsx
|   |
|   +-- stores/               # Zustand stores
|   |   +-- auth-store.ts
|   |   +-- ui-store.ts
|   |   +-- query-store.ts
|   |   +-- settings-store.ts
|   |   +-- schema-cache-store.ts
|   |   +-- notification-store.ts
|   |   +-- toast-store.ts
|   |
|   +-- lib/                  # Utilities and libraries
|   |   +-- api-client.ts     # OpenAPI typed client
|   |   +-- websocket.ts      # WebSocket manager
|   |   +-- permissions.ts    # RBAC utilities
|   |   +-- format.ts         # Number/date formatting
|   |   +-- i18n.ts           # i18n configuration
|   |   +-- network-status.ts # Online/offline detection
|   |   +-- feature-flags.ts
|   |   +-- utils.ts          # General utilities
|   |
|   +-- hooks/                # Custom React hooks
|   |   +-- use-query.ts      # React Query hooks
|   |   +-- use-websocket.ts
|   |   +-- use-permission.ts
|   |   +-- use-format.ts
|   |   +-- use-network-status.ts
|   |   +-- use-debounce.ts
|   |
|   +-- types/                # TypeScript type definitions
|   |   +-- api.ts            # Generated from openapi-typescript
|   |   +-- chat.ts
|   |   +-- schema.ts
|   |   +-- ...
|   |
|   +-- styles/               # Global styles
|       +-- globals.css       # Tailwind imports + design tokens
|       +-- fonts.css         # Font-face declarations
|
+-- tests/
|   +-- unit/                 # Vitest unit tests
|   +-- integration/          # Component integration tests
|   +-- e2e/                  # Playwright E2E tests
|
+-- service-worker.ts         # Workbox service worker
+-- next.config.ts
+-- tailwind.config.ts
+-- tsconfig.json
+-- vitest.config.ts
+-- playwright.config.ts
+-- package.json
```

### 21.2 Naming Conventions

| Entity | Convention | Example |
|--------|-----------|---------|
| Pages | PascalCase + Page suffix | ChatPage.tsx |
| Components | PascalCase | ChatMessageList.tsx |
| Stores | kebab-case + -store suffix | auth-store.ts |
| Hooks | camelCase + use prefix | usePermission.ts |
| Lib files | kebab-case | api-client.ts |
| Types | PascalCase | Conversation |
| CSS classes | Tailwind utility classes | (no custom CSS except design tokens) |
| File names | kebab-case | sql-display.tsx |
| Test files | {name}.test.tsx | chat-input.test.tsx |

### 21.3 Import Order

```
// 1. React/Next.js
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

// 2. Third-party libraries
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

// 3. Stores
import { useAuthStore } from '@/stores/auth-store';

// 4. Components
import { Button } from '@/components/ui/button';
import { ChatMessageList } from '@/components/chat/chat-message-list';

// 5. Hooks
import { usePermission } from '@/hooks/use-permission';

// 6. Utilities
import { formatDate } from '@/lib/format';

// 7. Types
import type { Conversation } from '@/types/chat';

// 8. Styles
import '@/styles/globals.css';
```

### 21.4 Linting & Formatting

| Tool | Configuration |
|------|--------------|
| ESLint | Next.js base config + @typescript-eslint strict |
| Prettier | 100 char width, single quotes, trailing commas |
| Husky | pre-commit: lint-staged (eslint --fix + prettier --write) |
| lint-staged | *.{ts,tsx}: eslint --fix, *.{json,md}: prettier --write |

### 21.5 Development Workflow

```
# Development
npm run dev              # Next.js dev server on :3000
npm run dev:mock         # Dev with MSW (mock API)
npm run typecheck        # tsc --noEmit
npm run lint             # ESLint
npm run format           # Prettier

# Testing
npm run test             # Vitest (unit + integration)
npm run test:watch       # Watch mode
npm run test:e2e         # Playwright (requires dev server + API)
npm run test:e2e:ui      # Playwright UI mode

# Building
npm run build            # Production build
npm run build:static     # Static export for air-gapped
npm run analyze          # Bundle analyzer
```

---

## 22. Testing Strategy

### 22.1 Test Pyramid

```
        /\
       /  \            E2E (Playwright)
      /    \           5-10 critical user journeys
     /------\
    /        \         Integration (Vitest + Testing Library)
   /          \        40-60 component + hook tests
  /------------\
 /              \      Unit (Vitest)
/                \    100-200 store + utility tests
/------------------\
```

### 22.2 Unit Tests (Vitest)

| Target | Coverage | Key Tests |
|--------|----------|-----------|
| Zustand stores | 90%+ | State initialization, action dispatching, edge cases (empty, error) |
| Utility functions | 95%+ | Format functions, permission checks, validation |
| Hooks | 90%+ | Mock store states, verify derived values |
| Types | 100% | Zod schema validation |

```
// tests/unit/stores/auth-store.test.ts
describe('AuthStore', () => {
  beforeEach(() => {
    useAuthStore.setState(initialState);
  });

  it('should initialize with unauthenticated state', () => {
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
  });

  it('should set user on login', async () => {
    const store = useAuthStore.getState();
    mockApi.post('/v1/auth/login').resolve({ user: mockUser });

    await store.login('test@example.com', 'password');

    const newState = useAuthStore.getState();
    expect(newState.isAuthenticated).toBe(true);
    expect(newState.user?.email).toBe('test@example.com');
  });

  it('should handle login failure', async () => {
    const store = useAuthStore.getState();
    mockApi.post('/v1/auth/login').reject(new ApiError(401, 'Invalid credentials'));

    await expect(store.login('bad@example.com', 'wrong')).rejects.toThrow();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });
});
```

### 22.3 Integration Tests (Vitest + Testing Library)

| Target | Coverage | Key Tests |
|--------|----------|-----------|
| Chat input + message flow | 85%+ | Submit query, show user message, streaming response |
| Schema tree + detail panel | 85%+ | Expand table, show detail, loading/error states |
| History list + filters | 85%+ | Filter by status, paginate, empty state |
| Settings forms | 85%+ | Fill form, validate, submit, error display |
| Admin dashboard | 80%+ | Load metrics, show charts, period change |
| Auth flow components | 90%+ | Login form, MFA challenge, error display |
| Error boundaries | 90%+ | Catch error, show fallback, retry action |

```
// tests/integration/chat-input.test.tsx
describe('ChatInput', () => {
  it('should submit query on Enter', async () => {
    render(<ChatInput />);

    const input = screen.getByPlaceholderText('Ask anything...');
    await userEvent.type(input, 'Show revenue by customer{Enter}');

    expect(screen.getByText('Show revenue by customer')).toBeInTheDocument();
    expect(mockApi.post).toHaveBeenCalledWith('/v1/query', {
      query: 'Show revenue by customer',
      database_id: expect.any(String),
    });
  });

  it('should show loading state while waiting for response', async () => {
    render(<ChatInput />);

    const input = screen.getByPlaceholderText('Ask anything...');
    await userEvent.type(input, 'Test query{Enter}');

    expect(screen.getByTestId('streaming-indicator')).toBeInTheDocument();
    expect(screen.getByText('Cancel')).toBeInTheDocument();
  });

  it('should show policy enforcement error when query is blocked', async () => {
    mockApi.post('/v1/query').reject({
      status: 422,
      error: { code: 'policy_blocked', reason: 'Query accesses blocked table' }
    });

    render(<ChatInput />);
    const input = screen.getByPlaceholderText('Ask anything...');
    await userEvent.type(input, 'Show salaries{Enter}');

    expect(screen.getByText(/blocked/)).toBeInTheDocument();
    expect(screen.getByText('View policy details')).toBeInTheDocument();
  });
});
```

### 22.4 E2E Tests (Playwright)

| User Journey | Test Count | Critical |
|-------------|-----------|----------|
| Login -> Chat -> Query -> See results | 3 | Critical |
| Login -> Schema -> Browse -> Expand table | 2 | Critical |
| Login -> History -> Filter -> View detail | 2 | Critical |
| Login -> Settings -> Add database -> Test | 2 | High |
| Login -> Admin -> View metrics | 1 | High |
| Login -> Settings -> Invite team member | 1 | Medium |
| Full auth flow (login -> MFA -> token refresh -> logout) | 2 | Critical |
| Error states (network offline, 500 error, rate limited) | 3 | High |
| Responsive (mobile nav, tablet layout) | 2 | Medium |
| Dark mode toggle persistence | 1 | Low |
| Keyboard navigation (Tab, Enter, Escape, Cmd+K) | 2 | Medium |

```
// tests/e2e/chat-flow.spec.ts
test('user can ask a question and see results', async ({ page }) => {
  await page.goto('/login');
  await page.fill('[name="email"]', 'user@company.com');
  await page.fill('[name="password"]', 'password');
  await page.click('button:has-text("Sign In")');

  await expect(page).toHaveURL('/dashboard/chat');

  await page.fill('[placeholder="Ask anything..."]', 'Show me top 10 customers by revenue');
  await page.press('[placeholder="Ask anything..."]', 'Enter');

  // Wait for SQL to appear
  await expect(page.locator('.sql-display')).toBeVisible({ timeout: 15000 });

  // Wait for results
  await expect(page.locator('.result-table')).toBeVisible({ timeout: 30000 });

  // Verify table has data
  const rows = await page.locator('.result-table tbody tr').count();
  expect(rows).toBeGreaterThan(0);
});

test('policy enforcement blocks dangerous query', async ({ page }) => {
  await login(page);

  await page.fill('[placeholder="Ask anything..."]', 'Show me all customer passwords');
  await page.press('[placeholder="Ask anything..."]', 'Enter');

  await expect(page.locator('.policy-error')).toBeVisible();
  await expect(page.locator('.policy-error')).toContainText('blocked');
});
```

### 22.5 Visual Regression Testing

```
// tests/visual/chat-page.spec.ts
test('chat page matches snapshot', async ({ page }) => {
  await login(page);
  await page.goto('/dashboard/chat');
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('chat-page.png', {
    maxDiffPixels: 100,
    threshold: 0.1,
  });
});

test('dark mode chat page', async ({ page }) => {
  await login(page);
  await page.goto('/dashboard/chat');
  await page.evaluate(() => document.documentElement.classList.add('dark'));

  await expect(page).toHaveScreenshot('chat-page-dark.png', {
    maxDiffPixels: 100,
    threshold: 0.1,
  });
});
```

### 22.6 Testing Tools Configuration

```
// vitest.config.ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/unit/**/*.test.ts', 'tests/unit/**/*.test.tsx'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/types/**', 'src/app/**', '*.config.*'],
      thresholds: {
        statements: 80,
        branches: 75,
        functions: 80,
        lines: 80,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
```

```
// tests/setup.ts
import '@testing-library/jest-dom';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

// Mock Zustand stores
vi.mock('@/stores/auth-store');
vi.mock('@/stores/query-store');

// Mock WebSocket
vi.mock('@/lib/websocket', () => ({
  wsManager: {
    subscribe: vi.fn(),
    send: vi.fn(),
    disconnect: vi.fn(),
    connect: vi.fn(),
  },
}));

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
  }),
  usePathname: () => '/dashboard/chat',
  useSearchParams: () => new URLSearchParams(),
}));

afterEach(() => {
  cleanup();
});
```

### 22.7 Accessibility Testing

```
// tests/a11y/chat-page.a11y.test.ts
import { test, expect } from '@playwright/test';

test('chat page has no detectable accessibility violations', async ({ page }) => {
  await login(page);
  await page.goto('/dashboard/chat');
  await page.waitForLoadState('networkidle');

  // Run axe-core checks
  const results = await page.evaluate(async () => {
    const axe = await import('@axe-core/playwright');
    return await axe.default.run();
  });

  expect(results.violations).toHaveLength(0);
});
```

### 22.8 Performance Testing

```
// tests/performance/chat-load.spec.ts
test('chat page loads within budget', async ({ page }) => {
  await page.goto('/dashboard/chat', { waitUntil: 'commit' });

  // Use Performance API
  const ttfb = await page.evaluate(() =>
    performance.getEntriesByType('navigation')[0].responseStart
  );
  const fcp = await page.evaluate(() =>
    performance.getEntriesByType('paint')
      .find(e => e.name === 'first-contentful-paint')?.startTime ?? 0
  );

  expect(ttfb).toBeLessThan(1500); // 1.5s TTFB
  expect(fcp).toBeLessThan(2500);  // 2.5s FCP
});
```

### 22.9 Test Data Strategy

| Data Type | Source | Reset Strategy |
|-----------|--------|---------------|
| Mock API responses | MSW handlers in tests/mocks/ | Reset between tests |
| Zustand store state | Direct setState() | Reset in beforeEach |
| Auth tokens | Mock JWT strings | Reset between tests |
| Database schemas | MSW fixtures | Immutable fixtures |
| Query history | MSW paginated responses | Reset between test suites |
| Admin metrics | MSW chart data | Reset between tests |
| WebSocket events | Manual dispatch via wsManager.mock | Reset in afterEach |
| Browser storage | vi.stubGlobal / cleanup | Clear between tests |

---

