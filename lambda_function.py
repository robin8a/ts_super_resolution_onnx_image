import os
import numpy as np
import cv2
import onnxruntime as ort
from sklearn.preprocessing import MinMaxScaler
import boto3
import time
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.crs import CRS

# ===================== CONFIGURATION =====================
SELECTED_INDICES = [0, 1, 2, 3, 4, 18, 19]
EXTRA_IDX_FOR_UNET = [3, 4, 5, 6]
S1_IDX = (5, 6)
TILE_LR_SIZE   = 32
PAD_LR_PIXELS  = 4
SR_PREPROC_MODE = "zero_one"
UNET_PATCH     = 256
SR_OUTPUT_PREFIX = "super_resolution"

# ===================== HELPER FUNCTIONS =====================

def normalize_band_auto(b):
    """Normalize a single band to 0-1 range based on its data range."""
    b = b.astype(np.float32)
    valid = np.isfinite(b)
    if not valid.any():
        return np.zeros_like(b, dtype=np.float32)
    bmax = np.nanmax(b); bmin = np.nanmin(b)
    if bmax > 2000:
        out = np.clip(b / 10000.0, 0, 1)
    elif bmax > 1.5:
        out = np.clip(b / 255.0, 0, 1)
    else:
        p1, p99 = np.nanpercentile(b[valid], [1, 99])
        if p99 > p1:
            out = np.clip((b - p1) / (p99 - p1), 0, 1)
        else:
            out = np.clip(b, 0, 1)
    return out

def normalize_bands_auto(bands_chw, s1_idx=(5,6)):
    """Normalize multiple bands to 0-1 range."""
    nb = bands_chw.astype(np.float32).copy()
    C,H,W = nb.shape
    for c in range(C):
        if c in s1_idx:
            b = nb[c]; mask = np.isfinite(b)
            if mask.any():
                scaler = MinMaxScaler()
                nb[c][mask] = scaler.fit_transform(b[mask].reshape(-1,1)).reshape(b[mask].shape)
                nb[c][~mask] = 0.0
        else:
            nb[c] = normalize_band_auto(nb[c])
    return nb

def tile_image_array_indexed(arr_hw_c, tile_size=32):
    """Split image into indexed tiles."""
    H,W,C = arr_hw_c.shape
    assert H % tile_size == 0 and W % tile_size == 0, f"{H}x{W} no múltiplo de {tile_size}"
    ty, tx = H // tile_size, W // tile_size
    tiles = {}
    for r in range(ty):
        for c in range(tx):
            y, x = r*tile_size, c*tile_size
            tiles[(r,c)] = arr_hw_c[y:y+tile_size, x:x+tile_size, :].copy()
    return tiles, ty, tx

def reconstruct_from_indexed_tiles(tiles_dict, tiles_y, tiles_x):
    """Reconstruct image from indexed tiles."""
    sample = next(iter(tiles_dict.values()))
    th, tw, C = sample.shape
    H, W = th*tiles_y, tw*tiles_x
    out = np.zeros((H,W,C), dtype=sample.dtype)
    for (r,c), tile in tiles_dict.items():
        y, x = r*th, c*tw
        out[y:y+th, x:x+tw, :] = tile
    return out

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)

def sr_preprocess_rgb(tile_hw3: np.ndarray, mode: str = "zero_one") -> np.ndarray:
    """Preprocess RGB tile for super-resolution model."""
    x = tile_hw3.astype(np.float32)
    if mode == "zero_one":
        pass
    elif mode == "minus_one_one":
        x = x * 2.0 - 1.0
    elif mode == "imagenet":
        x = (x - IMAGENET_MEAN) / IMAGENET_STD
    else:
        raise ValueError("SR_PREPROC_MODE inválido")
    x = np.transpose(x, (2,0,1))[None, ...]
    return x

def sr_postprocess_rgb(out_nchw: np.ndarray, mode: str = "zero_one") -> np.ndarray:
    """Postprocess super-resolution output back to RGB."""
    y = out_nchw[0]
    y = np.transpose(y, (1,2,0))
    if mode == "zero_one":
        pass
    elif mode == "minus_one_one":
        y = (y + 1.0) * 0.5
    elif mode == "imagenet":
        y = y * IMAGENET_STD + IMAGENET_MEAN
    else:
        raise ValueError("SR_PREPROC_MODE inválido")
    return np.clip(y, 0.0, 1.0)

