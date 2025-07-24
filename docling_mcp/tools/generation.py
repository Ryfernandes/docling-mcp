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
    GroupItem,
    LevelNumber,
    RefItem,
    NodeItem,
)
from docling_core.types.doc.labels import (
    DocItemLabel,
    GroupLabel,
)
from docling_core.types.io import DocumentStream

import docling_mcp.shared as shared
from docling_mcp.logger import setup_logger
from docling_mcp.shared import mcp

# Create a default project logger
logger = setup_logger()


def hash_string_md5(input_string: str) -> str:
    """Creates an md5 hash-string from the input string."""
    return hashlib.md5(input_string.encode()).hexdigest()

def resolve(anchor: str | RefItem) -> NodeItem:
    ref: RefItem = None
    
    if isinstance(anchor, RefItem):
        ref = anchor
    else:
        ref = RefItem(cref=anchor)
    return ref.resolve(shared.document)



@dataclass
class NewDoclingDocumentOutput:
    """Output of the create_new_docling_document tool."""

    prompt: Annotated[str, Field(description="The original prompt.")]

    document: Annotated[
        object, Field(description="The json representation of the document.")
    ]


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
def export_docling_document_to_markdown() -> ExportDocumentMarkdownOutput:
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

    document: Annotated[
        object, Field(description="The json representation of the document.")
    ]
    anchor: Annotated[
        str | None, Field(description="The document anchor of the item that was updated or created.")
    ]


@mcp.tool(title="Insert or append a title to Docling document")
def add_title_to_docling_document(
    title: Annotated[
        str, Field(description="The title text to add or update to the document.")
    ],
    sibling_anchor: Annotated[
        str | None, Field(description="The anchor of the sibling item to insert the title before/after.")
    ] = None,
    insert_after: Annotated[
        bool, Field(description="Whether to insert the title after the sibling item. Defaults to inserting before.")
    ] = False,
    parent_anchor: Annotated[
        str | None, Field(description="The anchor of the parent item to insert the title under.")
    ] = None,
) -> DocumentUpdateOutput:
    """Insert a title by specifying sibling_anchor or append a title by specifying parent_anchor in a Docling Document object.
    """
    if not shared.document:
        raise ValueError(
            "Document has not been initialized. Please load a document first."
        )
    
    if sibling_anchor:
        try:
            sibling = resolve(sibling_anchor)

            if sibling.parent is None or sibling.parent == shared.document.body.get_ref():
                parent = shared.document.body
            else:
                parent = resolve(sibling.parent)
        except ValueError as e:
            raise ValueError(
                f"Invalid sibling-anchor: {sibling_anchor}. "
            ) from e

        if isinstance(parent, GroupItem):
            if parent.label == GroupLabel.LIST or parent.label == GroupLabel.ORDERED_LIST:
                raise ValueError(
                    "You are attempting to insert a title within a list, which is not allowed. Please choose a different location to insert the title"
                )

        item = shared.document.insert_title(sibling=sibling, text=title, after=insert_after)

        return DocumentUpdateOutput(shared.document.export_to_dict(), item.self_ref)
    if parent_anchor:
        try:
            parent = resolve(parent_anchor)
        except ValueError as e:
            raise ValueError(
                f"Invalid parent-anchor: {parent_anchor}. "
            ) from e

        if isinstance(parent, GroupItem):
            if parent.label == GroupLabel.LIST or parent.label == GroupLabel.ORDERED_LIST:
                raise ValueError(
                    "You are attempting to append a title within a list, which is not allowed. Please choose a different location to append the title"
                )

        item = shared.document.add_title(parent=parent, text=title)

        return DocumentUpdateOutput(shared.document.export_to_dict(), item.self_ref)

    item = shared.document.add_title(text=title)

    return DocumentUpdateOutput(shared.document.export_to_dict(), item.self_ref)


