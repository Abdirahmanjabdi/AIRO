"use client";

import CountUp from 'react-countup';
import './Hero.css';

interface CapitalSavedHeroProps {
  amount: number;
}

export default function CapitalSavedHero({ amount }: CapitalSavedHeroProps) {
  return (
    <div className="hero-container animate-slide-up">
      <div className="hero-label">Total Capital Saved</div>
      <div className="hero-amount-wrapper">
        <span className="hero-currency text-neon-mint">$</span>
        <CountUp
          start={0}
          end={amount}
          duration={2.5}
          decimals={2}
          separator=","
          className="hero-amount text-neon-mint"
        />
      </div>
      <div className="hero-subtitle">Secured by Hybrid Isolation Forest V5</div>
    </div>
  );
}
