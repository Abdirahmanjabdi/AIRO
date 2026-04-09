"use client";

import { Minimize2, AlertOctagon } from 'lucide-react';
import './Feed.css';

interface Intervention {
  id: string;
  time: string;
  action: 'REDUCE_SIZE' | 'BLOCK';
  reason: string;
  saved: number;
}

const MOCK_DATA: Intervention[] = [
  { id: '1', time: '10:45:02 AM', action: 'REDUCE_SIZE', reason: 'Lot size reduced 3.0 → 1.5 (Risk: Revenge Trading)', saved: 450.00 },
  { id: '2', time: '09:12:14 AM', action: 'BLOCK', reason: 'Trade Blocked (Risk: Extreme Drawdown Deviation)', saved: 1200.00 },
  { id: '3', time: 'Yesterday', action: 'REDUCE_SIZE', reason: 'Lot size reduced 1.0 → 0.25 (Risk: Max Losing Streak)', saved: 75.50 },
];

export default function InterventionLogFeed() {
  return (
    <div className="feed-container glass-panel animate-slide-up" style={{ animationDelay: '0.2s' }}>
      <div className="feed-header">
        <h3>Intervention Audit Log</h3>
        <span className="feed-count">{MOCK_DATA.length} Events</span>
      </div>
      
      <div className="feed-list">
        {MOCK_DATA.map((log) => (
          <div key={log.id} className="feed-item">
            <div className="feed-icon-wrapper">
              {log.action === 'REDUCE_SIZE' ? (
                <Minimize2 size={20} className="text-blue" />
              ) : (
                <AlertOctagon size={20} className="text-error" />
              )}
            </div>
            <div className="feed-content">
              <div className="feed-details">
                <span className="feed-reason">{log.reason}</span>
                <span className="feed-time">{log.time}</span>
              </div>
              <div className="feed-saved text-neon-mint">
                +${log.saved.toFixed(2)}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