@mcp.tool(title="Insert or append a section heading to Docling document")
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
    sibling_anchor: Annotated[
        str | None, Field(description="The anchor of the sibling item to insert the section heading before/after.")
    ] = None,
    insert_after: Annotated[
        bool, Field(description="Whether to insert the section heading after the sibling item. Defaults to inserting before.")
    ] = False,
    parent_anchor: Annotated[
        str | None, Field(description="The anchor of the parent item to insert the section heading under.")
    ] = None,
) -> DocumentUpdateOutput:
    """Insert a section heading by specifying sibling_anchor or append a section heading by specifying parent_anchor in a Docling Document object.

    Section levels typically represent heading hierarchy (e.g., 1 for H1, 2 for H2).
    """
    if not shared.document:
        raise ValueError(
            "Document has not been initialized. Please load a document first."
        )
    
    if sibling_anchor:
        try:
            sibling = resolve(sibling_anchor)

            if sibling.parent is None or sibling.parent == shared.document.body.get_ref():
                parent = shared.document.body
            else:
                parent = resolve(sibling.parent)
        except ValueError as e:
            raise ValueError(
                f"Invalid sibling-anchor: {sibling_anchor}. "
            ) from e

        if isinstance(parent, GroupItem):
            if parent.label == GroupLabel.LIST or parent.label == GroupLabel.ORDERED_LIST:
                raise ValueError(
                    "You are attempting to insert a section heading within a list, which is not allowed. Please choose a different location to insert the section heading"
                )

        item = shared.document.insert_heading(sibling=sibling, text=section_heading, level=section_level, after=insert_after)

        return DocumentUpdateOutput(shared.document.export_to_dict(), item.self_ref)
    if parent_anchor:
        try:
            parent = resolve(parent_anchor)
        except ValueError as e:
            raise ValueError(
                f"Invalid parent-anchor: {parent_anchor}. "
            ) from e

        if isinstance(parent, GroupItem):
            if parent.label == GroupLabel.LIST or parent.label == GroupLabel.ORDERED_LIST:
                raise ValueError(
                    "You are attempting to append a section heading within a list, which is not allowed. Please choose a different location to append the section heading"
                )

        item = shared.document.add_heading(parent=parent, text=section_heading, level=section_level)

        return DocumentUpdateOutput(shared.document.export_to_dict(), item.self_ref)
    
    item = shared.document.add_heading(text=section_heading, level=section_level)

    return DocumentUpdateOutput(shared.document.export_to_dict(), item.self_ref)


@mcp.tool(title="Insert or append a paragraph to Docling document")
def add_paragraph_to_docling_document(
    paragraph: Annotated[
        str, Field(description="The text content to add as a paragraph.")
    ],
    sibling_anchor: Annotated[
        str | None, Field(description="The anchor of the sibling item to insert the paragraph before/after.")
    ] = None,
    insert_after: Annotated[
        bool, Field(description="Whether to insert the paragraph after the sibling item. Defaults to inserting before.")
    ] = False,
    parent_anchor: Annotated[
        str | None, Field(description="The anchor of the parent item to insert the paragraph under.")
    ] = None,
) -> DocumentUpdateOutput:
    """Insert a paragraph by specifying sibling_anchor or append a paragraph by specifying parent_anchor in a Docling Document object.
    """
    if not shared.document:
        raise ValueError(
            "Document has not been initialized. Please load a document first."
        )
    
    if sibling_anchor:
        try:
            sibling = resolve(sibling_anchor)

            if sibling.parent is None or sibling.parent == shared.document.body.get_ref():
                parent = shared.document.body
            else:
                parent = resolve(sibling.parent)
        except ValueError as e:
            raise ValueError(
                f"Invalid sibling-anchor: {sibling_anchor}. "
            ) from e

        if isinstance(parent, GroupItem):
            if parent.label == GroupLabel.LIST or parent.label == GroupLabel.ORDERED_LIST:
                raise ValueError(
                    "You are attempting to insert a paragraph within a list, which is not allowed. Please choose a different location to insert the paragraph"
                )

        item = shared.document.insert_text(sibling=sibling, text=paragraph, label=DocItemLabel.TEXT, after=insert_after)

        return DocumentUpdateOutput(shared.document.export_to_dict(), item.self_ref)
    if parent_anchor:
        try:
            parent = resolve(parent_anchor)
        except ValueError as e:
            raise ValueError(
                f"Invalid parent-anchor: {parent_anchor}. "
            ) from e

        if isinstance(parent, GroupItem):
            if parent.label == GroupLabel.LIST or parent.label == GroupLabel.ORDERED_LIST:
                raise ValueError(
                    "You are attempting to append a paragraph within a list, which is not allowed. Please choose a different location to append the paragraph"
                )

        item = shared.document.add_text(parent=parent, text=paragraph, label=DocItemLabel.TEXT)

        return DocumentUpdateOutput(shared.document.export_to_dict(), item.self_ref)
    
    item = shared.document.add_text(text=paragraph, label=DocItemLabel.TEXT)

    return DocumentUpdateOutput(shared.document.export_to_dict(), item.self_ref)


