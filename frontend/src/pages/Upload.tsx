import { useState, useCallback } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import { useToast } from "@/components/ui/use-toast"
import { Upload, Loader2, CheckCircle, AlertCircle } from "lucide-react"

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("No file selected")
      const uploadResult = await api.uploadCSV(file)

      // Categorize
      const categorizeResult = await api.categorize(uploadResult.transactions)

      // Merge categories and save
      const categorizedTx = uploadResult.transactions.map(
        (tx: any, idx: number) => ({
          ...tx,
          category: categorizeResult.results[idx]?.category || "Other",
        })
      )

      await api.saveTransactions(categorizedTx)
      return { uploadResult, categorizeResult }
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] })
      queryClient.invalidateQueries({ queryKey: ["transactions"] })
      toast({
        title: "Upload successful",
        description: `Processed ${data.uploadResult.rows_parsed} transactions with ${data.categorizeResult.avg_confidence.toFixed(0)}% avg confidence`,
      })
      setFile(null)
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Upload failed",
        description: error.message,
      })
    },
  })

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile?.name.endsWith(".csv")) {
      setFile(droppedFile)
    }
  }, [])

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Upload Transactions</h1>
        <p className="text-muted-foreground">
          Upload a CSV file to import and categorize your transactions
        </p>
      </div>

      {/* Drop Zone */}
      <Card
        className={`border-2 border-dashed transition-colors ${
          isDragging ? "border-primary bg-primary/5" : "border-gray-200"
        }`}
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <CardContent className="p-12 text-center">
          <Upload className="mx-auto h-12 w-12 text-gray-400 mb-4" />
          <p className="text-lg font-medium mb-2">
            {file ? file.name : "Drop your CSV file here"}
          </p>
          <p className="text-sm text-muted-foreground mb-4">
            or click to browse
          </p>
          <Input
            type="file"
            accept=".csv"
            className="hidden"
            id="file-upload"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          <Button asChild variant="outline">
            <label htmlFor="file-upload">Select File</label>
          </Button>
        </CardContent>
      </Card>

      {/* Upload Button */}
      {file && (
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <CheckCircle className="h-5 w-5 text-green-600" />
                <div>
                  <p className="font-medium">{file.name}</p>
                  <p className="text-sm text-muted-foreground">
                    Ready to upload
                  </p>
                </div>
              </div>
              <Button
                onClick={() => uploadMutation.mutate()}
                disabled={uploadMutation.isPending}
              >
                {uploadMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Processing...
                  </>
                ) : (
                  "Upload & Categorize"
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Info Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5" />
            CSV Format Requirements
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p>Your CSV should have columns for:</p>
          <ul className="list-disc list-inside space-y-1 text-muted-foreground">
            <li>
              <strong>Date</strong> - Transaction date (various formats supported)
            </li>
            <li>
              <strong>Amount</strong> - Transaction amount
            </li>
            <li>
              <strong>Description</strong> - Transaction description (optional,
              will be auto-generated if missing)
            </li>
          </ul>
          <p className="mt-4 text-muted-foreground">
            The parser will automatically detect common column names like
            "Txn Date", "Value", "Payee", etc.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
