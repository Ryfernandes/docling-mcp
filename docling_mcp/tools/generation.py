"""Tools for generating Docling documents."""

import hashlib
from dataclasses import dataclass
from io import BytesIO
from typing import Annotated

from pydantic import Field

from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.document import (
    ConversionResult,
)
from docling.document_converter import DocumentConverter
from docling_core.types.doc.document import (
    ContentLayer,
    DoclingDocument,
    GroupItem,
    LevelNumber,
)
from docling_core.types.doc.labels import (
    DocItemLabel,
    GroupLabel,
)
from docling_core.types.io import DocumentStream

from docling_mcp.docling_cache import get_cache_dir
from docling_mcp.logger import setup_logger
from docling_mcp.shared import local_document_cache, local_stack_cache, mcp, stack_cache
import docling_mcp.shared as shared

# Create a default project logger
logger = setup_logger()


def hash_string_md5(input_string: str) -> str:
    """Creates an md5 hash-string from the input string."""
    return hashlib.md5(input_string.encode()).hexdigest()


@dataclass
class NewDoclingDocumentOutput:
    """Output of the create_new_docling_document tool."""

    prompt: Annotated[str, Field(description="The original prompt.")]

    document: Annotated[object, Field(description="The json representation of the document.")]

"""
@mcp.tool(title="Create new Docling document")
def create_new_docling_document(
    prompt: Annotated[
        str, Field(description="The prompt text to include in the new document.")
    ],
) -> NewDoclingDocumentOutput:
    ""Create a new Docling document from a provided prompt string.

    This function updates the shared document object to be edited with a new DoclingDocument
    ""
    doc = DoclingDocument(name="Generated Document")

    item = doc.add_text(
        label=DocItemLabel.TEXT,
        text=f"prompt: {prompt}",
        content_layer=ContentLayer.FURNITURE,
    )

    shared.document = doc

    shared.stack_cache = [item]

    return NewDoclingDocumentOutput(prompt, document.export_to_dict())
"""

@dataclass
class ExportDocumentMarkdownOutput:
    """Output of the export_docling_document_to_markdown tool."""

    markdown: Annotated[
        str, Field(description="The representation of the document in markdown format.")
    ]


@mcp.tool(title="Export Docling document to markdown format")
def export_docling_document_to_markdown(
) -> ExportDocumentMarkdownOutput:
    """Export the shared Docling Document object to markdown format.

    This tool converts the shared Docling Document object into
    a markdown formatted string, which can be used for display or further processing.
    """
    if not shared.document:
        raise ValueError(
            "Document has not been initialized. Please load a document first."
        )
    
    markdown = shared.document.export_to_markdown()

    return ExportDocumentMarkdownOutput(markdown)

@dataclass
class DocumentUpdateOutput:
    """Output of the tools that update the Docling document."""

    document: Annotated[object, Field(description="The json representation of the document.")]

@mcp.tool(title="Add or update title to Docling document")
def add_title_to_docling_document(
    title: Annotated[
        str, Field(description="The title text to add or update to the document.")
    ],
) -> DocumentUpdateOutput:
    """Add or update the title of the shared Docling Document object.

    This tool modifies the existing shared Docling Document object.
    It requires that the document already exists before a title can be added.
    """
    if not shared.document:
        raise ValueError(
            "Document has not been initialized. Please load a document first."
        )

    if len(stack_cache) == 0:
        raise ValueError(
            f"Stack size is zero for the shared Docling Document. Abort document generation"
        )

    parent = stack_cache[-1]

    if isinstance(parent, GroupItem):
        if parent.label == GroupLabel.LIST or parent.label == GroupLabel.ORDERED_LIST:
            raise ValueError(
                "A list is currently opened. Please close the list before adding a title!"
            )

    item = shared.document.add_title(text=title)
    stack_cache[-1] = item

    return DocumentUpdateOutput(shared.document.export_to_dict())


