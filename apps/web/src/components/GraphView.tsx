import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import cytoscape, { Core } from "cytoscape";
import { Activity, Loader2, AlertTriangle, ZoomIn, ZoomOut, Maximize } from "lucide-react";
import type { InvestigationGraph, GraphNode } from "../types";

export function GraphView({
  graph,
  onSelectNode,
  loading
}: {
  graph: InvestigationGraph | null;
  onSelectNode: (node: GraphNode) => void;
  loading: boolean;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<Core | null>(null);
  const [error, setError] = useState("");

  const nodeMap = useMemo(
    () => new Map((graph?.nodes ?? []).map((node) => [node.id, node])),
    [graph]
  );

  const handleZoomIn = useCallback(() => {
    if (!cyRef.current) return;
    cyRef.current.zoom({ level: cyRef.current.zoom() * 1.3, renderedPosition: { x: 500, y: 350 } });
  }, []);

  const handleZoomOut = useCallback(() => {
    if (!cyRef.current) return;
    cyRef.current.zoom({ level: cyRef.current.zoom() / 1.3, renderedPosition: { x: 500, y: 350 } });
  }, []);

  const handleFit = useCallback(() => {
    cyRef.current?.fit(undefined, 36);
  }, []);

  useEffect(() => {
    if (!ref.current || !graph) return;
    setError("");
    cyRef.current?.destroy();

    try {
      const elements = [
        ...graph.nodes.map((node) => ({
          data: {
            id: node.id,
            label: node.label,
            risk: node.risk_level,
            score: node.risk_score,
            hop: node.hop
          }
        })),
        ...graph.edges.map((edge) => ({
          data: {
            id: edge.id,
            source: edge.source,
            target: edge.target,
            label: `${edge.value_eth.toFixed(2)} ETH`
          }
        }))
      ];

      const cy = cytoscape({
        container: ref.current,
        elements,
        layout: {
          name: "cose",
          animate: false,
          fit: true,
          padding: 36,
          nodeRepulsion: () => 8000,
          idealEdgeLength: () => 120,
          gravity: 0.25
        },
        minZoom: 0.2,
        maxZoom: 3,
        wheelSensitivity: 0.3,
        style: [
          {
            selector: "node",
            style: {
              "background-color": "#163300",
              label: "data(label)",
              color: "#0e0f0c",
              "font-size": 11,
              "font-family": "OPPO Sans, Inter, system-ui, sans-serif",
              "font-weight": 600,
              "text-valign": "bottom",
              "text-margin-y": 8,
              "text-max-width": "120px",
              "text-wrap": "ellipsis",
              width: "mapData(score, 0, 100, 24, 58)",
              height: "mapData(score, 0, 100, 24, 58)",
              "border-color": "#9fe870",
              "border-width": 2
            }
          },
          {
            selector: 'node[risk = "medium"]',
            style: { "background-color": "#ffd11a", "border-color": "#b86700" }
          },
          {
            selector: 'node[risk = "high"]',
            style: { "background-color": "#ffc091", "border-color": "#b86700" }
          },
          {
            selector: 'node[risk = "critical"]',
            style: { "background-color": "#d03238", "border-color": "#a72027" }
          },
          {
            selector: "node:selected",
            style: {
              "border-width": 4,
              "border-color": "#9fe870",
              "overlay-opacity": 0.1
            }
          },
          {
            selector: "edge",
            style: {
              width: 1.4,
              "line-color": "#868685",
              "target-arrow-color": "#868685",
              "target-arrow-shape": "triangle",
              "curve-style": "bezier",
              label: "data(label)",
              color: "#454745",
              "font-size": 9,
              "font-family": "OPPO Sans, Inter, system-ui, sans-serif",
              "text-background-color": "#ffffff",
              "text-background-opacity": 0.9,
              "text-background-padding": "3px"
            }
          }
        ]
      });

      cy.on("tap", "node", (event) => {
        const node = nodeMap.get(event.target.id());
        if (node) onSelectNode(node);
      });

      cyRef.current = cy;
    } catch {
      setError("Failed to render graph visualization.");
    }

    return () => {
      cyRef.current?.destroy();
      cyRef.current = null;
    };
  }, [graph, nodeMap, onSelectNode]);

  if (loading) {
    return (
      <div className="graph-canvas graph-loading">
        <Loader2 className="spin" size={36} />
        <span>Loading graph data...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="graph-canvas graph-error">
        <AlertTriangle size={36} />
        <span>{error}</span>
        <button className="secondary-button" onClick={() => setError("")}>
          Retry
        </button>
      </div>
    );
  }

  if (!graph) {
    return (
      <div className="graph-canvas graph-empty">
        <Activity size={34} />
        <span>Enter an address and run investigation to see the transaction graph.</span>
      </div>
    );
  }

  if (graph.nodes.length === 0) {
    return (
      <div className="graph-canvas graph-empty">
        <Activity size={34} />
        <span>No graph data available for this investigation.</span>
      </div>
    );
  }

  return (
    <div className="graph-wrapper">
      <div className="graph-controls">
        <button onClick={handleZoomIn} title="Zoom in" className="graph-control-btn">
          <ZoomIn size={16} />
        </button>
        <button onClick={handleZoomOut} title="Zoom out" className="graph-control-btn">
          <ZoomOut size={16} />
        </button>
        <button onClick={handleFit} title="Fit to view" className="graph-control-btn">
          <Maximize size={16} />
        </button>
      </div>
      <div className="graph-canvas" ref={ref} />
    </div>
  );
}
