---
name: excalidraw-diagram
description: Generate architecture diagrams, flowcharts, and visual documentation as Excalidraw files (.excalidraw). Use this skill when the user asks for a diagram, architecture visualization, flowchart, system design drawing, or any visual representation of code structure, data flow, or system components. Also trigger on "draw", "diagram", "visualize architecture", or "system overview".
---

# Excalidraw Diagram Generator

Create clean, readable diagrams as `.excalidraw` JSON files that can be opened in Excalidraw.

## Supported Diagram Types

- System architecture diagrams
- Data flow diagrams
- Component relationship maps
- Flowcharts and decision trees
- Sequence flows
- Module dependency graphs

## Process

1. Understand what needs to be visualized
2. Identify components, connections, and flow direction
3. Generate valid Excalidraw JSON with proper element positioning
4. Save as `.excalidraw` file

## Excalidraw JSON Structure

Each element needs: `id`, `type`, `x`, `y`, `width`, `height`, `strokeColor`, `backgroundColor`, `text` (for text elements).

Use `rectangle` for boxes, `arrow` for connections, `text` for labels.

## Layout Guidelines

- Space elements evenly (min 200px between components)
- Flow left-to-right or top-to-bottom
- Group related components visually
- Use consistent colors: same color for same type of component
- Keep text short and readable
- Label all arrows with relationship type
