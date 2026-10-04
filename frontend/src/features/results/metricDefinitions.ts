/** Metric definitions shown in the Results UI (backend formulas). */

export interface MetricDefinition {
  id: string
  abbr: string
  title: string
  formula: string
  unit: string
  notes: string
}

export const METRIC_DEFINITIONS: readonly MetricDefinition[] = [
  {
    id: 'reliability',
    abbr: 'R(t)',
    title: 'System Reliability',
    formula: 'R(t) = P(T_failure > t)',
    unit: 'доля прогонов',
    notes:
      'В агрегатах — R(horizon): доля прогонов без системного отказа ' +
      'к горизонту. CI — Wilson / Clopper-Pearson.',
  },
  {
    id: 'ai',
    abbr: 'Ai',
    title: 'Inherent Availability',
    formula: 'Ai = MTBF / (MTBF + MTTR)',
    unit: 'доля',
    notes: 'Только корректирующие простои (ремонт).',
  },
  {
    id: 'ao',
    abbr: 'Ao',
    title: 'Operational Availability',
    formula: 'Ao = MTBM / (MTBM + MDT)',
    unit: 'доля',
    notes:
      'MDT включает диагностику, ожидание ресурса/запчасти, ремонт ' +
      'и логистику.',
  },
  {
    id: 'mtbf',
    abbr: 'MTBF',
    title: 'Mean Time Between Failures',
    formula: 'рабочее время / число отказов',
    unit: 'мин',
    notes: 'Среднее по прогонам Monte Carlo; P5/P50/P95 по прогонам.',
  },
  {
    id: 'mttr',
    abbr: 'MTTR',
    title: 'Mean Time To Repair',
    formula: 'время CM / число ремонтов',
    unit: 'мин',
    notes: 'Также repair p90/p95 по выборке длительностей ремонта.',
  },
  {
    id: 'mtbm',
    abbr: 'MTBM',
    title: 'Mean Time Between Maintenance',
    formula: 'время / (PM + CM события)',
    unit: 'мин',
    notes: 'Все события обслуживания.',
  },
  {
    id: 'mdt',
    abbr: 'MDT',
    title: 'Mean Down Time',
    formula: 'суммарный простой / число простоев',
    unit: 'мин',
    notes: 'Включает ожидание ресурсов и запчастей.',
  },
  {
    id: 'production_loss',
    abbr: 'Loss',
    title: 'Production Loss',
    formula: 'sum(loss_rate × nominal_rate × duration)',
    unit: 'ед. продукции',
    notes: 'Warm-up период исключается из метрик на backend.',
  },
  {
    id: 'production_availability',
    abbr: 'PA',
    title: 'Production Availability',
    formula: 'фактический выпуск / номинальный',
    unit: 'доля',
    notes: 'Агрегат по прогонам с mean/median/P5/P95/CI.',
  },
]
