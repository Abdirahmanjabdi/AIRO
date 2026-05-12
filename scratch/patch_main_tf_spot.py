import os

file_path = r"c:\Users\jamaa\OneDrive\Documenti\SentinelTrading\infra\terraform\main.tf"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """      disk_size      = 20
      capacity_type  = "ON_DEMAND"

      labels = {
        workload = "mt5"
      }"""

replacement = """      disk_size      = 20
      capacity_type  = "SPOT"

      labels = {
        workload = "mt5"
      }"""

content = content.replace(target, replacement)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patch SPOT capacity_type successful!")
