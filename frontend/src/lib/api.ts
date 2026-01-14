import { createClient } from "@supabase/supabase-js"

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

export const supabase = createClient(supabaseUrl!, supabaseAnonKey!)

const API_BASE = "/api"

async function getUserId(): Promise<string> {
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) throw new Error("Not authenticated")
  return user.id
}

export const api = {
  // Health check
  health: async () => {
    const res = await fetch(`${API_BASE}/health`)
    return res.json()
  },

  // Upload CSV
  uploadCSV: async (file: File) => {
    const userId = await getUserId()
    const formData = new FormData()
    formData.append("file", file)

    const res = await fetch(`${API_BASE}/upload/csv`, {
      method: "POST",
      body: formData,
      headers: { "X-User-ID": userId },
    })

    if (!res.ok) throw new Error("Upload failed")
    return res.json()
  },

  // Categorize transactions
  categorize: async (transactions: Transaction[]) => {
    const userId = await getUserId()
    const res = await fetch(`${API_BASE}/categorize`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-ID": userId,
      },
      body: JSON.stringify({
        transactions,
        user_id: userId,
      }),
    })

    if (!res.ok) throw new Error("Categorization failed")
    return res.json()
  },

  // Save transactions
  saveTransactions: async (transactions: Transaction[]) => {
    const userId = await getUserId()
    const res = await fetch(`${API_BASE}/transactions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-ID": userId,
      },
      body: JSON.stringify(transactions),
    })

    if (!res.ok) throw new Error("Save failed")
    return res.json()
  },

  // Get transactions
  getTransactions: async (filters?: {
    start_date?: string
    end_date?: string
    category?: string
    limit?: number
  }) => {
    const userId = await getUserId()
    const params = new URLSearchParams()
    if (filters?.start_date) params.set("start_date", filters.start_date)
    if (filters?.end_date) params.set("end_date", filters.end_date)
    if (filters?.category) params.set("category", filters.category)
    if (filters?.limit) params.set("limit", String(filters.limit))

    const res = await fetch(
      `${API_BASE}/transactions?${params.toString()}`,
      { headers: { "X-User-ID": userId } }
    )

    if (!res.ok) throw new Error("Fetch failed")
    return res.json()
  },

  // Dashboard
  getDashboard: async () => {
    const userId = await getUserId()
    const res = await fetch(`${API_BASE}/dashboard`, {
      headers: { "X-User-ID": userId },
    })

    if (!res.ok) throw new Error("Fetch failed")
    return res.json()
  },

  // Budgets
  getBudgets: async (month?: number) => {
    const userId = await getUserId()
    const params = month ? `?month=${month}` : ""
    const res = await fetch(`${API_BASE}/budgets${params}`, {
      headers: { "X-User-ID": userId },
    })

    if (!res.ok) throw new Error("Fetch failed")
    return res.json()
  },

  createBudget: async (budget: {
    category: string
    monthly_limit: number
    month: string
    user_id: string
  }) => {
    const userId = await getUserId()
    const res = await fetch(`${API_BASE}/budgets`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-ID": userId,
      },
      body: JSON.stringify({ ...budget, user_id: userId }),
    })

    if (!res.ok) throw new Error("Create failed")
    return res.json()
  },

  // Forecast
  generateForecast: async (request: {
    months_ahead?: number
    category?: string | null
  }) => {
    const userId = await getUserId()
    const res = await fetch(`${API_BASE}/forecast`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-ID": userId,
      },
      body: JSON.stringify({ ...request, user_id: userId }),
    })

    if (!res.ok) throw new Error("Forecast failed")
    return res.json()
  },

  // Check alerts
  checkAlerts: async () => {
    const userId = await getUserId()
    const res = await fetch(`${API_BASE}/alerts/check`, {
      method: "POST",
      headers: { "X-User-ID": userId },
    })

    if (!res.ok) throw new Error("Check failed")
    return res.json()
  },
}

export interface Transaction {
  date: string
  description: string
  amount: number
  category?: string
  is_income?: boolean
  source?: string
}
