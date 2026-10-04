import {
  Alert,
  Box,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Typography,
} from '@mui/material'
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from 'dagre'
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { connectionsApi, equipmentApi } from '../../api/resources'

interface Props {
  versionId: string
}

const NODE_WIDTH = 180
const NODE_HEIGHT = 56

function layoutGraph(nodes: Node[], edges: Edge[]): Node[] {
  const graph = new dagre.graphlib.Graph()
  graph.setDefaultEdgeLabel(() => ({}))
  graph.setGraph({ rankdir: 'LR', nodesep: 40, ranksep: 80 })
  for (const node of nodes) {
    graph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT })
  }
  for (const edge of edges) {
    graph.setEdge(edge.source, edge.target)
  }
  dagre.layout(graph)
  return nodes.map((node) => {
    const position = graph.node(node.id)
    return {
      ...node,
      position: {
        x: position.x - NODE_WIDTH / 2,
        y: position.y - NODE_HEIGHT / 2,
      },
    }
  })
}

export function EquipmentGraph({ versionId }: Props) {
  const [typeFilter, setTypeFilter] = useState<string>('ALL')

  const equipmentQuery = useQuery({
    queryKey: ['equipment', versionId],
    queryFn: () => equipmentApi.list(versionId),
  })
  const connectionsQuery = useQuery({
    queryKey: ['connections', versionId],
    queryFn: () => connectionsApi.list(versionId),
  })

  const { nodes, edges } = useMemo(() => {
    const equipment = equipmentQuery.data ?? []
    const connections = connectionsQuery.data ?? []
    const filteredConnections =
      typeFilter === 'ALL'
        ? connections
        : connections.filter((item) => item.connection_type === typeFilter)

    const usedIds = new Set<string>()
    for (const connection of filteredConnections) {
      usedIds.add(connection.source_id)
      usedIds.add(connection.target_id)
    }
    for (const item of equipment) {
      if (item.parent_id) {
        usedIds.add(item.id)
        usedIds.add(item.parent_id)
      }
    }

    const baseNodes: Node[] = equipment
      .filter((item) => usedIds.size === 0 || usedIds.has(item.id))
      .map((item) => ({
        id: item.id,
        data: {
          label: `${item.tag}\n${item.name}`,
        },
        position: { x: 0, y: 0 },
        style: {
          width: NODE_WIDTH,
          border:
            item.criticality === 'CRITICAL' || item.criticality === 'HIGH'
              ? '2px solid #c62828'
              : '1px solid #90a4ae',
          background: item.criticality === 'CRITICAL' ? '#ffebee' : '#ffffff',
          fontSize: 12,
          whiteSpace: 'pre-line',
          textAlign: 'center',
          padding: 8,
        },
      }))

    const linkEdges: Edge[] = filteredConnections.map((item) => ({
      id: item.id,
      source: item.source_id,
      target: item.target_id,
      label: item.connection_type,
      markerEnd: { type: MarkerType.ArrowClosed },
    }))

    for (const item of equipment) {
      if (item.parent_id) {
        linkEdges.push({
          id: `parent-${item.id}`,
          source: item.parent_id,
          target: item.id,
          label: 'HIERARCHY',
          style: { strokeDasharray: '4 2' },
        })
      }
    }

    return {
      nodes: layoutGraph(baseNodes, linkEdges),
      edges: linkEdges,
    }
  }, [connectionsQuery.data, equipmentQuery.data, typeFilter])

  if (equipmentQuery.isError || connectionsQuery.isError) {
    return <Alert severity="error">Не удалось загрузить граф</Alert>
  }

  return (
    <Stack spacing={1} sx={{ height: 520 }}>
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
        <Typography variant="subtitle1">Граф оборудования</Typography>
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel id="conn-filter">Тип связи</InputLabel>
          <Select
            labelId="conn-filter"
            label="Тип связи"
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value)}
          >
            <MenuItem value="ALL">Все</MenuItem>
            <MenuItem value="PROCESS">PROCESS</MenuItem>
            <MenuItem value="MATERIAL">MATERIAL</MenuItem>
            <MenuItem value="ENERGY">ENERGY</MenuItem>
            <MenuItem value="ELECTRICAL">ELECTRICAL</MenuItem>
            <MenuItem value="CONTROL">CONTROL</MenuItem>
            <MenuItem value="UTILITY">UTILITY</MenuItem>
            <MenuItem value="DEPENDENCY">DEPENDENCY</MenuItem>
          </Select>
        </FormControl>
      </Box>
      <Typography variant="body2" color="text.secondary">
        Красная рамка — высокая/критическая критичность. Пунктир — иерархия
        parent.
      </Typography>
      <Box sx={{ flex: 1, border: '1px solid', borderColor: 'divider' }}>
        <ReactFlow nodes={nodes} edges={edges} fitView>
          <Background />
          <MiniMap />
          <Controls />
        </ReactFlow>
      </Box>
    </Stack>
  )
}