@mcp.tool(title="Add section heading to Docling document")
def add_section_heading_to_docling_document(
    section_heading: Annotated[
        str, Field(description="The text to use for the section heading.")
    ],
    section_level: Annotated[
        LevelNumber,
        Field(
            description="The level of the heading, starting from 1, where 1 is the highest level."
        ),
    ],
) -> DocumentUpdateOutput:
    """Add a section heading to the shared Docling Document object.

    This tool inserts a section heading with the specified heading text and level
    into the existing shared Docling Document object.
    Section levels typically represent heading hierarchy (e.g., 1 for H1, 2 for H2).
    """
    if not shared.document:
        raise ValueError(
            "Document has not been initialized. Please load a document first."
        )

    if len(stack_cache) == 0:
        raise ValueError(
            f"Stack size is zero for the shared Docling Document. Abort document generation"
        )

    parent = stack_cache[-1]

    if isinstance(parent, GroupItem):
        if parent.label == GroupLabel.LIST or parent.label == GroupLabel.ORDERED_LIST:
            raise ValueError(
                "A list is currently opened. Please close the list before adding a section-heading!"
            )

    item = shared.document.add_heading(
        text=section_heading, level=section_level
    )
    stack_cache[-1] = item

    return DocumentUpdateOutput(shared.document.export_to_dict())


@mcp.tool(title="Add paragraph to Docling document")
def add_paragraph_to_docling_document(
    paragraph: Annotated[
        str, Field(description="The text content to add as a paragraph.")
    ],
) -> DocumentUpdateOutput:
    """Add a paragraph of text to the shared Docling Document object.

    This tool inserts a new paragraph under the specified section header and level
    into the existing shared Docling Document object.
    """
    if not shared.document:
        raise ValueError(
            "Document has not been initialized. Please load a document first."
        )

    if len(stack_cache) == 0:
        raise ValueError(
            f"Stack size is zero for the shared Docling Document. Abort document generation"
        )

    parent = stack_cache[-1]

    if isinstance(parent, GroupItem):
        if parent.label == GroupLabel.LIST or parent.label == GroupLabel.ORDERED_LIST:
            raise ValueError(
                "A list is currently opened. Please close the list before adding a paragraph!"
            )

    item = shared.document.add_text(
        label=DocItemLabel.TEXT, text=paragraph
    )
    stack_cache[-1] = item

    return DocumentUpdateOutput(shared.document.export_to_dict())


@mcp.tool(title="Open list in Docling document")
def open_list_in_docling_document() -> DocumentUpdateOutput:
    """Open a new list group in the shared Docling Document object.

    This tool creates a new list structure within the existing shared Docling
    Document object. It requires that the document already exists
    and that there is at least one item in the document's stack cache.
    """
    if not shared.document:
        raise ValueError(
            "Document has not been initialized. Please load a document first."
        )

    if len(stack_cache) == 0:
        raise ValueError(
            f"Stack size is zero for the shared Docling Document. Abort document generation"
        )

    item = shared.document.add_group(label=GroupLabel.LIST)
    stack_cache.append(item)

    return DocumentUpdateOutput(shared.document.export_to_dict())


@mcp.tool(title="Close list in Docling document")
def close_list_in_docling_document() -> DocumentUpdateOutput:
    """Closes a list group in the shared Docling Document object.

    This tool closes a previously opened list structure within a document.
    It requires that the document exists and that there is more than one item
    in the document's stack cache.
    """
    if not shared.document:
        raise ValueError(
            "Document has not been initialized. Please load a document first."
        )

    if len(stack_cache) == 0:
        raise ValueError(
            f"Stack size is zero for the shared Docling Document. Abort document generation"
        )

    stack_cache.pop()

    return DocumentUpdateOutput(shared.document.export_to_dict())


