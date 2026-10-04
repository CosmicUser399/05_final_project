import type { RouteObject } from 'react-router-dom'

import { Layout } from '../components/Layout'
import { AnalystPage } from '../features/ai/AnalystPage'
import { GenerateSystemPage } from '../features/ai/GenerateSystemPage'
import { ProposalReviewPage } from '../features/ai/ProposalReviewPage'
import { SimulationDetailPage } from '../features/results/SimulationDetailPage'
import { SimulationsListPage } from '../features/results/SimulationsListPage'
import { ReferenceBrowserPage } from '../features/reference/ReferenceBrowserPage'
import { ScenarioDetailPage } from '../features/scenarios/ScenarioDetailPage'
import { ScenariosListPage } from '../features/scenarios/ScenariosListPage'
import { SystemDetailPage } from '../features/systems/SystemDetailPage'
import { SystemsListPage } from '../features/systems/SystemsListPage'
import { HomePage, NotFoundPage } from '../pages/pages'

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'systems', element: <SystemsListPage /> },
      { path: 'systems/:systemId', element: <SystemDetailPage /> },
      { path: 'ai/generate', element: <GenerateSystemPage /> },
      { path: 'ai/analyst', element: <AnalystPage /> },
      { path: 'ai/proposals/:proposalId', element: <ProposalReviewPage /> },
      { path: 'simulations', element: <SimulationsListPage /> },
      { path: 'simulations/:runId', element: <SimulationDetailPage /> },
      { path: 'scenarios', element: <ScenariosListPage /> },
      { path: 'scenarios/:scenarioId', element: <ScenarioDetailPage /> },
      { path: 'reference', element: <ReferenceBrowserPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
