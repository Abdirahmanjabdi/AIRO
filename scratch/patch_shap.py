import os

file_path = r"c:\Users\jamaa\OneDrive\Documenti\SentinelTrading\frontend\src\components\SHAPHoverCard.tsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

props_target = """interface SHAPHoverCardProps {
  children: React.ReactNode;
  explanation: FeatureContribution[];
}

export default function SHAPHoverCard({ children, explanation }: SHAPHoverCardProps) {"""

props_replacement = """interface SHAPHoverCardProps {
  children: React.ReactNode;
  explanation: FeatureContribution[];
  contamination?: number;
}

export default function SHAPHoverCard({ children, explanation, contamination = 0.0399 }: SHAPHoverCardProps) {"""
content = content.replace(props_target, props_replacement)

render_target = """          </div>
        </div>
      </HoverCardContent>"""

render_replacement = """          </div>
          
          <div className="pt-3 mt-2 border-t border-border/50 text-[10px] text-muted-foreground font-mono bg-background/20 p-2 rounded-sm">
            <div className="text-secondary font-bold mb-1">MATH UNDERPINNING</div>
            <div>Isolation Forest Contamination: {contamination.toFixed(4)}</div>
            <div className="mt-1 leading-4 text-foreground/60">
              The anomaly threshold is derived dynamically. If the aggregated SHAP force pushes the decision boundary beyond the {contamination * 100}% statistical threshold, the intervention gate is triggered.
            </div>
          </div>
        </div>
      </HoverCardContent>"""
content = content.replace(render_target, render_replacement)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("SHAPHoverCard.tsx patched successfully!")