@mcp.tool(title="Insert or append a list group to Docling document")
def add_list_group_to_docling_document(
    sibling_anchor: Annotated[
        str | None, Field(description="The anchor of the sibling item to insert the list group before/after.")
    ] = None,
    insert_after: Annotated[
        bool, Field(description="Whether to insert the list group after the sibling item. Defaults to inserting before.")
    ] = False,
    parent_anchor: Annotated[
        str | None, Field(description="The anchor of the list group item to insert the paragraph under.")
    ] = None,
) -> DocumentUpdateOutput:
    """Insert a list group by specifying sibling_anchor or append a list group by specifying parent_anchor in a Docling Document object.

    List items can only be added to a list group, so this tool is the necessary first step when attempting to create a new list.
    """
    if not shared.document:
        raise ValueError(
            "Document has not been initialized. Please load a document first."
        )
    
    if sibling_anchor:
        try:
            sibling = resolve(sibling_anchor)

            if sibling.parent is None or sibling.parent == shared.document.body.get_ref():
                parent = shared.document.body
            else:
                parent = resolve(sibling.parent)
        except ValueError as e:
            raise ValueError(
                f"Invalid sibling-anchor: {sibling_anchor}. "
            ) from e

        item = shared.document.insert_list_group(sibling=sibling, after=insert_after)

        return DocumentUpdateOutput(shared.document.export_to_dict(), item.self_ref)
    if parent_anchor:
        try:
            parent = resolve(parent_anchor)
        except ValueError as e:
            raise ValueError(
                f"Invalid parent-anchor: {parent_anchor}. "
            ) from e

        item = shared.document.add_list_group(parent=parent)

        return DocumentUpdateOutput(shared.document.export_to_dict(), item.self_ref)
    
    item = shared.document.add_list_group()

    return DocumentUpdateOutput(shared.document.export_to_dict(), item.self_ref)


@dataclass
class ListItem:
    """A class to represent a list item pairing."""

    list_item_text: Annotated[str, Field(description="The text of a list item.")]
    list_marker_text: Annotated[str, Field(description="The marker of a list item.")]

@dataclass
class DocumentBatchUpdateOutput:
    """Output of the tools that update the Docling document with multiple items."""

    document: Annotated[
        object, Field(description="The json representation of the document.")
    ]
    anchors: Annotated[
        list[str] | None, Field(description="A list of the document anchors of the items that were updated or created.")
    ]

@mcp.tool(title="Insert or append items to list in Docling document")
def add_list_items_to_list_in_docling_document(
    list_items: Annotated[
        list[ListItem],
        Field(description="A list of list_item_text and list_marker_text items."),
    ],
    sibling_anchor: Annotated[
        str | None, Field(description="The anchor of the sibling item to insert the list items before/after.")
    ] = None,
    insert_after: Annotated[
        bool, Field(description="Whether to insert the list items after the sibling item. Defaults to inserting before.")
    ] = False,
    parent_anchor: Annotated[
        str | None, Field(description="The anchor of the parent item to insert the list items under.")
    ] = None,
) -> DocumentBatchUpdateOutput:
    """Insert list items by specifying sibling_anchor or append list items by specifying parent_anchor in a Docling Document object.

    List items will be added with their specified text and marker.
    """
    if not shared.document:
        raise ValueError(
            "Document has not been initialized. Please load a document first."
        )
    
    if sibling_anchor:
        try:
            sibling = resolve(sibling_anchor)

            if sibling.parent is None or sibling.parent == shared.document.body.get_ref():
                parent = shared.document.body
            else:
                parent = resolve(sibling.parent)
        except ValueError as e:
            raise ValueError(
                f"Invalid sibling-anchor: {sibling_anchor}. "
            ) from e

        if not isinstance(parent, GroupItem) or parent.label not in (GroupLabel.LIST, GroupLabel.ORDERED_LIST):
            raise ValueError(
                "You are attempting to insert list items outside of a list, which is not allowed. Please choose a different location to insert the list items."
            )

        refs = []

        for list_item in reversed(list_items):
            item = shared.document.insert_list_item(
                text=list_item.list_item_text,
                marker=list_item.list_marker_text,
                sibling=sibling,
                after=insert_after,
            )

            refs.append(item.self_ref)

        return DocumentBatchUpdateOutput(shared.document.export_to_dict(), refs)
    if parent_anchor:
        try:
            parent = resolve(parent_anchor)
        except ValueError as e:
            raise ValueError(
                f"Invalid parent-anchor: {parent_anchor}. "
            ) from e

        if not isinstance(parent, GroupItem) or parent.label not in (GroupLabel.LIST, GroupLabel.ORDERED_LIST):
            raise ValueError(
                "You are attempting to append list items outside of a list, which is not allowed. Please choose a different parent under which to append the list items."
            )
        
        refs = []

        for list_item in reversed(list_items):
            item = shared.document.add_list_item(
                text=list_item.list_item_text,
                marker=list_item.list_marker_text,
                parent=parent
            )

            refs.append(item.self_ref)

        return DocumentBatchUpdateOutput(shared.document.export_to_dict(), refs)
    
    raise ValueError(
        "List items much be added under a group (list or ordered list) parent. Thus, either a sibling_anchor or parent_anchor must be provided."
    )


