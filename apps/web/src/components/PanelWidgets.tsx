import { Activity, Target } from "lucide-react";
import type { PatternSignal, SourceHit, GraphNode } from "../types";
import { compactAddress } from "../api";

export function PatternSignals({ signals }: { signals: PatternSignal[] }) {
  return (
    <section className="panel">
      <div className="panel-title">
        <Activity size={18} />
        Pattern Signals ({signals.length})
      </div>
      <div className="signal-list">
        {signals.length === 0 && (
          <div className="empty-state">
            <p>No pattern signals detected.</p>
          </div>
        )}
        {signals.slice(0, 10).map((signal) => (
          <article className={`signal ${signal.severity}`} key={`${signal.name}-${signal.subject}`}>
            <div>
              <strong>{signal.name.replaceAll("_", " ")}</strong>
              <span className="signal-score">{signal.score.toFixed(1)}</span>
            </div>
            <p>{signal.evidence}</p>
            <code title={signal.subject}>{compactAddress(signal.subject)}</code>
          </article>
        ))}
      </div>
    </section>
  );
}

export function SourceHits({ hits }: { hits: SourceHit[] }) {
  return (
    <section className="panel">
      <div className="panel-title">
        <Target size={18} />
        Source Hits ({hits.length})
      </div>
      <div className="source-list">
        {hits.length === 0 && (
          <div className="empty-state">
            <p>No source hits found.</p>
          </div>
        )}
        {hits.slice(0, 10).map((hit) => (
          <article className={`source-hit ${hit.severity}`} key={`${hit.source}-${hit.address}-${hit.category}`}>
            <div>
              <strong>{hit.direct_hit ? "DIRECT" : hit.source}</strong>
              <span>{hit.category}</span>
            </div>
            <p>{hit.evidence}</p>
            <code title={hit.address}>{compactAddress(hit.address)}</code>
          </article>
        ))}
      </div>
    </section>
  );
}

export function NodeDetails({ node }: { node: GraphNode | null }) {
  return (
    <section className="panel">
      <div className="panel-title">
        <Target size={18} />
        Node Detail
      </div>
      {!node && (
        <div className="empty-state">
          <p>Click a node in the graph to see its details.</p>
        </div>
      )}
      {node && (
        <div className="node-detail">
          <code title={node.address}>{node.address}</code>
          <div className="detail-grid">
            <span>Hop</span>
            <strong>{node.hop}</strong>
            <span>Risk Score</span>
            <strong>{node.risk_score.toFixed(1)}</strong>
            <span>Level</span>
            <strong className={`risk-level-text ${node.risk_level}`}>{node.risk_level}</strong>
            <span>Source</span>
            <strong>{node.source}</strong>
          </div>
          <div className="tag-row">
            {node.tags.length === 0 && <span className="tag neutral">no tags</span>}
            {node.tags.map((tag) => (
              <span className="tag" key={tag}>
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
