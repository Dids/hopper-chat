"""
Hopper Chat with ChatGPT backend

Author: Shawn Hymel
Date: April 20, 2024
License: 0BSD (https://opensource.org/license/0bsd)
"""

import queue
import time
import sys
import json
import os
from collections import deque

from dotenv import load_dotenv
import numpy as np
import resampy
import sounddevice as sd
import soundfile as sf
from vosk import Model, KaldiRecognizer
import openai
from TTS.api import TTS

#---------------------------------------------------------------------------------------------------
# Settings

# Print stuff to console
DEBUG = True

# Set input and output audio devices (get from the "Available sound devices")
AUDIO_INPUT_INDEX = 1
AUDIO_OUTPUT_INDEX = 2

# Volume (1.0 = normal, 2.0 = double volume)
AUDIO_OUTPUT_VOLUME = 1.0

# Sample rate (determined by speaker hardware)
AUDIO_OUTPUT_SAMPLE_RATE = 48000

# Set notification sound (when wake phrase is heard). Leave blank for no notification sound.
NOTIFICATION_PATH = "./sounds/cowbell.wav"

# Set wake words or phrases
WAKE_PHRASES = [
    "hey hopper",
    "a hopper",
]

# Set action phrases
ACTION_CLEAR_HISTORY = [    # Clear chat history
    "clear history",
    "clear chat history",
]
ACTION_STOP = [             # Return to waiting for wake phrase
    "stop",
    "stop listening",
    "nevermind", 
    "never mind",
]

# ChatGPT settings
GPT_API_KEY = ""            # Leave blank to load from OPENAI_API_KEY environment variable
GPT_MODEL = "gpt-3.5-turbo"
GPT_MAX_HISTORY = 20        # Number of prompts and replies to remember
GPT_MAX_REPLY_SENTENCES = 2 # Max number of sentences to respond with (0 is infinite)
GPT_GET_FULL_REPLY = False  # Get full reply after getting the summary

# TTS settings
TTS_ENABLE = True
TTS_MODEL = "tts_models/en/ljspeech/speedy-speech"  # Run `tts --list_models` to see options
TTS_MODEL_SAMPLE_RATE = 22050   # Determined by model

#---------------------------------------------------------------------------------------------------
# Classes

class FixedSizeQueue:
    """
    Fixed size array with FIFO
    """
    def __init__(self, max_size):
        self.queue = deque(maxlen=max_size)

    def push(self, item):
        self.queue.append(item)

    def get(self):
        return list(self.queue)

#---------------------------------------------------------------------------------------------------
# Functions

def callback_record(in_data, frames, time, debug):
    """
    Fill global input queue with audio data
    """
    global in_q

    if debug:
        print(status, file=sys.stderr)
    in_q.put(bytes(in_data))

def wait_for_stt(sd, recognizer):
    """
    Wait for STT to hear something and return the text
    """

    global in_q

    # Listen for wake word/phrase
    with sd.RawInputStream(
        dtype="int16",
        channels=1,
        callback=callback_record
    ):
        if DEBUG:
            print("Listening...")
    
        # Perform keyword spotting
        while True:
            data = in_q.get()
            if recognizer.AcceptWaveform(data):

                # Perform speech-to-text (STT)
                result = recognizer.Result()
                result_dict = json.loads(result)
                result_text = result_dict.get("text", "")

                return result_text

def query_chat(msg):
    """
    Send message to chat backend (ChatGPT) and return response text
    """

    global msg_history

    # Add prompt to message history
    msg_history.push({
        "role": "user",
        "content": msg,
    })

    print(msg_history.get())

    # Query ChatGPT
    completion = gpt_client.chat.completions.create(
        model=GPT_MODEL,
        messages=msg_history.get()
    )
    
    # Extract text reply and append to message history
    reply = completion.choices[0].message.content
    msg_history.push({
        "role": "assistant",
        "content": reply,
    })

    return reply

#---------------------------------------------------------------------------------------------------
# Main

# Print available sound devices
if DEBUG:
    print("Available sound devices:")
    print(sd.query_devices())

