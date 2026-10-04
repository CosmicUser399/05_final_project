import { Alert, Button, Stack, Typography } from '@mui/material'
import { useMutation } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { excelApi } from '../../api/resources'

interface ExcelExchangePanelProps {
  versionId: string
}

export function ExcelExchangePanel({ versionId }: ExcelExchangePanelProps) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const exportMutation = useMutation({
    mutationFn: () => excelApi.exportWorkbook(versionId),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `version-${versionId}.xlsx`
      anchor.click()
      URL.revokeObjectURL(url)
      setMessage('Excel-файл скачан')
      setError(null)
    },
    onError: (err: Error) => {
      setError(err.message)
      setMessage(null)
    },
  })

  const importMutation = useMutation({
    mutationFn: (file: File) => excelApi.importWorkbook(versionId, file),
    onSuccess: (result) => {
      setMessage(
        `Импортировано оборудования: ${String(result.imported.equipment)}`,
      )
      setError(null)
    },
    onError: (err: Error) => {
      setError(err.message)
      setMessage(null)
    },
  })

  return (
    <Stack spacing={2}>
      <Typography variant="h6">Excel обмен</Typography>
      <Typography color="text.secondary" variant="body2">
        Экспорт и импорт версии как производного формата. Импорт только в пустой
        DRAFT. Domain DB остаётся источником истины.
      </Typography>
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
        <Button
          variant="contained"
          onClick={() => exportMutation.mutate()}
          disabled={exportMutation.isPending}
        >
          Экспорт .xlsx
        </Button>
        <Button
          variant="outlined"
          onClick={() => inputRef.current?.click()}
          disabled={importMutation.isPending}
        >
          Импорт .xlsx
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0]
            if (file) {
              importMutation.mutate(file)
            }
            event.target.value = ''
          }}
        />
      </Stack>
      {message ? <Alert severity="success">{message}</Alert> : null}
      {error ? <Alert severity="error">{error}</Alert> : null}
    </Stack>
  )
}
