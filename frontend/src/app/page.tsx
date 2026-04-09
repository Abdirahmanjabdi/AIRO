"use client";

import { useState } from 'react';
import BrokerConnectCard from '@/components/BrokerConnectCard';
import CapitalSavedHero from '@/components/CapitalSavedHero';
import InterventionLogFeed from '@/components/InterventionLogFeed';
import RiskStatusBadge from '@/components/RiskStatusBadge';

import './page.css';

export default function Dashboard() {
  const [isConnected, setIsConnected] = useState(false);

  return (
    <div className="dashboard-layout">
      {/* Top Header Row for Desktop, Sticky Header for Mobile */}
      <header className="dashboard-header">
        <div className="header-brand text-neon-mint">Sentinel AIRO</div>
        <div className="header-status">
          <RiskStatusBadge status={isConnected ? 'ACTIVE' : 'RISK_OFF'} />
        </div>
      </header>

      <main className={`dashboard-main ${!isConnected ? 'centered' : ''}`}>
        {!isConnected ? (
          <div className="onboarding-wrapper">
            <BrokerConnectCard onConnected={() => setIsConnected(true)} />
          </div>
        ) : (
          <div className="dashboard-grid animate-slide-up">
            
            {/* Sidebar Desktop / Settings Modal Mobile */}
            <aside className="dashboard-sidebar">
              <div className="sidebar-card glass-panel">
                <h4>Broker Config</h4>
                <p className="text-muted text-sm mt-2">ICMarkets-Demo</p>
                <p className="text-primary text-sm mt-1">Acct: 98765432</p>
                <button className="glow-btn mt-4" style={{width: '100%', padding: '8px'}} onClick={() => setIsConnected(false)}>
                  Disconnect
                </button>
              </div>
            </aside>

            {/* Central Content */}
            <div className="dashboard-content">
              {/* Capital Saved Hero - Top Left Desktop / Center Top Mobile */}
              <section className="hero-section">
                <CapitalSavedHero amount={8452.50} />
              </section>

              {/* Intervention Log Feed - Main Central Desktop / Bottom Sheet Mobile */}
              <section className="log-section">
                <InterventionLogFeed />
              </section>
            </div>
            
          </div>
        )}
      </main>

      {/* Mobile Fixed Navigation Indicator */}
      <div className="mobile-fixed-nav glass-panel">
         <RiskStatusBadge status={isConnected ? 'ACTIVE' : 'RISK_OFF'} />
      </div>
    </div>
  );
}
