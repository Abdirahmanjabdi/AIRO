"use client";

import { useState, useEffect } from 'react';
import { Network, Database, BrainCircuit, CheckCircle2 } from 'lucide-react';
import './Card.css';

export default function BrokerConnectCard({ onConnected }: { onConnected: () => void }) {
  const [stage, setStage] = useState<'IDLE' | 'STAGE1' | 'STAGE2' | 'STAGE3' | 'READY'>('IDLE');
  
  // Form State
  const [server, setServer] = useState('ICMarkets-Demo');
  const [accountId, setAccountId] = useState('98765432');
  const [password, setPassword] = useState('********');

  const handleConnect = (e: React.FormEvent) => {
    e.preventDefault();
    setStage('STAGE1');
  };

  // Simulate the polling progression for the 202 Async BackgroundTask
  useEffect(() => {
    let timer: NodeJS.Timeout;
    
    if (stage === 'STAGE1') {
      timer = setTimeout(() => setStage('STAGE2'), 2500); // Wait for broker connection
    } else if (stage === 'STAGE2') {
      timer = setTimeout(() => setStage('STAGE3'), 3000); // Polling historical trades
    } else if (stage === 'STAGE3') {
      timer = setTimeout(() => {
        setStage('READY');
        setTimeout(() => onConnected(), 1500); // Deploy animation delay
      }, 4000); // Calibrating Isolation Forest
    }

    return () => clearTimeout(timer);
  }, [stage, onConnected]);

  return (
    <div className="broker-card glass-panel animate-slide-up">
      <div className="card-header">
        <h2>Sentinel Configuration</h2>
        <p>Connect your MT5 account to initialize the AIRO baseline.</p>
      </div>

      {stage === 'IDLE' ? (
        <form className="connect-form" onSubmit={handleConnect}>
          <div className="form-group">
            <label>MT5 Server</label>
            <input 
              type="text" 
              value={server} 
              onChange={(e) => setServer(e.target.value)} 
              required 
            />
          </div>
          <div className="form-group">
            <label>Account ID</label>
            <input 
              type="number" 
              value={accountId} 
              onChange={(e) => setAccountId(e.target.value)} 
              required 
            />
          </div>
          <div className="form-group">
            <label>Read-Only Password</label>
            <input 
              type="password" 
              value={password} 
              onChange={(e) => setPassword(e.target.value)} 
              required 
            />
          </div>
          
          <button type="submit" className="glow-btn connect-submit">
            Initialize Baseline
          </button>
        </form>
      ) : (
        <div className="stepper-container">
          <div className={`step ${stage === 'STAGE1' ? 'active' : 'completed'}`}>
            {stage === 'STAGE1' ? <Network className="spin-slow text-neon-mint" /> : <CheckCircle2 className="text-neon-mint" />}
            <span>Connecting to Broker LD4 Node...</span>
          </div>
          
          <div className={`step-connector ${stage !== 'STAGE1' ? 'active' : ''}`} />
          
          <div className={`step ${stage === 'STAGE2' ? 'active' : stage === 'STAGE3' || stage === 'READY' ? 'completed' : 'pending'}`}>
            {stage === 'STAGE2' ? <Database className="pulse text-blue" /> : stage === 'STAGE3' || stage === 'READY' ? <CheckCircle2 className="text-neon-mint" /> : <Database className="text-muted" />}
            <span>Auditing 150 historical trades...</span>
          </div>
          
          <div className={`step-connector ${stage === 'STAGE3' || stage === 'READY' ? 'active' : ''}`} />
          
          <div className={`step ${stage === 'STAGE3' ? 'active' : stage === 'READY' ? 'completed' : 'pending'}`}>
            {stage === 'STAGE3' ? <BrainCircuit className="pulse text-blue" /> : stage === 'READY' ? <CheckCircle2 className="text-neon-mint" /> : <BrainCircuit className="text-muted" />}
            <span>Calibrating V5 Hybrid Isolation Forest...</span>
          </div>

          <div className="stepper-status">
            {stage === 'READY' ? (
              <span className="text-neon-mint animate-pulse">Baseline Ready. Deploying Dashboard...</span>
            ) : (
              <span className="text-muted">Synchronizing with Sentinel-Brain...</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
