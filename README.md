# Background

This is a program that I wrote to convert the ISW's "Russian Offensive Campaign Assessment" reports to an audio format I could listen to while working. It's very hacky, only supports these specific articles at the moment, and it relies on OpenAI's TTS-1-HD and GPT-4o models. It generates a summary of the main efforts and scrapes the provided summary of daily events, and it reads them out before the full report.

## Installation

1.  `git clone https://github.com/acureau/isw-ai-podcast.git && cd isw-ai-podcast`
2.  `pip install -r requirements.txt`
3.  Install ffmpeg.

## Usage

1.  Insert your API key into the `constants.py` file.
2.  Update the report URL in the `main.py` file.
3.  Execute `main.py`, wait for the output `.wav` file.

## Contributions

In the rare chance anyone wants to contribute I'd like to expand support to other ISW reports. If you fix a bug I will merge. If you're more ambitious the code is currently scraping image URLs, the original plan was to generate a slideshow and display those images when relevant sections were being read. I have no immediate plans to do this myself.