def sr_on_indexed_tiles_with_padding(
    rgb_256_hw3: np.ndarray,
    sr_session,
    tile_size: int = 32,
    pad_lr: int = 4,
    mode: str = "zero_one"
):
    """Apply super-resolution to RGB image using tiling with padding."""
    tiles_lr, ty, tx = tile_image_array_indexed(rgb_256_hw3, tile_size=tile_size)
    in_name  = sr_session.get_inputs()[0].name
    out_name = sr_session.get_outputs()[0].name
    sr_tiles = {}
    scale_detected = None
    t0 = time.time()
    for (r,c), tile in tiles_lr.items():
        if pad_lr > 0:
            tile_pad = cv2.copyMakeBorder(tile, pad_lr, pad_lr, pad_lr, pad_lr, cv2.BORDER_REFLECT_101)
        else:
            tile_pad = tile
        inp = sr_preprocess_rgb(tile_pad, mode=mode)
        out = sr_session.run([out_name], {in_name: inp})[0]
        out_hw3 = sr_postprocess_rgb(out, mode=mode)
        if scale_detected is None:
            Hs, Ws, _ = out_hw3.shape
            scale_detected = Hs // (tile_size + 2*pad_lr)
            assert Hs == Ws and scale_detected >= 1, f"SR salida inesperada: {Hs}x{Ws}"
        tgt = tile_size * scale_detected
        Hs, Ws, _ = out_hw3.shape
        off_y = (Hs - tgt) // 2
        off_x = (Ws - tgt) // 2
        out_cropped = out_hw3[off_y:off_y+tgt, off_x:off_x+tgt, :]
        sr_tiles[(r,c)] = out_cropped
    sr_mega = reconstruct_from_indexed_tiles(sr_tiles, tiles_y=ty, tiles_x=tx)
    return sr_mega, scale_detected

# ===================== LAMBDA HANDLER =====================

