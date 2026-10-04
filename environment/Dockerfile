# hash:sha256:9cccae10ecc176e206d4381a5547ff91bdff7975a40383155a14c2c95fba37f5
# Code Ocean capsule environment (exported from the working reproducible run).
# Local development: use code/scripts/activate_env.sh + code/requirements.txt instead;
# this base image is served from Code Ocean's registry.
FROM registry.codeocean.com/codeocean/py-r:python3.12.8-R4.4.2-JupyterLab4.3.5-RStudiorstudio-server-2024.12.1-563-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive

RUN pip install -U --no-cache-dir \
    google-genai==0.3.0 \
    matplotlib==3.11.1 \
    numpy==2.2.6 \
    openai==1.40.0 \
    pandas==2.2.3 \
    pytest==9.1.1 \
    pyyaml==6.0.3 \
    requests==2.34.2 \
    yfinance==1.5.2
