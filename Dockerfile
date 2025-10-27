# Dockerfile for Super Resolution Lambda Function
FROM public.ecr.aws/lambda/python:3.10

# Install system dependencies for GDAL and rasterio
RUN yum update -y && \
    yum install -y gcc gcc-c++ make gdal gdal-devel proj proj-devel && \
    yum clean all

# Copy function code
COPY lambda_function.py ${LAMBDA_TASK_ROOT}

# Copy ONNX models (both models supported)
COPY model/satlas_sr.onnx ${LAMBDA_TASK_ROOT}/model/satlas_sr.onnx
COPY model/unet_model.onnx ${LAMBDA_TASK_ROOT}/model/unet_model.onnx

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Set the CMD to your handler
CMD [ "lambda_function.lambda_handler" ]