def lambda_handler(event, context):
    """
    AWS Lambda handler for super-resolution of multi-band TIF images.
    
    Args:
        event: Dictionary containing:
            - bucket: S3 bucket name with input TIF
            - key: S3 key of input TIF
            - model_bucket: S3 bucket with ONNX models
            - sr_model_key: S3 key of super-resolution ONNX model
            - output_bucket: S3 bucket for output
            - output_key_prefix: Optional prefix for output key
            - use_unet: Optional, whether to use unet_model.onnx instead (default False)
            - band_indices: Optional, list of band indices to use as RGB (default [0,1,2])
        context: Lambda context
    
    Returns:
        Dictionary with statusCode and body containing output location
    """
    try:
        # Parse event parameters
        bucket_name = event['bucket']
        object_key = event['key']
        model_bucket = event['model_bucket']
        sr_model_key = event['sr_model_key']
        output_bucket = event['output_bucket']
        output_key_prefix = event.get('output_key_prefix', '')
        use_unet = event.get('use_unet', False)
        band_indices = event.get('band_indices', [0, 1, 2])
        
        print(f"Processing image from s3://{bucket_name}/{object_key}")
        print(f"Output bucket: {output_bucket}")
        print(f"Output prefix: {output_key_prefix}")
        
        s3 = boto3.client('s3')
        
        # Download input TIF from S3
        input_path = f'/tmp/{os.path.basename(object_key)}'
        print(f"Downloading input image to {input_path}")
        s3.download_file(bucket_name, object_key, input_path)
        
        # Read TIF with rasterio to preserve metadata
        print("Reading TIF with rasterio...")
        with rasterio.open(input_path) as src:
            # Read all bands
            bands_data = []
            for i in range(1, src.count + 1):
                bands_data.append(src.read(i))
            
            # Get metadata
            profile = src.profile.copy()
            transform = src.transform
            crs = src.crs
            bounds = src.bounds
            
            # Convert to numpy array (bands, height, width)
            image_stack = np.array(bands_data, dtype=np.float32)
            
            # Extract RGB bands
            if len(band_indices) > image_stack.shape[0]:
                raise ValueError(f"Band indices {band_indices} exceed available bands {image_stack.shape[0]}")
            
            # Use first 3 bands if band_indices not specified or out of range
            if max(band_indices) >= image_stack.shape[0]:
                print(f"Warning: Specified band indices out of range, using first 3 bands")
                rgb_256 = np.dstack([image_stack[0], image_stack[1], image_stack[2]])
            else:
                rgb_256 = np.dstack([image_stack[i] for i in band_indices])
            
            # Normalize bands
            print("Normalizing bands...")
            normalized_bands = normalize_bands_auto(image_stack, s1_idx=S1_IDX)
            rgb_256_normalized = np.dstack([normalized_bands[i] for i in band_indices if i < normalized_bands.shape[0]][:3])
            # Ensure we have 3 bands
            if rgb_256_normalized.shape[2] < 3:
                rgb_256_normalized = np.dstack([normalized_bands[0], normalized_bands[1], normalized_bands[2]])
            
            rgb_256_normalized = np.clip(rgb_256_normalized, 0, 1)
        
        os.remove(input_path)
        
        # Download ONNX model
        model_key = 'unet_model.onnx' if use_unet else sr_model_key
        model_path = f'/tmp/{os.path.basename(model_key)}'
        print(f"Downloading model {model_key}...")
        s3.download_file(model_bucket, model_key, model_path)
        
        # Load ONNX model
        print("Loading ONNX model...")
        sr_session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        
        # Perform super-resolution
        print("Applying super-resolution...")
        sr_result, scale = sr_on_indexed_tiles_with_padding(
            rgb_256_normalized,
            sr_session,
            tile_size=TILE_LR_SIZE,
            pad_lr=PAD_LR_PIXELS,
            mode=SR_PREPROC_MODE
        )
        
        print(f"Super-resolution applied with scale factor: {scale}")
        
        # Convert result back to uint16 for TIF output
        sr_result_uint16 = (sr_result * 65535).astype(np.uint16)
        
        # Update profile for output
        output_profile = profile.copy()
        output_profile['count'] = 3
        output_profile['dtype'] = 'uint16'
        output_profile['height'], output_profile['width'] = sr_result_uint16.shape[:2]
        
        # Calculate new transform for upscaled image
        new_transform = transform * rasterio.Affine.scale(1/scale)
        
        # Save output TIF with metadata
        original_filename = os.path.basename(object_key)
        original_name_without_ext = os.path.splitext(original_filename)[0]
        output_filename = f"{SR_OUTPUT_PREFIX}_{original_name_without_ext}.tif"
        output_path = f'/tmp/{output_filename}'
        
        print(f"Saving output TIF to {output_path}")
        with rasterio.open(output_path, 'w', **output_profile) as dst:
            dst.transform = new_transform
            dst.crs = crs
            # Write RGB bands
            for i in range(3):
                dst.write(sr_result_uint16[:, :, i], i + 1)
        
        # Upload to S3
        output_s3_key = os.path.join(output_key_prefix, output_filename) if output_key_prefix else output_filename
        print(f"Uploading to s3://{output_bucket}/{output_s3_key}")
        s3.upload_file(output_path, output_bucket, output_s3_key)
        
        # Cleanup
        os.remove(model_path)
        os.remove(output_path)
        
        return {
            'statusCode': 200,
            'body': {
                'message': 'Super-resolution applied successfully',
                'input_location': f's3://{bucket_name}/{object_key}',
                'output_location': f's3://{output_bucket}/{output_s3_key}',
                'scale_factor': float(scale)
            }
        }
    
    except KeyError as e:
        print(f"Error: Missing key in event object: {e}")
        return {
            'statusCode': 400,
            'body': f'Error: Missing key in event object: {e}. Event must contain "bucket", "key", "model_bucket", "sr_model_key", and "output_bucket".'
        }
    except Exception as e:
        print(f"Error during processing: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': f'Error processing image: {str(e)}'
        }


