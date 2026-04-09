"use client";

import { Activity, ShieldCheck, AlertTriangle } from 'lucide-react';
import './Badge.css';

interface RiskStatusBadgeProps {
  status: 'ACTIVE' | 'TRAINING' | 'RISK_OFF';
}

export default function RiskStatusBadge({ status }: RiskStatusBadgeProps) {
  const getStatusConfig = () => {
    switch (status) {
      case 'ACTIVE':
        return {
          icon: <ShieldCheck size={16} className="text-neon-mint animate-pulse" />,
          label: 'AIRO Active',
          className: 'badge-active'
        };
      case 'TRAINING':
        return {
          icon: <Activity size={16} className="badge-icon-spin" />,
          label: 'Calibrating V5 Baseline',
          className: 'badge-training'
        };
      case 'RISK_OFF':
        return {
          icon: <AlertTriangle size={16} />,
          label: 'System Risk-Off',
          className: 'badge-error'
        };
      default:
        return {
          icon: <Activity size={16} />,
          label: 'Unknown',
          className: 'badge-unknown'
        };
    }
  };

  const config = getStatusConfig();

  return (
    <div className={`status-badge glass-panel ${config.className}`}>
      {config.icon}
      <span>{config.label}</span>
    </div>
  );
}
