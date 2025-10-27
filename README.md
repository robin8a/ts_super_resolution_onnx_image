# Super Resolution Lambda Function

AWS Lambda function that applies super-resolution to multi-band TIF images using ONNX models.

## Overview

This Lambda function:
- Downloads multi-band TIF files from S3
- Extracts RGB bands from the multi-band image
- Applies super-resolution using ONNX models (satlas_sr.onnx or unet_model.onnx)
- Saves high-resolution TIF with preserved geospatial metadata
- Uploads result to S3 with naming pattern: `super_resolution_<original_name>.tif`

## Features

- Preserves geospatial metadata (CRS, transform, bounds)
- Supports multiple ONNX models (satlas_sr and unet)
- Configurable band selection for RGB extraction
- Automatic scale factor detection
- Memory-efficient tiling approach
- Error handling and cleanup

## Files

- `lambda_function.py` - Main Lambda handler with super-resolution logic
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container configuration with GDAL support
- `DEPLOYMENT.md` - Detailed deployment and usage guide
- `lambda_event.json` - Example event for testing
- `model/` - Directory containing ONNX models

## Quick Start

See `DEPLOYMENT.md` for detailed deployment instructions.

## Dependencies

- numpy - Numerical operations
- opencv-python-headless - Image processing
- onnxruntime - ONNX model inference
- scikit-learn - Data normalization
- boto3 - AWS S3 integration
- rasterio - Geospatial TIF handling

## Configuration

Key configuration parameters in `lambda_function.py`:
- `TILE_LR_SIZE`: Tile size for processing (default: 32)
- `PAD_LR_PIXELS`: Padding pixels (default: 4)
- `SR_PREPROC_MODE`: Preprocessing mode (default: "zero_one")
- `SR_OUTPUT_PREFIX`: Output filename prefix (default: "super_resolution")


