# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`openscad_docsgen` is a Python package that generates GitHub-flavored Markdown documentation from inline comments in OpenSCAD source files. It can also generate images by running OpenSCAD on embedded example scripts. Two CLI tools are provided: `openscad-docsgen` (doc generation) and `openscad-mdimggen` (image generation from Markdown).

## Development Setup

```bash
# Install in editable mode with dependencies
uv sync

# Run a command in the project environment
uv run openscad-docsgen --help
```

## Running the Tools

```bash
# Generate docs for all .scad files in current dir, output to ./docs/
openscad-docsgen -m *.scad

# Generate everything: per-file docs, TOC, index, topics, cheatsheet, sidebar
openscad-docsgen -mticIs *.scad

# Test-only mode (run scripts, no image output)
openscad-docsgen -m -T *.scad

# Use a different output directory and profile
openscad-docsgen -D wikidir -p wiki *.scad

# Process Markdown files to generate images from embedded OpenSCAD fences
openscad-mdimggen input.md
```

## Architecture

The main processing pipeline:

1. **`__init__.py` / `main()`** — CLI entry point; parses arguments into an `Options` object and calls `processFiles()`.
2. **`parser.py` / `DocsGenParser`** — Core parser. Reads `.openscad_docsgen_rc` config file at startup, then parses `.scad` files line by line, recognizing `// HEADER: value` comment patterns. Builds a tree of `Block` objects. Dispatches image generation through `image_manager` and `log_manager`.
3. **`blocks.py`** — Block class hierarchy (`GenericBlock`, `FileBlock`, `SectionBlock`, `ItemBlock`, `LabelBlock`, `TableBlock`, `BulletListBlock`, etc.). Each block holds a title, subtitle, body, origin info, parent, and children. Blocks render themselves to Markdown via the target object.
4. **`imagemanager.py` / `ImageRequest`** — Wraps `openscad_runner` to run OpenSCAD and generate PNG/GIF images. Parses image metadata tags (e.g., `3D`, `Spin`, `VPD=440`, `ColorScheme=BeforeDawn`).
5. **`logmanager.py`** — Manages async/queued image rendering requests.
6. **`target_wiki.py` / `Target_Wiki`** — Base class for output formatting (Markdown rendering helpers).
7. **`target_githubwiki.py` / `Target_GitHubWiki`** — Subclass with GitHub Wiki–specific HTML image alignment.
8. **`target.py`** — Registry of target profiles: `"githubwiki"` (default) and `"wiki"`.
9. **`filehashes.py`** — Tracks source file hashes to avoid regenerating unchanged images.
10. **`errorlog.py`** — Collects and reports warnings/errors; optionally writes `docsgen_report.json`.
11. **`mdimggen.py`** — Standalone tool that scans Markdown for ` ```openscad-METADATA ` fenced blocks and generates images.

## Configuration File (`.openscad_docsgen_rc`)

Place in the working directory. Key options:
- `DocsDirectory:`, `TargetProfile:`, `ProjectName:`
- `GeneratedDocs: Files, ToC, Index, Topics, CheatSheet`
- `IgnoreFiles:` / `PrioritizeFiles:` (one per line, supports globs)
- `DefineHeader(Type): HeaderName` — adds custom headers with types like `BulletList`, `Table`, `Text`

## Comment Syntax in OpenSCAD Files

A documentation block is a header line optionally followed by body lines:

```
// Header: optional subheader text
//   Body line one.
//   Body line two.
```

The header line matches `// CapitalizedHeader: subheader`, where the subheader is optional for some header types. Body lines follow immediately after and are identified by having more spaces of indentation between `//` and the text than the header line does (header uses one space; body uses two or more).

Key structural headers:
- `// LibFile:` / `// File:` — file-level block
- `// Section:` — section within a file
- `// Function:` / `// Module:` / `// Constant:` / `// Function&Module:` — item blocks
- `// Alias:` / `// Aliases:` — registers alternate names
- `// Arguments:` — two-column table (By Position / By Name)
- `// Example:` / `// Examples:` — code blocks that trigger image generation

## Adding a New Target Profile

1. Create `target_<name>.py` subclassing `Target_Wiki`.
2. Override rendering methods as needed.
3. Register in `target.py` under `target_classes`.
