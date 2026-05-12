import re

with open('docker-compose.yml', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(
    r'      dockerfile: infra/docker/Dockerfile\.brain\s*ports:', 
    '      dockerfile: infra/docker/Dockerfile.brain\n    deploy:\n      resources:\n        limits:\n          cpus: "2.0"\n    ports:', 
    content
)
                 
content = re.sub(
    r'      dockerfile: infra/docker/Dockerfile\.mt5\s*environment:',
    '      dockerfile: infra/docker/Dockerfile.mt5\n    deploy:\n      resources:\n        limits:\n          cpus: "1.0"\n          memory: "2G"\n    environment:', 
    content
)
                 
with open('docker-compose.yml', 'w', encoding='utf-8') as f:
    f.write(content)
