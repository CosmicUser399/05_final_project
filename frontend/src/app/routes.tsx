import type { RouteObject } from 'react-router-dom'

import { Layout } from '../components/Layout'
import {
  HomePage,
  NotFoundPage,
  ScenariosPage,
  SimulationsPage,
  SystemsPage,
} from '../pages/pages'

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'systems', element: <SystemsPage /> },
      { path: 'simulations', element: <SimulationsPage /> },
      { path: 'scenarios', element: <ScenariosPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
