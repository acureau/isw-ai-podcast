import re
import requests
from enum import Enum
from bs4 import BeautifulSoup, Tag
from dataclasses import dataclass
from constants import OPENAI_CLIENT


# All possible types of blocks.
class Type(Enum):
    HEADING = 0
    IMAGE = 1
    CONTENT = 2


# Represents a single "chunk" of an article.
@dataclass
class Block:
    type: Type
    value: str


# Represents a single "section" of an output.
@dataclass
class Section:
    name: str
    blocks: list[Block]


# Represents a complete output.
@dataclass
class Output:
    title: str
    sections: list[Section]


# Regex rules to use when validating text, matching means invalid.
_TEXT_FILTERS = [
    r"^\[\d+\]",  # Filter citations.
    r"^Note:",  # Filter notes.
    r"^Click here",  # Filter links.
    r"^We do not report in detail on Russian war crimes",  # Filter disclaimer.
    r"^Ukrainian Operations in the Russian Federation.+$",  # Filter table of contents.
    r"^Nothing significant to report.$",  # Filter fluff.
    r"^ISW is not publishing coverage of.*today\.$",  # Filter fluff.
    r"^See topline text.$",  # Filter fluff.
]


# Validates output text before creating a block.
def _validate_text(text):
    if len(text.strip()) < 1:
        return False

    for filter in _TEXT_FILTERS:
        if re.match(filter, text, re.DOTALL):
            return False

    return True


# Cleans output text.
def _clean_text(text):
    text = re.sub(r"\[\d+\]", "", text)
    text = text.replace("\n", " ").strip()
    return text


# Gets the raw HTML from the URL.
def _get_article_html(article_url):
    return requests.get(article_url).text


# Parses the HTML and constructs a list of article blocks.
def _get_article_blocks(article_html):
    article_blocks = []
    html_parser = BeautifulSoup(article_html, "html.parser")

    # Get article container and begin parsing it.
    article_container_element = html_parser.find(attrs={"property": "content:encoded"})
    for child_element in article_container_element:
        if type(child_element) == Tag:
            # Read heading block in span element.
            span_element = child_element.find("span")
            if span_element and child_element.get_text() == span_element.get_text():
                heading_text = span_element.get_text(strip=True)
                if _validate_text(heading_text):
                    article_blocks.append(
                        Block(Type.HEADING, _clean_text(heading_text))
                    )
                continue

            # Read image block in img element.
            img_element = child_element.find("img")
            if img_element:
                a_element = child_element.find("a")
                if a_element:
                    image_url = a_element["href"]
                    if len(image_url) > 0:
                        article_blocks.append(Block(Type.IMAGE, image_url))
                    continue

            # Read text content from all other elements.
            text = child_element.get_text()
            if _validate_text(text):
                article_blocks.append(Block(Type.CONTENT, _clean_text(text)))

    return article_blocks


# Cleans blocks not to be included in the 'audible' article output.
def _clean_article_blocks(article_blocks):

    # Remove the authors and date.
    article_blocks = [article_blocks[0]] + article_blocks[3:]

    # Remove headings with no blocks between.
    previous_block = None
    for block in list(article_blocks):
        if block.type == Type.HEADING:
            if previous_block != None and previous_block.type == Type.HEADING:
                article_blocks.remove(previous_block)
        previous_block = block

    # Remove last block if heading.
    if previous_block is not None and previous_block.type == Type.HEADING:
        article_blocks.remove(previous_block)

    return article_blocks


# Generates an efforts summary section w/ AI.
def _get_efforts_summary_text(events_text, events_summary_text, efforts_text):
    response = OPENAI_CLIENT.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": "Summarize the given conflict report in a concise and digestible way. All important details must be kept. Do not change the wording, or even speculate, on ANYTHING. This is an update, not an overview, you are writing for those already familiar with the conflict.",
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": events_text,
                    }
                ],
            },
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": events_summary_text,
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": efforts_text,
                    }
                ],
            },
        ],
        response_format={"type": "text"},
        temperature=1,
        max_completion_tokens=2048,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )
    return response.choices[0].message.content


# Converts article blocks to an output.
def _get_output(article_blocks):

    # Create empty strings for efforts AI sumarization.
    events_text = ""
    events_summary_text = ""
    efforts_text = ""

    # Parse title and create output.
    title_block = article_blocks.pop(0)
    output = Output(title_block.value, [])

    # Create and parse events section.
    events_section = Section(
        "That wraps up the overview — now we'll move on the to the full report.", []
    )
    while len(article_blocks) > 0:
        block = article_blocks.pop(0)
        if re.match(r"^Key Takeaways:$", block.value):
            break
        if block.type == Type.CONTENT:
            events_text += " " + block.value
        events_section.blocks.append(block)
    output.sections.append(events_section)

    # Create and parse events summary section.
    events_summary_section = Section(
        "So, let's start off with a summary of today's events.", []
    )
    while len(article_blocks) > 0:
        if article_blocks[0].type == Type.HEADING:
            break
        block = article_blocks.pop(0)
        if block.type == Type.CONTENT:
            events_summary_text += " " + block.value
        events_summary_section.blocks.append(block)
    output.sections.append(events_summary_section)

    # Create and parse all efforts sections with headings.
    efforts_section = None
    while len(article_blocks) > 0:
        block = article_blocks.pop(0)
        if block.type == Type.HEADING:
            if efforts_section != None:
                output.sections.append(efforts_section)
            efforts_section = Section(block.value, [])
        else:
            if block.type == Type.CONTENT:
                efforts_text += " " + block.value
            efforts_section.blocks.append(block)
    output.sections.append(efforts_section)

    # Generate efforts summary section.
    efforts_summary_text = _get_efforts_summary_text(
        events_text, events_summary_text, efforts_text
    )
    efforts_summary_section = Section(
        "Next up is a summary of the main efforts. Please note that this section is A.I. generated and may be inaccurate, so don't take it as fact!",
        [Block(Type.CONTENT, efforts_summary_text)],
    )

    # Re-order sections to place summaries first.
    output.sections.insert(2, efforts_summary_section)
    events_section = output.sections.pop(0)
    output.sections.insert(2, events_section)

    return output


# Debug method for converting blocks to markdown file.
def _dbg_export_blocks_md(blocks, name):
    article = ""
    for block in blocks:
        if block.type == Type.HEADING:
            article += "# " + block.value
        elif block.type == Type.IMAGE:
            article += "<!-- " + block.value + " -->"
        else:
            article += block.value
        article += "\n\n"
    open(f"{name}.md", "w", encoding="UTF-8").write(article)


# Scrapes a list of 'audible' block objects from an article URL.
def convert_article(article_url):
    article_html = _get_article_html(article_url)
    article_blocks = _get_article_blocks(article_html)
    cleaned_article_blocks = _clean_article_blocks(article_blocks)
    output = _get_output(cleaned_article_blocks)
    return output