@dataclass
class ListItem:
    """A class to represent a list item pairing."""

    list_item_text: Annotated[str, Field(description="The text of a list item.")]
    list_marker_text: Annotated[str, Field(description="The marker of a list item.")]


@mcp.tool(title="Add items to list in Docling document")
def add_list_items_to_list_in_docling_document(
    list_items: Annotated[
        list[ListItem],
        Field(description="A list of list_item_text and list_marker_text items."),
    ],
) -> DocumentUpdateOutput:
    """Add list items to an open list in the shared Docling Document object.

    This tool inserts new list items with the specified text and marker into an
    open list within a document. It requires that the document exists and that
    there is at least one item in the document's stack cache.
    """
    if not shared.document:
        raise ValueError(
            "Document has not been initialized. Please load a document first."
        )

    if len(stack_cache) == 0:
        raise ValueError(
            f"Stack size is zero for the shared Docling Document. Abort document generation"
        )
    
    parent = stack_cache[-1]

    if isinstance(parent, GroupItem):
        if parent.label != GroupLabel.LIST and parent.label != GroupLabel.ORDERED_LIST:
            raise ValueError(
                "No list is currently opened. Please open a list before adding list-items!"
            )
    else:
        raise ValueError(
            "No list is currently opened. Please open a list before adding list-items!"
        )

    for list_item in list_items:
        shared.document.add_list_item(
            text=list_item.list_item_text,
            marker=list_item.list_marker_text,
            parent=parent,
        )

    return DocumentUpdateOutput(shared.document.export_to_dict())


@mcp.tool(title="Add HTML table to Docling document")
def add_table_in_html_format_to_docling_document(
    html_table: Annotated[
        str,
        Field(
            description="The HTML string representation of the table to add.",
            examples=[
                "<table><tr><th>Name</th><th>Age</th></tr><tr><td>John</td><td>30</td></tr></table>",
                "<table><tr><th colspan='2'>Demographics</th></tr><tr><th>Name</th><th>Age</th></tr><tr><td>John</td><td rowspan='2'>30</td></tr><tr><td>Jane</td></tr></table>",
            ],
        ),
    ],
    table_captions: Annotated[
        list[str] | None,
        Field(description="A list of caption strings to associate with the table.."),
    ] = None,
    table_footnotes: Annotated[
        list[str] | None,
        Field(description="A list of footnote strings to associate with the table."),
    ] = None,
) -> DocumentUpdateOutput:
    """Add an HTML-formatted table to the shared Docling Document object.

    This tool parses the provided HTML table string, converts it to a structured table
    representation, and adds it to the existing shared Docling Document
    object. It also supports optional captions and footnotes for the table.
    """
    if not shared.document:
        raise ValueError(
            "Document has not been initialized. Please load a document first."
        )

    if len(stack_cache) == 0:
        raise ValueError(
            f"Stack size is zero for the shared Docling Document. Abort document generation"
        )

    html_doc: str = f"<html><body>{html_table}</body></html>"

    buff = BytesIO(html_doc.encode("utf-8"))
    doc_stream = DocumentStream(name="tmp", stream=buff)

    converter = DocumentConverter(allowed_formats=[InputFormat.HTML])
    conv_result: ConversionResult = converter.convert(doc_stream)

    if (
        conv_result.status == ConversionStatus.SUCCESS
        and len(conv_result.document.tables) > 0
    ):
        table = shared.document.add_table(data=conv_result.document.tables[0].data)

        for _ in table_captions or []:
            caption = shared.document.add_text(label=DocItemLabel.CAPTION, text=_)
            table.captions.append(caption.get_ref())

        for _ in table_footnotes or []:
            footnote = shared.document.add_text(label=DocItemLabel.FOOTNOTE, text=_)
            table.footnotes.append(footnote.get_ref())
    else:
        raise ValueError(
            "Could not parse the html string of the table! Please fix the html and try again!"
        )
    
    return DocumentUpdateOutput(shared.document.export_to_dict())