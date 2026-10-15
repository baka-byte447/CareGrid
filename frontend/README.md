# CareGrid — Frontend Client

A responsive, clinical-grade Command Center and Hospital Resource Allocation dashboard built with **React**, **Vite**, **Vanilla CSS Design System**, **Lucide Icons**, and **Recharts**.

Connects directly to the CareGrid FastAPI backend at `http://localhost:8000`.

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd frontend
npm install
```

### 2. Start the Development Server
```bash
npm run dev
```
The app will run locally at:
👉 **`http://localhost:5173`**

*(Requests to `/api/*` or direct paths like `/metrics`, `/beds`, `/patients`, `/allocation`, `/staff`, `/equipment`, `/audit` are automatically proxied to `http://localhost:8000` via `vite.config.js`)*

### 3. Production Build
```bash
npm run build
npm run preview
```

---

## 🏛️ Project Architecture

```
frontend/
├── index.html                  # HTML5 shell with Google Inter font
├── vite.config.js              # Vite config with backend API reverse proxy
├── package.json                # Dependencies: react, react-router-dom, recharts, lucide-react
└── src/
    ├── main.jsx                # React root and BrowserRouter mounting
    ├── App.jsx                 # App shell, persistent Sidebar & Route outlets
    ├── index.css               # Clinical Dark/Light CSS design tokens and micro-interactions
    │
    ├── services/
    │   └── api.js              # Centralized API service layer mapping all 9 FastAPI endpoints
    │
    ├── components/
    │   ├── Sidebar.jsx         # Sticky navigation with live route highlighting
    │   ├── MetricCard.jsx      # Reusable KPI stat card with trend badges
    │   ├── BedGrid.jsx         # Ward-by-ward bed visualizer with status & isolation indicators
    │   └── AllocationModal.jsx # Human-in-the-loop recommendation review & approval dialog
    │
    └── pages/
        ├── DashboardPage.jsx   # Executive overview: KPIs, bed occupancy charts, acuity distribution
        ├── WardsPage.jsx       # Real-time 100-bed grid categorized by ward type
        ├── PatientsPage.jsx    # Triage patient queue, acuity badges, and allocation trigger
        └── AuditPage.jsx       # Audit log history, staff workload gauges, and equipment status
```

---

## 🔌 API Endpoints Consumed

| Page / Component | FastAPI Route | Method | Purpose |
|------------------|---------------|--------|---------|
| **Dashboard** | `/metrics` | `GET` | Total beds, occupancy rate, waiting queue count, ICU ventilator utilization |
| **Dashboard** | `/beds` | `GET` | Bed distribution by ward for visualization charts |
| **Dashboard** | `/patients` | `GET` | Patient triage breakdown across Acuity levels 1–5 |
| **Wards** | `/beds` | `GET` | Live status (AVAILABLE / OCCUPIED / CLEANING) for all 100 beds |
| **Patients** | `/patients` | `GET` | Waiting queue list with acuity, isolation, and equipment requirements |
| **Allocation** | `/allocation/recommend` | `POST` | AI/RL recommendation engine suggests optimal bed assignment |
| **Allocation** | `/allocation/approve` | `POST` | Approves assignment with atomic row-locking to prevent race conditions |
| **Audit** | `/audit` | `GET` | Chronological audit trail of all approved admissions |
| **Audit** | `/staff` | `GET` | Staff roster with real-time assigned patient load percentages |
| **Audit** | `/equipment` | `GET` | Medical equipment status (Ventilators, Dialysis, ECMO, Infusion Pumps) |

---

## 🛡️ Robustness & Error Handling

- **Atomic Approvals**: Handles `409 Conflict` gracefully when a bed was already taken by a concurrent allocation request.
- **Auto Refresh**: Live polling timer on key views with manual instant-refresh buttons.
- **Backend Fallbacks**: Graceful error and loading states when the FastAPI server is launching or reconnecting.
