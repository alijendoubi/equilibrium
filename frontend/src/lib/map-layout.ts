import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceRadial,
  forceSimulation,
  forceX,
  forceY,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";
import type { Edge, MapNode, NodeType } from "@/lib/api/types";
import { ALL_NODE_TYPES } from "@/lib/graph-map";

/**
 * Static, deterministic force layout for the evidence map.
 *
 * The simulation runs to completion up front (at most MAX_TICKS, stopping early once it has
 * settled) and is never animated, so the same data always draws the same picture and
 * prefers-reduced-motion users never see motion. Initial positions are seeded by node type
 * (one sector per type) and hop distance (one ring per hop), so types read as neighbourhoods.
 */

export const MAX_TICKS = 300;
const RING = 190;
const OVERVIEW_RING = 260;
const LABEL_ROOM = 16;

export interface Point {
  x: number;
  y: number;
}

export interface MapLayout {
  positions: Map<string, Point>;
  /** viewBox [x, y, width, height] that frames every node and its label. */
  viewBox: [number, number, number, number];
  ticks: number;
}

interface SimNode extends SimulationNodeDatum {
  id: string;
  r: number;
  distance: number | null;
  type: NodeType;
}

/** Node radius: grows with the number of links on the map, the center is drawn larger. */
export function nodeRadius(degree: number, isCenter = false): number {
  const base = Math.min(7 + Math.sqrt(degree) * 3, 22);
  return isCenter ? base + 6 : base;
}

function seed(nodes: MapNode[], center: string | null): SimNode[] {
  const present = ALL_NODE_TYPES.filter((t) => nodes.some((n) => n.node.type === t));
  const indexInType = new Map<NodeType, number>();
  const sizeOfType = new Map<NodeType, number>();
  for (const n of nodes) sizeOfType.set(n.node.type, (sizeOfType.get(n.node.type) ?? 0) + 1);
  return nodes.map((n) => {
    const isCenter = n.node.id === center;
    const type = n.node.type;
    const i = indexInType.get(type) ?? 0;
    indexInType.set(type, i + 1);
    const sector = (2 * Math.PI) / Math.max(present.length, 1);
    const angle =
      present.indexOf(type) * sector + ((i + 0.5) / (sizeOfType.get(type) ?? 1)) * sector * 0.8;
    const ring = center
      ? RING * Math.max(n.distance ?? 1, 1)
      : OVERVIEW_RING * (0.6 + (i % 3) * 0.2);
    const sim: SimNode = {
      id: n.node.id,
      r: nodeRadius(n.degree, isCenter),
      distance: n.distance,
      type,
      x: isCenter ? 0 : Math.cos(angle) * ring,
      y: isCenter ? 0 : Math.sin(angle) * ring,
    };
    if (isCenter) {
      sim.fx = 0;
      sim.fy = 0;
    }
    return sim;
  });
}

/** Lays out the given nodes and the edges between them. Pure and deterministic. */
export function computeLayout(nodes: MapNode[], edges: Edge[], center: string | null): MapLayout {
  const simNodes = seed(nodes, center);
  const ids = new Set(simNodes.map((n) => n.id));
  const links: SimulationLinkDatum<SimNode>[] = edges
    .filter((e) => ids.has(e.source_id) && ids.has(e.target_id) && e.source_id !== e.target_id)
    .map((e) => ({ source: e.source_id, target: e.target_id }));

  const simulation = forceSimulation<SimNode>(simNodes)
    .force(
      "link",
      forceLink<SimNode, SimulationLinkDatum<SimNode>>(links)
        .id((d) => d.id)
        .distance(center ? 90 : 70)
        .strength(0.35),
    )
    .force("charge", forceManyBody<SimNode>().strength(center ? -320 : -240))
    .force(
      "collide",
      forceCollide<SimNode>()
        .radius((d) => d.r + LABEL_ROOM)
        .strength(0.9),
    )
    .force("x", forceX<SimNode>(0).strength(center ? 0.02 : 0.06))
    .force("y", forceY<SimNode>(0).strength(center ? 0.03 : 0.08))
    .stop();
  if (center) {
    simulation.force(
      "radial",
      forceRadial<SimNode>((d) => RING * (d.distance ?? 1), 0, 0).strength(0.5),
    );
  }

  let ticks = 0;
  while (ticks < MAX_TICKS && simulation.alpha() > simulation.alphaMin()) {
    simulation.tick();
    ticks += 1;
  }

  const positions = new Map<string, Point>();
  let minX = 0;
  let minY = 0;
  let maxX = 0;
  let maxY = 0;
  for (const n of simNodes) {
    const x = n.x ?? 0;
    const y = n.y ?? 0;
    positions.set(n.id, { x, y });
    minX = Math.min(minX, x - n.r);
    maxX = Math.max(maxX, x + n.r);
    minY = Math.min(minY, y - n.r);
    maxY = Math.max(maxY, y + n.r);
  }
  // Labels sit under the nodes and run sideways, so leave room on every edge.
  const padX = 110;
  const padTop = 30;
  const padBottom = 40;
  const viewBox: MapLayout["viewBox"] = [
    minX - padX,
    minY - padTop,
    Math.max(maxX - minX + 2 * padX, 480),
    Math.max(maxY - minY + padTop + padBottom, 320),
  ];
  return { positions, viewBox, ticks };
}
