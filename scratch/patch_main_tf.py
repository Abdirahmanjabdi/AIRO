import os

file_path = r"c:\Users\jamaa\OneDrive\Documenti\SentinelTrading\infra\terraform\main.tf"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}"""

replacement = """  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "models" {
  bucket = aws_s3_bucket.models.id

  rule {
    id     = "intelligent-tiering"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "INTELLIGENT_TIERING"
    }
  }
}"""

content = content.replace(target, replacement)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patch S3 Lifecycle Rule successful!")
