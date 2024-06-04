#
# Allow build-time overrides for customizing Piper TTS on a per image basis.
# Voices: https://github.com/rhasspy/piper/blob/master/VOICES.md
#
ARG PIPER_VERSION="v1.0.0"
ARG PIPER_SPEAKER_LANGUAGE="en"
ARG PIPER_SPEAKER_LANGUAGE_CODE="en_US"
ARG PIPER_SPEAKER_NAME="hfc_female"
ARG PIPER_SPEAKER_QUALITY="medium"

#
# Use an appropriate base image.
#
FROM python:3.12

#
# Set the working directory.
#
WORKDIR /app

#
# Install dependencies.
# Models: https://github.com/rhasspy/piper/blob/master/VOICES.md
#
RUN \
    git init && \
    git remote add origin https://github.com/rhasspy/piper && \
    git fetch origin 078bf8a17e24ebb18332710354c0797872dcef6a --depth=1 && \
    git reset --hard FETCH_HEAD && \
    cd src/python_run/ && \
    python3 -m pip install -e . && \
    python3 -m pip install -r requirements_http.txt && \
    mkdir -p /app/models/ && \
    cd /app/models/ && \
    wget -O model.onnx "https://huggingface.co/rhasspy/piper-voices/resolve/${PIPER_VERSION}/${PIPER_SPEAKER_LANGUAGE}/${PIPER_SPEAKER_LANGUAGE_CODE}/${PIPER_SPEAKER_NAME}/${PIPER_SPEAKER_QUALITY}/${PIPER_SPEAKER_LANGUAGE_CODE}-${PIPER_SPEAKER_NAME}-${PIPER_SPEAKER_QUALITY}.onnx?download=true" && \
    wget -O model.onnx.json "https://huggingface.co/rhasspy/piper-voices/resolve/${PIPER_VERSION}/${PIPER_SPEAKER_LANGUAGE}/${PIPER_SPEAKER_LANGUAGE_CODE}/${PIPER_SPEAKER_NAME}/${PIPER_SPEAKER_QUALITY}/${PIPER_SPEAKER_LANGUAGE_CODE}-${PIPER_SPEAKER_NAME}-${PIPER_SPEAKER_QUALITY}.onnx.json?download=true.json"

#
# Expose the port the server will run on.
#
EXPOSE 10803

#
# Command to run the server.
#
ENTRYPOINT ["python3", "-m", "piper.http_server", "--model", "/app/models/model.onnx", "--config", "/app/models/model.onnx.json", "--port", "10803"]