# Set the input and output devices
sd.default.device = [AUDIO_INPUT_INDEX, AUDIO_OUTPUT_INDEX]

# Get sample rate
device_info = sd.query_devices(sd.default.device[0], "input")
sample_rate = int(device_info["default_samplerate"])

# Display input device info
if DEBUG:
    print(f"Input device info: {json.dumps(device_info, indent=2)}")

# Load notification sound into memory
if NOTIFICATION_PATH:
    notification_wav, notification_sample_rate = sf.read(NOTIFICATION_PATH)
    notification_wav = np.array(notification_wav) * AUDIO_OUTPUT_VOLUME
    notification_wav = resampy.resample(
        notification_wav,
        notification_sample_rate,
        AUDIO_OUTPUT_SAMPLE_RATE
    )


# Set up queue and callback
in_q = queue.Queue()

# Build the model
model = Model(lang="en-us")
recognizer = KaldiRecognizer(model, sample_rate)
recognizer.SetWords(False)

# Load ChatGPT API key
try:
    from dotenv import load_dotenv
    load_dotenv()
except ModuleNotFoundError:
    pass
gpt_api_key = os.environ.get("OPENAI_API_KEY", GPT_API_KEY)

# List available models
if DEBUG:
    models = openai.models.list()
    for model in models:
        print(model.id)

# Initialize ChatGPT client
gpt_client = openai.OpenAI(api_key=gpt_api_key)

# Initialize TTS
if TTS_ENABLE:
    tts = TTS(model_name=TTS_MODEL, progress_bar=False)

# Superloop
msg_history = FixedSizeQueue(GPT_MAX_HISTORY)
while True:
    
    # Listen for wake word or phrase
    text = wait_for_stt(sd, recognizer)
    if DEBUG:
        print(f"Heard: {text}")
    if text in WAKE_PHRASES:
        if DEBUG:
            print(f"Wake phrase detected.")
    else:
        continue

    # Play notification sound
    if NOTIFICATION_PATH:
        sd.play(notification_wav, samplerate=AUDIO_OUTPUT_SAMPLE_RATE, device=AUDIO_OUTPUT_INDEX)
        sd.wait()

    # Listen for query
    text = wait_for_stt(sd, recognizer)
    if text != "":
        if DEBUG:
            print(f"Heard: {text}")
    else:
        if DEBUG:
            print("No sound detected. Returning to wake word detection.")
        continue
    listening_for_query = False

    # Perform actions for particular phrases
    if text in ACTION_CLEAR_HISTORY:
        if DEBUG:
            print("ACTION: clearning history")
        msg_history = FixedSizeQueue(GPT_MAX_HISTORY)
        continue
    elif text in ACTION_STOP:
        if DEBUG:
            print("ACTION: stop listening")
        continue

    # Default action: query chat backend
    else:

        # Send request with limited reply length
        if GPT_MAX_REPLY_SENTENCES > 0:
            msg = text + f". Your response must be {GPT_MAX_REPLY_SENTENCES} sentences or fewer."
        if DEBUG:
            print(f"Sending: {msg}")
        reply = query_chat(msg)
        if DEBUG:
            print(f"Received: {reply}")

        # Repeat the query to get the full reply
        # TODO: Looks like it's still giving us a truncated version. Come back and fix this.
        if GPT_GET_FULL_REPLY:
            msg = "Repeat the previous request, but do so without any limit on number of sentences."
            if DEBUG:
                print(f"Sending: {msg}")
            reply_full = query_chat(msg)
            if DEBUG:
                print(f"Received: {reply}")

        # Perform text-to-speech (TTS)
        if TTS_ENABLE and reply:
            if DEBUG:
                print("Playing reply...")
            wav = tts.tts(text=reply)
            wav = np.array(wav) * AUDIO_OUTPUT_VOLUME
            wav = resampy.resample(wav, TTS_MODEL_SAMPLE_RATE, AUDIO_OUTPUT_SAMPLE_RATE)
            sd.play(wav, samplerate=AUDIO_OUTPUT_SAMPLE_RATE, device=AUDIO_OUTPUT_INDEX)
            sd.wait()
