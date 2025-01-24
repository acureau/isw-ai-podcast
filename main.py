import nltk
import convert
import generate

# Convert the article to an output object.
parsed_output = convert.convert_article(
    "https://www.understandingwar.org/backgrounder/russian-offensive-campaign-assessment-january-23-2025"
)

# Ensure dependency.
nltk.download("punkt_tab", quiet=True)

# Convert the output to audio.
generate.generate_audio(parsed_output)