@mcp.tool(title="Insert or append an HTML table to Docling document")
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
    sibling_anchor: Annotated[
        str | None, Field(description="The anchor of the sibling item to insert the table before/after.")
    ] = None,
    insert_after: Annotated[
        bool, Field(description="Whether to insert the table after the sibling item. Defaults to inserting before.")
    ] = False,
    parent_anchor: Annotated[
        str | None, Field(description="The anchor of the parent item to insert the table under.")
    ] = None,
    table_captions: Annotated[
        list[str] | None,
        Field(description="A list of caption strings to associate with the table.."),
    ] = None,
    table_footnotes: Annotated[
        list[str] | None,
        Field(description="A list of footnote strings to associate with the table."),
    ] = None,
) -> DocumentUpdateOutput:
    """Insert an HTML-formatted table by specifying sibling_anchor or append an HTML-formatted table by specifying parent_anchor in a Docling Document object.

    This tool parses the provided HTML table string, converts it to a structured table
    representation, and inserts/appends it to the existing shared Docling Document
    object. It also supports optional captions and footnotes for the table.
    """
    if not shared.document:
        raise ValueError(
            "Document has not been initialized. Please load a document first."
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
        if sibling_anchor:
            try:
                sibling = resolve(sibling_anchor)

                if sibling.parent is None or sibling.parent == shared.document.body.get_ref():
                    parent = shared.document.body
                else:
                    parent = resolve(sibling.parent)
            except ValueError as e:
                raise ValueError(
                    f"Invalid sibling-anchor: {sibling_anchor}. "
                ) from e

            if isinstance(parent, GroupItem):
                if parent.label == GroupLabel.LIST or parent.label == GroupLabel.ORDERED_LIST:
                    raise ValueError(
                        "You are attempting to insert a table within a list, which is not allowed. Please choose a different location to insert the table"
                    )

            table = shared.document.insert_table(data=conv_result.document.tables[0].data, sibling=sibling, after=insert_after)

            for _ in reversed(table_footnotes  or []):
                footnote = shared.document.insert_text(label=DocItemLabel.FOOTNOTE, text=_, sibling=table, after=insert_after)
                table.footnotes.insert(0, footnote.get_ref())
            
            for _ in reversed(table_captions or []):
                caption = shared.document.insert_text(label=DocItemLabel.CAPTION, text=_, sibling=table, after=insert_after)
                table.captions.insert(0, caption.get_ref())

            return DocumentUpdateOutput(shared.document.export_to_dict(), table.self_ref)
        if parent_anchor:
            try:
                parent = resolve(parent_anchor)
            except ValueError as e:
                raise ValueError(
                    f"Invalid parent-anchor: {parent_anchor}. "
                ) from e

            if isinstance(parent, GroupItem):
                if parent.label == GroupLabel.LIST or parent.label == GroupLabel.ORDERED_LIST:
                    raise ValueError(
                        "You are attempting to append a title within a list, which is not allowed. Please choose a different location to append the title"
                    )

            table = shared.document.add_table(data=conv_result.document.tables[0].data, parent=parent)

            for _ in table_captions or []:
                caption = shared.document.add_text(label=DocItemLabel.CAPTION, text=_, parent=parent)
                table.captions.append(caption.get_ref())

            for _ in table_footnotes or []:
                footnote = shared.document.add_text(label=DocItemLabel.FOOTNOTE, text=_, parent=parent)
                table.footnotes.append(footnote.get_ref())

            return DocumentUpdateOutput(shared.document.export_to_dict(), table.self_ref)
        
        table = shared.document.add_table(data=conv_result.document.tables[0].data)

        for _ in table_captions or []:
            caption = shared.document.add_text(label=DocItemLabel.CAPTION, text=_)
            table.captions.append(caption.get_ref())

        for _ in table_footnotes or []:
            footnote = shared.document.add_text(label=DocItemLabel.FOOTNOTE, text=_)
            table.footnotes.append(footnote.get_ref())

        return DocumentUpdateOutput(shared.document.export_to_dict(), table.self_ref)
    else:
        raise ValueError(
            "Could not parse the html string of the table! Please fix the html and try again!"
        )