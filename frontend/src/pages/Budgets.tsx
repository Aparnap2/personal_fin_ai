import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { api, formatCurrency } from "@/lib/api"
import { useToast } from "@/components/ui/use-toast"
import { Plus, Loader2 } from "lucide-react"

const CATEGORIES = [
  "Groceries",
  "Dining",
  "Transport",
  "Utilities",
  "Shopping",
  "Entertainment",
  "Health",
  "Subscriptions",
]

export default function BudgetsPage() {
  const [newBudget, setNewBudget] = useState({
    category: "",
    monthly_limit: "",
    month: new Date().toISOString().slice(0, 7),
  })
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const { data: budgets, isLoading } = useQuery({
    queryKey: ["budgets"],
    queryFn: () => api.getBudgets(),
  })

  const createMutation = useMutation({
    mutationFn: api.createBudget,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budgets"] })
      toast({ title: "Budget created" })
      setNewBudget({ category: "", monthly_limit: "", month: newBudget.month })
    },
    onError: (error: Error) => {
      toast({ variant: "destructive", title: "Failed", description: error.message })
    },
  })

  const handleCreate = () => {
    if (!newBudget.category || !newBudget.monthly_limit) {
      toast({ variant: "destructive", title: "Error", description: "Fill all fields" })
      return
    }
    createMutation.mutate({
      category: newBudget.category,
      monthly_limit: parseFloat(newBudget.monthly_limit),
      month: newBudget.month,
      user_id: "",
    })
  }

  // Calculate spending per category from budgets
  const { data: transactions } = useQuery({
    queryKey: ["transactions"],
    queryFn: () => api.getTransactions({ limit: 500 }),
  })

  const getSpending = (category: string) => {
    return transactions
      ?.filter((tx: any) => tx.category === category && !tx.is_income)
      .reduce((sum: number, tx: any) => sum + Number(tx.amount), 0) || 0
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Budgets</h1>
        <p className="text-muted-foreground">
          Set spending limits for each category
        </p>
      </div>

      {/* Create Budget Form */}
      <Card>
        <CardHeader>
          <CardTitle>Create Budget</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-4">
            <select
              value={newBudget.category}
              onChange={(e) =>
                setNewBudget({ ...newBudget, category: e.target.value })
              }
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">Select category</option>
              {CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
            <Input
              type="number"
              placeholder="Monthly limit (₹)"
              value={newBudget.monthly_limit}
              onChange={(e) =>
                setNewBudget({ ...newBudget, monthly_limit: e.target.value })
              }
            />
            <Input
              type="month"
              value={newBudget.month}
              onChange={(e) =>
                setNewBudget({ ...newBudget, month: e.target.value })
              }
            />
            <Button onClick={handleCreate} disabled={createMutation.isPending}>
              {createMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              <span className="ml-2">Add Budget</span>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Budget List */}
      <div className="grid gap-4 md:grid-cols-2">
        {isLoading ? (
          <div className="col-span-2 flex justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
          </div>
        ) : budgets?.length > 0 ? (
          budgets.map((budget: any) => {
            const spending = getSpending(budget.category)
            const pctUsed = (spending / Number(budget.monthly_limit)) * 100
            const isOver = pctUsed > 110

            return (
              <Card
                key={budget.id}
                className={isOver ? "border-red-200 bg-red-50" : ""}
              >
                <CardHeader className="pb-2">
                  <CardTitle className="text-lg flex justify-between">
                    <span>{budget.category}</span>
                    <span
                      className={`text-sm font-normal ${
                        isOver ? "text-red-600" : "text-muted-foreground"
                      }`}
                    >
                      {pctUsed.toFixed(0)}% used
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Spent</span>
                      <span className="font-medium">
                        {formatCurrency(spending)}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Budget</span>
                      <span className="font-medium">
                        {formatCurrency(Number(budget.monthly_limit))}
                      </span>
                    </div>
                    <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          isOver
                            ? "bg-red-500"
                            : pctUsed > 80
                            ? "bg-yellow-500"
                            : "bg-green-500"
                        }`}
                        style={{ width: `${Math.min(pctUsed, 100)}%` }}
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            )
          })
        ) : (
          <div className="col-span-2 text-center py-12 text-muted-foreground">
            No budgets set. Create one above to start tracking.
          </div>
        )}
      </div>
    </div>
  )
}
