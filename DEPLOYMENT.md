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

**Important:** When building on macOS or other non-Linux platforms, use the `--platform linux/amd64` flag to ensure compatibility with Lambda's Linux environment:

```bash
cd /Users/robinochoa/Documents/serverless_ws/ts_super_resolution_onnx_image
docker build --platform linux/amd64 -t ts_super_resolution_onnx_image .
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

Output:

```sh
{
    "repository": {
        "repositoryArn": "arn:aws:ecr:us-east-1:036134507423:repository/ts_super_resolution_onnx_image",
        "registryId": "036134507423",
        "repositoryName": "ts_super_resolution_onnx_image",
        "repositoryUri": "036134507423.dkr.ecr.us-east-1.amazonaws.com/ts_super_resolution_onnx_image",
        "createdAt": "2025-10-27T08:41:20.249000-05:00",
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
    --function-name TSSuperResolutionONNXImageFunction \
    --package-type Image \
    --code ImageUri=036134507423.dkr.ecr.us-east-1.amazonaws.com/ts_super_resolution_onnx_image:latest \
    --role arn:aws:iam::036134507423:role/ts-lambda-biomass-execution-role \
    --timeout 120 \
    --memory-size 3008 \
    --region us-east-1 \
    --profile suan-blockchain
```

Output: 

```sh
{
    "FunctionName": "TSSuperResolutionONNXImageFunction",
    "FunctionArn": "arn:aws:lambda:us-east-1:036134507423:function:TSSuperResolutionONNXImageFunction",
    "Role": "arn:aws:iam::036134507423:role/ts-lambda-biomass-execution-role",
    "CodeSize": 0,
    "Description": "",
    "Timeout": 120,
    "MemorySize": 3008,
    "LastModified": "2025-10-27T14:15:58.505+0000",
    "CodeSha256": "97f274bdcd39980dec2c753b66e127757586151756320bae8b7078b34dc82172",
    "Version": "$LATEST",
    "TracingConfig": {
        "Mode": "PassThrough"
    },
    "RevisionId": "2f02e434-5163-4599-a81e-557ffc38c0f7",
    "State": "Pending",
    "StateReason": "The function is being created.",
    "StateReasonCode": "Creating",
    "PackageType": "Image",
    "Architectures": [
        "x86_64"
    ],
    "EphemeralStorage": {
        "Size": 512
    },
    "SnapStart": {
        "ApplyOn": "None",
        "OptimizationStatus": "Off"
    }
}
```

### 6. Test the Function

```bash
aws lambda invoke \
    --function-name TSSuperResolutionONNXImageFunction \
    --cli-binary-format raw-in-base64-out \
    --payload '{"bucket": "your-bucket", "key": "path/to/file.tif", "model_bucket": "model-bucket", "sr_model_key": "satlas_sr.onnx", "output_bucket": "output-bucket"}' \
    output.json \
    --profile suan-blockchain
```

Example with specific bucket:

```bash
aws lambda invoke \
    --function-name TSSuperResolutionONNXImageFunction \
    --cli-binary-format raw-in-base64-out \
    --payload '{"bucket": "tsbiomassmodeldata", "key": "test_image.tif", "model_bucket": "tsbiomassmodeldata", "sr_model_key": "model/satlas_sr.onnx", "output_bucket": "tsbiomassmodeldata", "output_key_prefix": "super_resolution/"}' \
    output.json \
    --profile suan-blockchain
```

Test

```sh
aws lambda invoke \
    --function-name TSSuperResolutionONNXImageFunction \
    --cli-binary-format raw-in-base64-out \
    --payload '{"bucket": "tsbiomassmodeldata", "key": "biomass_map_img__20251016212350__S2__B4_B3_B2__2023_01_28__2336.tif", "model_bucket": "tsbiomassmodeldata", "sr_model_key": "model/satlas_sr.onnx", "output_bucket": "tsbiomassmodeldata", "output_key_prefix": "super_resolution/"}' \
    output.json \
    --profile suan-blockchain
```

## Update Function Code

To update the function with new code:

```bash
# 1. Rebuild the Docker image (use --platform linux/amd64 on macOS)
docker build --platform linux/amd64 -t ts_super_resolution_onnx_image .

# 2. Tag the image
docker tag ts_super_resolution_onnx_image:latest 036134507423.dkr.ecr.us-east-1.amazonaws.com/ts_super_resolution_onnx_image:latest

# 3. Login to ECR (if not already logged in)
aws ecr get-login-password --region us-east-1 --profile suan-blockchain | docker login --username AWS --password-stdin 036134507423.dkr.ecr.us-east-1.amazonaws.com

# 4. Push the updated image
docker push 036134507423.dkr.ecr.us-east-1.amazonaws.com/ts_super_resolution_onnx_image:latest

# 5. Update Lambda function with new code
aws lambda update-function-code \
    --function-name TSSuperResolutionONNXImageFunction \
    --image-uri 036134507423.dkr.ecr.us-east-1.amazonaws.com/ts_super_resolution_onnx_image:latest \
    --profile suan-blockchain

# 6. Wait for update to complete and test
aws lambda wait function-updated \
    --function-name TSSuperResolutionONNXImageFunction \
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

## Calling via API Gateway

The function is exposed via API Gateway at:

```
https://9e7wnzvwcb.execute-api.us-east-1.amazonaws.com/dev/util_super_resolution
```

### Using curl

```bash
curl -X POST https://9e7wnzvwcb.execute-api.us-east-1.amazonaws.com/dev/util_super_resolution \
  -H "Content-Type: application/json" \
  -d '{
    "bucket": "tsbiomassmodeldata",
    "key": "biomass_map_img__20251016212350__S2__B4_B3_B2__2023_01_28__2336.tif",
    "model_bucket": "tsbiomassmodeldata",
    "sr_model_key": "model/satlas_sr.onnx",
    "output_bucket": "tsbiomassmodeldata",
    "output_key_prefix": "super_resolution/"
  }'
```

### Using Python requests

```python
import requests
import json

url = "https://9e7wnzvwcb.execute-api.us-east-1.amazonaws.com/dev/util_super_resolution"

payload = {
    "bucket": "tsbiomassmodeldata",
    "key": "biomass_map_img__20251016212350__S2__B4_B3_B2__2023_01_28__2336.tif",
    "model_bucket": "tsbiomassmodeldata",
    "sr_model_key": "model/satlas_sr.onnx",
    "output_bucket": "tsbiomassmodeldata",
    "output_key_prefix": "super_resolution/",
    "use_unet": False,
    "band_indices": [0, 1, 2]
}

response = requests.post(url, json=payload)
print(f"Status Code: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
```

### Using JavaScript/Node.js

```javascript
const axios = require('axios');

const url = 'https://9e7wnzvwcb.execute-api.us-east-1.amazonaws.com/dev/util_super_resolution';

const payload = {
  bucket: 'tsbiomassmodeldata',
  key: 'biomass_map_img__20251016212350__S2__B4_B3_B2__2023_01_28__2336.tif',
  model_bucket: 'tsbiomassmodeldata',
  sr_model_key: 'model/satlas_sr.onnx',
  output_bucket: 'tsbiomassmodeldata',
  output_key_prefix: 'super_resolution/'
};

axios.post(url, payload)
  .then(response => {
    console.log('Status Code:', response.status);
    console.log('Response:', JSON.stringify(response.data, null, 2));
  })
  .catch(error => {
    console.error('Error:', error.response ? error.response.data : error.message);
  });
```

### Using JavaScript Fetch (Browser)

```javascript
const url = 'https://9e7wnzvwcb.execute-api.us-east-1.amazonaws.com/dev/util_super_resolution';

const payload = {
  bucket: 'tsbiomassmodeldata',
  key: 'biomass_map_img__20251016212350__S2__B4_B3_B2__2023_01_28__2336.tif',
  model_bucket: 'tsbiomassmodeldata',
  sr_model_key: 'model/satlas_sr.onnx',
  output_bucket: 'tsbiomassmodeldata',
  output_key_prefix: 'super_resolution/'
};

fetch(url, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(payload)
})
  .then(response => response.json())
  .then(data => {
    console.log('Response:', data);
  })
  .catch(error => {
    console.error('Error:', error);
  });
```

### API Gateway Response Format

The API Gateway endpoint will return the Lambda response wrapped in an API Gateway response format:

**Success (200 OK):**
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

**Error (400 Bad Request):**
```json
{
  "statusCode": 400,
  "body": "Error: Missing key in event object: 'bucket'. Event must contain 'bucket', 'key', 'model_bucket', 'sr_model_key', and 'output_bucket'."
}
```

**Error (500 Internal Server Error):**
```json
{
  "statusCode": 500,
  "body": "Error processing request: <error details>"
}
```

### Important Notes

- **HTTP Method**: POST
- **Content-Type**: application/json
- **Timeout**: The Lambda function has a 120 second timeout, which should be sufficient for most image processing tasks
- **Asynchronous**: The function processes images asynchronously. Large images may take time to process
- **CORS**: If calling from a browser, ensure CORS is properly configured on the API Gateway endpoint

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

## Troubleshooting

### Common Errors

#### 1. Numpy Import Error

**Error:**
```
Runtime.ImportModuleError: numpy.core.multiarray failed to import
```

**Solution:**
This error occurs with numpy 2.0+ or when building Docker images on non-Linux platforms. The `requirements.txt` has been fixed to use numpy 1.26.4. Rebuild and redeploy with the correct platform:

```bash
# Rebuild the Docker image with linux/amd64 platform (important on macOS)
docker build --platform linux/amd64 -t ts_super_resolution_onnx_image .

# Tag and push
docker tag ts_super_resolution_onnx_image:latest 036134507423.dkr.ecr.us-east-1.amazonaws.com/ts_super_resolution_onnx_image:latest
docker push 036134507423.dkr.ecr.us-east-1.amazonaws.com/ts_super_resolution_onnx_image:latest

# Update Lambda
aws lambda update-function-code \
    --function-name TSSuperResolutionONNXImageFunction \
    --image-uri 036134507423.dkr.ecr.us-east-1.amazonaws.com/ts_super_resolution_onnx_image:latest \
    --profile suan-blockchain
```

#### 2. Timeout Errors

**Error:** Function times out after 120 seconds

**Solution:** Increase the timeout in Lambda configuration:

```bash
aws lambda update-function-configuration \
    --function-name TSSuperResolutionONNXImageFunction \
    --timeout 300 \
    --profile suan-blockchain
```

#### 3. Memory Issues

**Error:** Out of memory errors

**Solution:** Increase memory allocation:

```bash
aws lambda update-function-configuration \
    --function-name TSSuperResolutionONNXImageFunction \
    --memory-size 5120 \
    --profile suan-blockchain
```

Note: Lambda supports up to 10,240 MB (10 GB) memory.

#### 4. S3 Permission Errors

**Error:** Access denied when accessing S3 buckets

**Solution:** Ensure the Lambda execution role has the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::input-bucket/*",
        "arn:aws:s3:::output-bucket/*",
        "arn:aws:s3:::model-bucket/*"
      ]
    }
  ]
}
```

#### 5. Model Not Found

**Error:** Model file not found in S3

**Solution:** Verify the model exists in the specified bucket and path:

```bash
aws s3 ls s3://model-bucket/model/satlas_sr.onnx --profile suan-blockchain
```
