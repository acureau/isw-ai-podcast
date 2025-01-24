import os
from convert import Type
from slugify import slugify
from pydub import AudioSegment
from constants import OPENAI_CLIENT
from nltk.tokenize import sent_tokenize
from concurrent.futures import ThreadPoolExecutor


# Speaking delay constants.
TITLE_DELAY = 2
HEADING_DELAY = 1.3
CONTENT_DELAY = 0.8


# Produce audio files from text.
def _text_to_audio(text, filename):
    response = OPENAI_CLIENT.audio.speech.create(
        model="tts-1-hd",
        voice="onyx",
        input=text,
        response_format="wav",
    )
    response.write_to_file(filename)
    audio = AudioSegment.from_wav(filename)
    os.remove(filename)
    return audio


# Chunks text into one or more strings, split at complete sentences, which do not exceed a maximum character length.
def _chunk_text(input_text, max_size=4096):
    sentences = sent_tokenize(input_text)
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 <= max_size:
            current_chunk += sentence + " "
        else:
            chunks.append(current_chunk.strip())
            current_chunk = sentence + " "

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


# Gets a sequence of spoken strings and delay seconds from the parsed output.
def _get_sequence_from_output(parsed_output):
    sequence = [TITLE_DELAY, parsed_output.title, TITLE_DELAY]
    for section in parsed_output.sections:
        sequence += [HEADING_DELAY, section.name, HEADING_DELAY]
        for block in section.blocks:
            if block.type == Type.HEADING:
                sequence += [HEADING_DELAY, block.value, HEADING_DELAY]
            elif block.type == Type.CONTENT:
                sequence += _chunk_text(block.value) + [CONTENT_DELAY]
    return sequence


# Converts a parsed sequence to audio segmenets, processes in parallel.
def _get_audio_from_sequence(sequence):
    def process_item(item):
        if type(item) == int or type(item) == float:
            return AudioSegment.silent(item * 1000)
        else:
            return _text_to_audio(item, f"temp_audio_{hash(item)}.wav")

    with ThreadPoolExecutor() as executor:
        sequence = list(executor.map(process_item, sequence))

    return sequence


# Generates an audio file from parsed output.
def generate_audio(parsed_output):
    sequence = _get_sequence_from_output(parsed_output)
    audio = _get_audio_from_sequence(sequence)
    combined_audio = sum(audio)
    combined_audio.export(f"{slugify(parsed_output.title)}.wav", format="wav")
