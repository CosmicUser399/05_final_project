import {
  Alert,
  Box,
  Button,
  CircularProgress,
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
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { ApiError } from '../../api/client'
import { petriApi } from '../../api/resources'
import type { PetriSubnet } from '../../api/types'

interface Props {
  versionId: string
}

const NODE_WIDTH = 140
const NODE_HEIGHT = 48

function layoutGraph(nodes: Node[], edges: Edge[]): Node[] {
  const graph = new dagre.graphlib.Graph()
  graph.setDefaultEdgeLabel(() => ({}))
  graph.setGraph({ rankdir: 'LR', nodesep: 36, ranksep: 70 })
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

function subnetToFlow(subnet: PetriSubnet): {
  nodes: Node[]
  edges: Edge[]
} {
  const placeNodes: Node[] = subnet.places.map((place) => ({
    id: place.id,
    data: {
      label: `${place.role}\n${place.id}`,
      kind: 'place',
      source_entity_type: place.source_entity_type,
      source_entity_id: place.source_entity_id,
    },
    position: { x: 0, y: 0 },
    style: {
      width: NODE_WIDTH,
      borderRadius: 24,
      border: '2px solid #3d5a73',
      background: place.initial > 0 ? '#e8f0e9' : '#ffffff',
      fontSize: 11,
      whiteSpace: 'pre-line',
      textAlign: 'center',
      padding: 6,
    },
  }))

  const transitionNodes: Node[] = subnet.transitions.map((transition) => ({
    id: transition.id,
    data: {
      label: `${transition.role}\n${transition.id}`,
      kind: 'transition',
      source_entity_type: transition.source_entity_type,
      source_entity_id: transition.source_entity_id,
    },
    position: { x: 0, y: 0 },
    style: {
      width: NODE_WIDTH,
      borderRadius: 2,
      border: '2px solid #b35c1e',
      background: '#fff8f1',
      fontSize: 11,
      whiteSpace: 'pre-line',
      textAlign: 'center',
      padding: 6,
    },
  }))

  const edges: Edge[] = subnet.arcs.map((arc) => ({
    id: arc.id,
    source: arc.source,
    target: arc.target,
    label: arc.weight > 1 ? String(arc.weight) : undefined,
    markerEnd: { type: MarkerType.ArrowClosed },
  }))

  const nodes = layoutGraph([...placeNodes, ...transitionNodes], edges)
  return { nodes, edges }
}

export function PetriViewer({ versionId }: Props) {
  const queryClient = useQueryClient()
  const [subnetKey, setSubnetKey] = useState<string>('')
  const [selected, setSelected] = useState<{
    id: string
    kind: string
    source_entity_type: string | null
    source_entity_id: string | null
  } | null>(null)
  const [collapsed, setCollapsed] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const petriQuery = useQuery({
    queryKey: ['petri', versionId],
    queryFn: () => petriApi.getLatest(versionId),
    retry: false,
  })

  const generateMutation = useMutation({
    mutationFn: () => petriApi.generate(versionId),
    onSuccess: () => {
      setError(null)
      void queryClient.invalidateQueries({
        queryKey: ['petri', versionId],
      })
    },
    onError: (err: unknown) => {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Не удалось сгенерировать Petri-модель',
      )
    },
  })

  const definition = petriQuery.data?.definition ?? null
  const subnets = useMemo(() => definition?.subnets ?? [], [definition])
  const activeKey = subnetKey || subnets[0]?.key || ''
  const activeSubnet = subnets.find((item) => item.key === activeKey) ?? null

  const { nodes, edges } = useMemo(() => {
    if (!activeSubnet || collapsed) {
      return { nodes: [] as Node[], edges: [] as Edge[] }
    }
    return subnetToFlow(activeSubnet)
  }, [activeSubnet, collapsed])

  const overviewNodes: Node[] = useMemo(() => {
    if (!collapsed) {
      return []
    }
    return layoutGraph(
      subnets.map((subnet, index) => ({
        id: subnet.key,
        data: {
          label: `${subnet.name}\n${subnet.kind}`,
          kind: 'subnet',
          source_entity_type: null,
          source_entity_id: null,
        },
        position: { x: index * 200, y: 0 },
        style: {
          width: NODE_WIDTH + 20,
          border: '1px solid #5b6b7c',
          background: '#f7f7f5',
          fontSize: 11,
          whiteSpace: 'pre-line',
          textAlign: 'center',
          padding: 8,
        },
      })),
      [],
    )
  }, [collapsed, subnets])

  if (petriQuery.isLoading) {
    return <CircularProgress />
  }

  if (petriQuery.isError && !petriQuery.data) {
    return (
      <Stack spacing={2}>
        <Typography variant="h6">Petri viewer</Typography>
        <Alert severity="info">
          Petri-модель для версии ещё не сгенерирована.
        </Alert>
        {error ? <Alert severity="error">{error}</Alert> : null}
        <Button
          variant="contained"
          onClick={() => generateMutation.mutate()}
          disabled={generateMutation.isPending}
        >
          Сгенерировать Petri-модель
        </Button>
      </Stack>
    )
  }

  const model = petriQuery.data
  if (!model || !definition) {
    return <Alert severity="warning">Пустое определение Petri</Alert>
  }

  const selectedEquipmentId = selected
    ? definition.id_map[selected.id]?.equipment_id
    : null

  return (
    <Stack spacing={2} sx={{ height: 640 }}>
      <Typography variant="h6">Petri viewer</Typography>
      <Typography variant="body2" color="text.secondary">
        validation={model.validation_status}; model_hash=
        {model.reliability_model_hash.slice(0, 12)}…; places = окружности,
        transitions = прямоугольники. Клик показывает source entity.
      </Typography>
      <Stack direction={{ xs: 'column', md: 'row' }} spacing={1}>
        <FormControl size="small" sx={{ minWidth: 260 }} disabled={collapsed}>
          <InputLabel id="subnet">Подсеть</InputLabel>
          <Select
            labelId="subnet"
            label="Подсеть"
            value={activeKey}
            onChange={(event) => setSubnetKey(event.target.value)}
          >
            {subnets.map((subnet) => (
              <MenuItem key={subnet.key} value={subnet.key}>
                {subnet.name} ({subnet.kind})
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Button
          variant="outlined"
          onClick={() => setCollapsed((value) => !value)}
        >
          {collapsed ? 'Развернуть подсеть' : 'Свернуть до оборудования'}
        </Button>
        <Button
          variant="outlined"
          onClick={() => generateMutation.mutate()}
          disabled={generateMutation.isPending}
        >
          Перегенерировать
        </Button>
      </Stack>
      {error ? <Alert severity="error">{error}</Alert> : null}
      {selected ? (
        <Alert severity="info">
          {selected.kind} {selected.id}
          {selected.source_entity_type
            ? `; source: ${selected.source_entity_type}`
            : ''}
          {selected.source_entity_id
            ? ` / ${selected.source_entity_id}`
            : ' (нет привязки)'}
          {selectedEquipmentId ? `; equipment=${selectedEquipmentId}` : ''}
        </Alert>
      ) : null}
      <Box sx={{ flex: 1, border: '1px solid', borderColor: 'divider' }}>
        <ReactFlow
          nodes={collapsed ? overviewNodes : nodes}
          edges={collapsed ? [] : edges}
          fitView
          onNodeClick={(_event, node) => {
            if (collapsed) {
              setSubnetKey(node.id)
              setCollapsed(false)
              setSelected(null)
              return
            }
            const data = node.data as {
              kind?: string
              source_entity_type?: string | null
              source_entity_id?: string | null
            }
            setSelected({
              id: node.id,
              kind: data.kind ?? 'node',
              source_entity_type: data.source_entity_type ?? null,
              source_entity_id: data.source_entity_id ?? null,
            })
          }}
        >
          <Background />
          <MiniMap />
          <Controls />
        </ReactFlow>
      </Box>
    </Stack>
  )
}
