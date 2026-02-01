# Three-Step Workflow Implementation Plan

## Overview
Complete redesign of ProcessingWindow into three distinct steps with clear visual progression.

## Step 1: Document Stitching
### UI Layout
```
┌─────────────────────────────────────────────────────────────┐
│ Document Stitching                          Step 1 of 3     │
├─────────────────────────────────────────────────────────────┤
│ [Thumbnail Strip - 200px high - confirmed pages]            │
├──────────┬────────────────────────────────┬─────────────────┤
│          │                                │                 │
│ Spinner  │   Large Page Preview           │  [Exclude Page] │
│ Loading  │   (Current page being          │                 │
│ Anim     │    analyzed by Ollama)         │  [Include Page] │
│          │                                │                 │
│          │                                │                 │
├──────────┴────────────────────────────────┴─────────────────┤
│ Status: Analyzing page 5 of 20... (3s elapsed)              │
└─────────────────────────────────────────────────────────────┘
```

### Workflow
1. Load next unprocessed page
2. Display in large preview
3. Show spinner on left
4. Send to Ollama for validation
5. User can:
   - Wait for Ollama → auto-include if YES, prompt if NO
   - Click "Include Page" → add to group, show next page
   - Click "Exclude Page" → end stitching, move to Step 2

## Step 2: Document Analysis
### UI Layout
```
┌─────────────────────────────────────────────────────────────┐
│ Document Analysis                           Step 2 of 3     │
├─────────────────────────────────────────────────────────────┤
│ [Thumbnail Strip - 200px high - clickable to change view]   │
├──────────┬────────────────────────────────┬─────────────────┤
│ Company: │                                │                 │
│ [______] │                                │  [Continue]     │
│          │   Large Page Preview           │  (appears when  │
│ Title:   │   (Click thumbnails            │   Ollama done)  │
│ [______] │    to change view)             │                 │
│          │                                │  [Cancel]       │
│ Date:    │                                │  (stop Ollama)  │
│ [______] │                                │                 │
│          │                                │  [Abort]        │
│          │                                │  (exit)         │
├──────────┴────────────────────────────────┴─────────────────┤
│ Status: Extracting metadata... (5s elapsed)                 │
└─────────────────────────────────────────────────────────────┘
```

### Workflow
1. Show all pages in thumbnail strip
2. Automatically send to Ollama for metadata extraction
3. User can click thumbnails to view different pages
4. When Ollama responds:
   - Populate Company, Title, Date fields
   - Show "Continue" button
5. User can:
   - Edit fields
   - Click "Continue" → move to Step 3
   - Click "Cancel" → stop Ollama, complete manually
   - Click "Abort" → return to main window

## Step 3: Document Finalization
### UI Layout
```
┌─────────────────────────────────────────────────────────────┐
│ Document Finalization                       Step 3 of 3     │
├─────────────────────────────────────────────────────────────┤
│ [Thumbnail Strip - 200px high - final pages]                │
├──────────┬────────────────────────────────┬─────────────────┤
│          │                                │                 │
│  PDF     │   Large Page Preview           │ [Accept &       │
│  Info    │   (Final document)             │  Delete Sources]│
│          │                                │                 │
│  Pages:5 │                                │ [Accept &       │
│  Search  │                                │  Keep Sources]  │
│  able:Y  │                                │                 │
│          │                                │ [Reject &       │
│          │                                │  Delete PDF]    │
├──────────┴────────────────────────────────┴─────────────────┤
│ Status: PDF created successfully                            │
└─────────────────────────────────────────────────────────────┘
```

### Workflow
1. Create PDF from selected pages
2. Show PDF info
3. Display final pages
4. User chooses:
   - Accept & Delete Sources
   - Accept & Keep Sources
   - Reject & Delete PDF

## Implementation Notes
- Each step has different side panel content
- Thumbnail strip persists across all steps
- Large page preview persists across all steps
- Status bar shows step-appropriate messages
- Smooth transitions between steps
