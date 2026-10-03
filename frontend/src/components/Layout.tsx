import {
  AppBar,
  Box,
  Button,
  Container,
  Toolbar,
  Typography,
} from '@mui/material'
import { Link as RouterLink, NavLink, Outlet } from 'react-router-dom'

import { NAV_ITEMS } from '../app/navigation'
import { BackendStatus } from '../features/health/BackendStatus'

export function Layout() {
  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'grey.50' }}>
      <AppBar position="static">
        <Toolbar sx={{ gap: 1 }}>
          <Typography
            variant="h6"
            component={RouterLink}
            to="/"
            sx={{ color: 'inherit', textDecoration: 'none', mr: 2 }}
          >
            AI Reliability Modelling
          </Typography>
          {NAV_ITEMS.map((item) => (
            <Button
              key={item.path}
              color="inherit"
              component={NavLink}
              to={item.path}
              end={item.path === '/'}
              sx={{ '&.active': { bgcolor: 'rgba(255,255,255,0.18)' } }}
            >
              {item.label}
            </Button>
          ))}
          <Box sx={{ flexGrow: 1 }} />
          <BackendStatus />
        </Toolbar>
      </AppBar>
      <Container maxWidth="xl" sx={{ py: 3 }}>
        <Outlet />
      </Container>
    </Box>
  )
}
