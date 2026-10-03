import type { RouteObject } from 'react-router-dom'

import { Layout } from '../components/Layout'
import { GenerateSystemPage } from '../features/ai/GenerateSystemPage'
import { ProposalReviewPage } from '../features/ai/ProposalReviewPage'
import { SystemDetailPage } from '../features/systems/SystemDetailPage'
import { SystemsListPage } from '../features/systems/SystemsListPage'
import {
  HomePage,
  NotFoundPage,
  ScenariosPage,
  SimulationsPage,
} from '../pages/pages'

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'systems', element: <SystemsListPage /> },
      { path: 'systems/:systemId', element: <SystemDetailPage /> },
      { path: 'ai/generate', element: <GenerateSystemPage /> },
      { path: 'ai/proposals/:proposalId', element: <ProposalReviewPage /> },
      { path: 'simulations', element: <SimulationsPage /> },
      { path: 'scenarios', element: <ScenariosPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
