import {
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'

import { METRIC_DEFINITIONS } from './metricDefinitions'

export function MetricDefinitionsPanel() {
  return (
    <Stack spacing={2}>
      <Typography variant="h6">Определения метрик</Typography>
      <Typography variant="body2" color="text.secondary">
        Формулы совпадают с backend / ADR; фронтенд не пересчитывает
        значения.
      </Typography>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Аббр.</TableCell>
            <TableCell>Название</TableCell>
            <TableCell>Формула</TableCell>
            <TableCell>Ед.</TableCell>
            <TableCell>Пояснение</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {METRIC_DEFINITIONS.map((item) => (
            <TableRow key={item.id}>
              <TableCell>{item.abbr}</TableCell>
              <TableCell>{item.title}</TableCell>
              <TableCell>
                <code>{item.formula}</code>
              </TableCell>
              <TableCell>{item.unit}</TableCell>
              <TableCell>{item.notes}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Stack>
  )
}
