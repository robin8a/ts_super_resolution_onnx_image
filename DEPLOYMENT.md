# Super Resolution Lambda Function

This Lambda function applies super-resolution to multi-band TIF images and outputs high-resolution TIF files with preserved geospatial metadata.

## Function Overview

- **Input**: Multi-band TIF file from S3
- **Processing**: Applies super-resolution to RGB bands extracted from multi-band image
- **Output**: High-resolution TIF file with pattern `super_resolution_<original_name>.tif` in S3
- **Metadata**: Preserves geospatial metadata (CRS, transform, bounds)

## Event Format

```json
{
    "bucket": "your-input-bucket-name",
    "key": "path/to/your/file.tif",
    "model_bucket": "your-model-bucket",
    "sr_model_key": "models/satlas_sr.onnx",
    "output_bucket": "your-output-bucket",
    "output_key_prefix": "processed/",
    "use_unet": false,
    "band_indices": [0, 1, 2]
}
```

### Event Parameters

- `bucket` (required): S3 bucket name with input TIF file
- `key` (required): S3 key of input TIF file
- `model_bucket` (required): S3 bucket containing ONNX models
- `sr_model_key` (required): S3 key of super-resolution ONNX model (e.g., "satlas_sr.onnx")
- `output_bucket` (required): S3 bucket for output TIF file
- `output_key_prefix` (optional): Prefix for output key in S3
- `use_unet` (optional): Boolean to use unet_model.onnx instead (default: false)
- `band_indices` (optional): List of band indices to extract as RGB (default: [0, 1, 2])

## Deployment Instructions

### Prerequisites

- Docker installed
- AWS CLI configured with `suan-blockchain` profile
- Access to ECR repository

### 1. Build Docker Image

```bash
cd /Users/robinochoa/Documents/serverless_ws/ts_super_resolution_onnx_image
docker build -t ts_super_resolution_onnx_image .
```

### 2. Login to ECR

```bash
aws ecr get-login-password --region us-east-1 --profile suan-blockchain | docker login --username AWS --password-stdin 036134507423.dkr.ecr.us-east-1.amazonaws.com
```

### 3. Create ECR Repository

```bash
aws ecr create-repository --repository-name ts_super_resolution_onnx_image --region us-east-1 --profile suan-blockchain
```

Expected output:

```json
{
    "repository": {
        "repositoryArn": "arn:aws:ecr:us-east-1:036134507423:repository/ts_super_resolution_onnx_image",
        "registryId": "036134507423",
        "repositoryName": "ts_super_resolution_onnx_image",
        "repositoryUri": "036134507423.dkr.ecr.us-east-1.amazonaws.com/ts_super_resolution_onnx_image",
        "createdAt": "2025-01-XX...",
        "imageTagMutability": "MUTABLE",
        "imageScanningConfiguration": {
            "scanOnPush": false
        },
        "encryptionConfiguration": {
            "encryptionType": "AES256"
        }
    }
}
```

### 4. Tag and Push Image

```bash
docker tag ts_super_resolution_onnx_image:latest 036134507423.dkr.ecr.us-east-1.amazonaws.com/ts_super_resolution_onnx_image:latest

docker push 036134507423.dkr.ecr.us-east-1.amazonaws.com/ts_super_resolution_onnx_image:latest
```

### 5. Create Lambda Function

```bash
aws lambda create-function \
    --function-name TSSuperResolutionFunction \
    --package-type Image \
    --code ImageUri=036134507423.dkr.ecr.us-east-1.amazonaws.com/ts_super_resolution_onnx_image:latest \
    --role arn:aws:iam::036134507423:role/ts-lambda-biomass-execution-role \
    --timeout 120 \
    --memory-size 3008 \
    --region us-east-1 \
    --profile suan-blockchain
```

### 6. Test the Function

```bash
aws lambda invoke \
    --function-name TSSuperResolutionFunction \
    --cli-binary-format raw-in-base64-out \
    --payload '{"bucket": "your-bucket", "key": "path/to/file.tif", "model_bucket": "model-bucket", "sr_model_key": "satlas_sr.onnx", "output_bucket": "output-bucket"}' \
    output.json \
    --profile suan-blockchain
```

Example with specific bucket:

```bash
aws lambda invoke \
    --function-name TSSuperResolutionFunction \
    --cli-binary-format raw-in-base64-out \
    --payload '{"bucket": "tsbiomassmodeldata", "key": "test_image.tif", "model_bucket": "tsbiomassmodeldata", "sr_model_key": "model/satlas_sr.onnx", "output_bucket": "tsbiomassmodeldata", "output_key_prefix": "super_resolution/"}' \
    output.json \
    --profile suan-blockchain
```

## Update Function Code

To update the function with new code:

```bash
# After rebuilding the image and pushing to ECR
aws lambda update-function-code \
    --function-name TSSuperResolutionFunction \
    --image-uri 036134507423.dkr.ecr.us-east-1.amazonaws.com/ts_super_resolution_onnx_image:latest \
    --profile suan-blockchain
```

## Response Format

### Success Response

```json
{
    "statusCode": 200,
    "body": {
        "message": "Super-resolution applied successfully",
        "input_location": "s3://bucket/input.tif",
        "output_location": "s3://bucket/super_resolution_input.tif",
        "scale_factor": 4.0
    }
}
```

### Error Response

```json
{
    "statusCode": 400,
    "body": "Error: Missing key in event object: 'bucket'. Event must contain 'bucket', 'key', 'model_bucket', 'sr_model_key', and 'output_bucket'."
}
```

## Technical Details

### Super-Resolution Configuration

- **Tile Size**: 32x32 pixels (TILE_LR_SIZE)
- **Padding**: 4 pixels (PAD_LR_PIXELS)
- **Preprocessing Mode**: "zero_one" (normalized to 0-1 range)
- **Scale Factor**: Detected automatically from model output

### Output Naming

Output files follow the pattern:
```
super_resolution_<original_filename_without_extension>.tif
```

For example, if input is `image_2023.tif`, output will be `super_resolution_image_2023.tif`.

### Metadata Preservation

The function preserves all geospatial metadata from the input TIF:
- Coordinate Reference System (CRS)
- Transform matrix (updated for higher resolution)
- Geographic bounds
- Data type and profile information

## Notes

- The function extracts RGB bands from multi-band TIF files
- Band selection can be customized via `band_indices` parameter
- Both satlas_sr.onnx and unet_model.onnx are supported
- Output resolution is automatically scaled based on model capabilities
- All temporary files are cleaned up after processing


