import { useState } from 'react'
import { RouterProvider, createBrowserRouter } from 'react-router-dom'

import { Providers } from './app/Providers'
import { createQueryClient } from './app/queryClient'
import { routes } from './app/routes'

export default function App() {
  const [router] = useState(() => createBrowserRouter(routes))
  const [client] = useState(createQueryClient)
  return (
    <Providers client={client}>
      <RouterProvider router={router} />
    </Providers>
  )
}
