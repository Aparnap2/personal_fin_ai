import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { api, formatCurrency, formatDate } from "@/lib/api"

const CATEGORIES = [
  "Groceries",
  "Dining",
  "Transport",
  "Utilities",
  "Shopping",
  "Entertainment",
  "Health",
  "Subscriptions",
  "Income",
  "Savings",
  "Other",
]

export default function TransactionsPage() {
  const [filter, setFilter] = useState("")
  const [categoryFilter, setCategoryFilter] = useState("")

  const { data: transactions, isLoading } = useQuery({
    queryKey: ["transactions", { category: categoryFilter }],
    queryFn: () =>
      api.getTransactions({
        category: categoryFilter || undefined,
        limit: 100,
      }),
  })

  const filteredTransactions = transactions?.filter(
    (tx: any) =>
      tx.description.toLowerCase().includes(filter.toLowerCase()) ||
      tx.category?.toLowerCase().includes(filter.toLowerCase())
  )

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Transactions</h1>
        <p className="text-muted-foreground">
          View and manage your transactions
        </p>
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <Input
          placeholder="Search transactions..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="max-w-xs"
        />
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
        >
          <option value="">All Categories</option>
          {CATEGORIES.map((cat) => (
            <option key={cat} value={cat}>
              {cat}
            </option>
          ))}
        </select>
      </div>

      {/* Transactions List */}
      <Card>
        <CardHeader>
          <CardTitle>
            {filteredTransactions?.length || 0} Transactions
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            </div>
          ) : filteredTransactions?.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b text-left text-sm text-muted-foreground">
                    <th className="pb-3 font-medium">Date</th>
                    <th className="pb-3 font-medium">Description</th>
                    <th className="pb-3 font-medium">Category</th>
                    <th className="pb-3 font-medium text-right">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTransactions.map((tx: any) => (
                    <tr
                      key={tx.id}
                      className="border-b last:border-0 py-3 hover:bg-gray-50"
                    >
                      <td className="py-3">{formatDate(tx.date)}</td>
                      <td className="py-3 font-medium">{tx.description}</td>
                      <td className="py-3">
                        <span className="inline-flex items-center rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
                          {tx.category || "Uncategorized"}
                        </span>
                      </td>
                      <td
                        className={`py-3 text-right font-semibold ${
                          tx.is_income ? "text-green-600" : "text-red-600"
                        }`}
                      >
                        {tx.is_income ? "+" : "-"}
                        {formatCurrency(tx.amount)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-center py-8 text-muted-foreground">
              No transactions found
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
