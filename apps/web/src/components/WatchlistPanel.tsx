import { Shield, Plus, Loader2, AlertTriangle, Search } from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import { request, compactAddress } from "../api";

interface WatchlistEntry {
  address: string;
  label: string;
  category: string;
  severity: string;
  notes?: string;
}

interface WatchlistStats {
  total_entries: number;
  by_severity: Record<string, number>;
  by_category: Record<string, number>;
}

export function WatchlistPanel() {
  const [entries, setEntries] = useState<WatchlistEntry[]>([]);
  const [stats, setStats] = useState<WatchlistStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [newAddress, setNewAddress] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [newCategory, setNewCategory] = useState("sanctions");
  const [newSeverity, setNewSeverity] = useState("critical");
  const [newNotes, setNewNotes] = useState("");
  const [addLoading, setAddLoading] = useState(false);

  const loadWatchlist = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const entriesData = await request<WatchlistEntry[]>("/api/v1/watchlists");
      setEntries(entriesData);
      setStats(buildStats(entriesData));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load watchlist");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadWatchlist();
  }, [loadWatchlist]);

  async function addEntry() {
    if (!newAddress.trim() || !newLabel.trim()) return;
    setAddLoading(true);
    try {
      await request("/api/v1/watchlists", {
        method: "POST",
        body: JSON.stringify({
          address: newAddress.trim(),
          label: newLabel.trim(),
          category: newCategory,
          severity: newSeverity,
          notes: newNotes.trim() || undefined
        })
      });
      setNewAddress("");
      setNewLabel("");
      setNewNotes("");
      setShowAdd(false);
      await loadWatchlist();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add entry");
    } finally {
      setAddLoading(false);
    }
  }

  return (
    <section className="panel watchlist-panel">
      <div className="panel-title">
        <Shield size={18} />
        Watchlist
        {stats && <span className="watchlist-count">({stats.total_entries})</span>}
      </div>

      {stats && (
        <div className="watchlist-stats">
          {Object.entries(stats.by_severity).map(([sev, count]) => (
            <span key={sev} className={`tag ${sev}`}>
              {sev}: {count}
            </span>
          ))}
        </div>
      )}

      <button className="secondary-button" onClick={() => setShowAdd(!showAdd)}>
        <Plus size={16} />
        {showAdd ? "Cancel" : "Add Entry"}
      </button>

      {showAdd && (
        <div className="watchlist-add-form">
          <label>
            <span>Address</span>
            <input
              value={newAddress}
              onChange={(e) => setNewAddress(e.target.value)}
              placeholder="0x..."
              spellCheck={false}
            />
          </label>
          <label>
            <span>Label</span>
            <input
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              placeholder="Entity name"
            />
          </label>
          <label>
            <span>Category</span>
            <select value={newCategory} onChange={(e) => setNewCategory(e.target.value)}>
              <option value="sanctions">Sanctions</option>
              <option value="pep">PEP</option>
              <option value="stablecoin_blacklist">Stablecoin Blacklist</option>
              <option value="mixer">Mixer</option>
              <option value="exchange">Exchange</option>
              <option value="other">Other</option>
            </select>
          </label>
          <label>
            <span>Severity</span>
            <select value={newSeverity} onChange={(e) => setNewSeverity(e.target.value)}>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </label>
          <label>
            <span>Notes (optional)</span>
            <input
              value={newNotes}
              onChange={(e) => setNewNotes(e.target.value)}
              placeholder="Additional context"
            />
          </label>
          <button className="primary-button" onClick={addEntry} disabled={addLoading}>
            {addLoading ? <Loader2 className="spin" size={16} /> : <Plus size={16} />}
            Add to Watchlist
          </button>
        </div>
      )}

      {error && (
        <div className="inline-error">
          <AlertTriangle size={14} />
          <span>{error}</span>
        </div>
      )}

      {loading && (
        <div className="watchlist-skeleton">
          <div className="skeleton-line w80" />
          <div className="skeleton-line w60" />
          <div className="skeleton-line w90" />
        </div>
      )}

      {!loading && entries.length === 0 && (
        <div className="empty-state">
          <Search size={24} />
          <p>Watchlist is empty. Add addresses to monitor.</p>
        </div>
      )}

      {!loading && entries.length > 0 && (
        <div className="watchlist-entries">
          {entries.slice(0, 20).map((entry) => (
            <article key={entry.address} className={`watchlist-entry ${entry.severity}`}>
              <div className="watchlist-entry-header">
                <strong>{entry.label}</strong>
                <span className={`tag ${entry.severity}`}>{entry.severity}</span>
              </div>
              <code title={entry.address}>{compactAddress(entry.address)}</code>
              <span className="watchlist-category">{entry.category}</span>
              {entry.notes && <p className="watchlist-notes">{entry.notes}</p>}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function buildStats(entries: WatchlistEntry[]): WatchlistStats {
  const bySeverity: Record<string, number> = {};
  const byCategory: Record<string, number> = {};
  for (const entry of entries) {
    bySeverity[entry.severity] = (bySeverity[entry.severity] ?? 0) + 1;
    byCategory[entry.category] = (byCategory[entry.category] ?? 0) + 1;
  }
  return {
    total_entries: entries.length,
    by_severity: bySeverity,
    by_category: byCategory
  };
}
