"use client";

import { motion } from "framer-motion";
import CountUp from "react-countup";
import "./Hero.css";

interface CapitalSavedHeroProps {
  amount: number;
}

export default function CapitalSavedHero({ amount }: CapitalSavedHeroProps) {
  return (
    <motion.div
      className="hero-container animate-slide-up"
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
    >
      <motion.div
        className="hero-signal"
        animate={{ scale: [1, 1.08, 1], opacity: [0.45, 0.9, 0.45] }}
        transition={{ repeat: Number.POSITIVE_INFINITY, duration: 3.2, ease: "easeInOut" }}
      />
      <motion.div
        className="hero-label"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1, duration: 0.5 }}
      >
        Total Capital Saved
      </motion.div>
      <motion.div
        className="hero-amount-wrapper"
        animate={{ boxShadow: ["0 0 0 rgba(0,255,163,0.1)", "0 0 36px rgba(0,255,163,0.22)", "0 0 0 rgba(0,255,163,0.1)"] }}
        transition={{ repeat: Number.POSITIVE_INFINITY, duration: 4.2, ease: "easeInOut" }}
      >
        <span className="hero-currency text-neon-mint">$</span>
        <CountUp
          start={0}
          end={amount}
          duration={2.5}
          decimals={2}
          separator=","
          className="hero-amount text-neon-mint"
        />
      </motion.div>
      <motion.div
        className="hero-subtitle"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.25, duration: 0.6 }}
      >
        Real-time mitigation running on your personalized baseline.
      </motion.div>
    </motion.div>
  );
}
