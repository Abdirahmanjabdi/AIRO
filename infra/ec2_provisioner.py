import os
import logging
import boto3

logger = logging.getLogger(__name__)

def provision_sentinel_ec2(instance_name: str, key_name: str) -> str:
    """
    Provision a high-capacity single-node EC2 instance for hosting isolated MT5 clients in Portable Mode.
    Installs Vault, Redis, PostgreSQL, and sets up Master and User directory boundaries.
    """
    logger.info("Initializing AWS EC2 single-node deployment sequence...")
    ec2 = boto3.resource("ec2", region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
    
    # UserData powershell script to boot, install dependencies via Chocolatey, and configure templates
    user_data = """<powershell>
    New-Item -ItemType Directory -Force -Path "C:\\Sentinel\\Master_MT5"
    New-Item -ItemType Directory -Force -Path "C:\\Sentinel\\Users"
    
    # Download MetaTrader 5 terminal installer
    Invoke-WebRequest -Uri "https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe" -OutFile "C:\\Sentinel\\mt5setup.exe"
    
    # Execute quiet install into the designated Master MT5 directory
    Start-Process -FilePath "C:\\Sentinel\\mt5setup.exe" -ArgumentList "/auto", "/path:C:\\Sentinel\\Master_MT5" -Wait
    
    # Intialize Chocolatey packages
    Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    
    # Install structural database, cache, and secrets managers
    choco install postgresql redis-64-bit hashicorp-vault -y
    
    # Set Services to start automatically on system boot
    Set-Service -Name "postgresql-x64-16" -StartupType Automatic
    Set-Service -Name "redis-server" -StartupType Automatic
    
    Start-Service -Name "postgresql-x64-16"
    Start-Service -Name "redis-server"
    
    logger.info("EC2 dynamic services deployment sequence complete.")
    </powershell>"""

    try:
        instances = ec2.create_instances(
            ImageId="ami-0fc5d935ebf8bc3bc",  # Windows Server 2025 Base AMI
            InstanceType="t3.xlarge",          # 4 vCPUs, 16 GB Ram - supports 50-150 isolated clients
            KeyName=key_name,
            MinCount=1,
            MaxCount=1,
            UserData=user_data,
            TagSpecifications=[{
                "ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": instance_name}]
            }]
        )
        
        instance = instances[0]
        logger.info(f"EC2 Instance created. ID: {instance.id}. Waiting for boot sequence...")
        instance.wait_until_running()
        instance.reload()
        logger.info(f"EC2 single-node deployment online. Public DNS: {instance.public_dns_name}")
        return str(instance.public_dns_name)
    except Exception as exc:
        logger.error(f"Failed to provision Sentinel EC2 node: {exc}")
        raise
