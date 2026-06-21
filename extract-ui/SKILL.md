---
name: extract-ui
description: This skill should be used when the user wants to reverse-engineer an existing codebase to extract its UI/UX structure, interaction patterns, visual assets, and business workflows into a structured Markdown spec. Triggers on /extract-ui or when the user says things like "提取这个项目的界面和交互", "帮我分析这个产品的体验现状", "把现有代码的UI结构整理出来". The output is saved as output/uiux-extraction-[module].md and serves as input for the redesign-ui skill.
---

# extract-ui

Reverse-extract the UI/UX structure, interaction patterns, visual assets, and business workflows from an existing codebase into a structured Markdown spec file.

## Trigger

Activated by `/extract-ui [module-name]` or natural language requests to analyze existing code UI/UX.

- If `[module-name]` is omitted, perform a global scan of the entire codebase and use `overview` as the module name.
- If `[module-name]` is provided (e.g., `/extract-ui dashboard`), scope the analysis to files and routes related to that module.

## Step 1: Detect Project Type

Before scanning, determine whether the project has a frontend:

- Check for `src/`, `pages/`, `components/`, `views/`, `app/` directories.
- Check `package.json` for frontend frameworks (React, Vue, Next.js, Nuxt, Angular, etc.).

**If frontend code exists** → extract frontend UI structure, interaction patterns, visual assets, and API calls.

**If no frontend exists (backend-only)** → extract backend business logic, route definitions, request/response contracts. Describe the interaction as if explaining to a UI designer what the system does and what data it exposes. Skip visual asset extraction.

## Step 2: Extract Five Dimensions

### Dimension 1: Information Architecture (IA)

Map the current navigation and page structure:

- **Page hierarchy tree**: All routes → pages → nested views
- **Navigation pattern**: sidebar / top nav / bottom tab / drawer / breadcrumb
- **Entry points**: How does the user arrive at each page (URL, nav click, redirect, modal)
- **Page responsibility**: One-sentence description of what each page does
- **Access control**: Which pages require auth, which have role-based access

### Dimension 2: Component & Interaction Patterns

Identify the building blocks and recurring interaction habits:

- **Layout framework**: overall grid system, content areas, responsive breakpoints
- **Reusable component inventory**:
  - Data display: table / list / card / grid / calendar / timeline
  - Input: form / filter / search / upload
  - Feedback: modal / drawer / toast / notification / inline error
  - Navigation: tabs / accordion / menu / pagination / breadcrumb
- **Recurring interaction patterns**: describe each as "User does X → system responds with Y"
  - Example: "User clicks filter → drawer opens → selects values → table refreshes inline"
  - Example: "User submits form → inline validation → API call → success toast → redirect to list"
- **Modal/drawer usage rules**: what triggers overlay vs. page navigation

### Dimension 3: Visual Assets

Reverse-extract the design system from code:

- **CSS framework / UI library**: Tailwind / Ant Design / MUI / shadcn/ui / Element Plus / etc.
- **Color palette**:
  - Primary / secondary brand colors
  - Semantic colors: success, warning, error, info
  - Surface colors: background, card, elevated
  - Text colors: primary, secondary, disabled, inverted
- **Typography**:
  - Font family stack
  - Type scale: sizes for display / H1-H6 / body / caption / label
- **Spacing system**: base unit, common increments used
- **Shape**: border radius values used (small pill, medium card, large modal)
- **Shadow / elevation**: levels used for cards, modals, dropdowns
- **Icons**: library name (Lucide / Heroicons / AntD icons / etc.) and common usage
- **Motion**: any standard transition durations or easing functions found in CSS/JS

### Dimension 4: User Flows & States

Map how users complete tasks and how the UI behaves across conditions:

- **Core task flows**: For each primary user goal, list the click-by-click path
  - Example: "Create Order: List page → Click 'New' → Form page → Fill → Submit → Success → List with new item"
- **State matrix** for each key page/component:
  | Page/Component | Initial | Loading | Empty | Error | Success |
  |----------------|---------|---------|-------|-------|---------|
  | Product Table  | —       | Skeleton| Empty illustration | Inline retry | Checkbox batch actions |
- **Feedback patterns**:
  - Success feedback: toast / inline banner / modal confirmation / redirect
  - Error feedback: field-level / form-level / page-level / modal retry
  - Loading feedback: skeleton / spinner / progress bar / blur overlay
- **Empty states**: What is shown when there is no data? Is there a CTA to create?
- **Error recovery**: Can the user retry? Is there a fallback route?

### Dimension 5: Business Interface Mapping (UI-relevant only)

Extract only the APIs that directly feed the UI or are triggered by user actions:

- **Page initialization APIs**: endpoints called when a page loads
- **Action APIs**: endpoints triggered by buttons, form submissions, toggles
- **Real-time interfaces**: WebSocket, SSE, polling endpoints
- **Key request/response fields** relevant to UI rendering
- **Error states** that the UI must handle (401 redirect, 403 disabled, 422 field errors, 500 retry)

Omit pure backend-internal services, message queues, or admin-only RPCs unless they produce user-visible effects.

## Step 3: Write Output File

Save the result to `output/uiux-extraction-[module-name].md`. Create the `output/` directory if it does not exist.

Use this structure:

```markdown
# UI/UX Extraction: [Module Name]

**Project type**: Frontend + Backend / Backend only
**Tech stack**: [detected stack]
**Extracted at**: [date]

---

## 1. Information Architecture

### Page Hierarchy
[Tree structure or indented list]

### Navigation Pattern
[Description + list of nav items and their targets]

### Access Control
[Which routes require auth/roles]

---

## 2. Component & Interaction Patterns

### Layout Framework
[Grid, breakpoints, content areas]

### Component Inventory
[Table: Component | Type | Used on Pages | Notes]

### Recurring Interaction Patterns
[Numbered list of "User does X → system responds with Y"]

### Overlay Usage Rules
[When modal vs drawer vs page navigation is used]

---

## 3. Visual Assets

### Design System
- CSS Framework: [name]
- Icon Library: [name]

### Color Palette
[Table: Token | Hex | Usage]

### Typography
[Font stack + type scale table]

### Spacing & Shape
[Base unit, common increments, border radius values]

### Elevation
[Shadow levels and their usage]

### Motion
[Transition durations and easing if found]

---

## 4. User Flows & States

### Core Task Flows
[Numbered flows with step-by-step paths]

### State Matrix
[Table: Page/Component | Initial | Loading | Empty | Error | Success]

### Feedback Patterns
- Success: [description]
- Error: [description]
- Loading: [description]

---

## 5. Business Interface Mapping

### Page Initialization APIs
[Endpoint | Page | Purpose | Key Response Fields]

### Action APIs
[Endpoint | Trigger | Purpose | Key Request Fields | Expected UI Feedback]

### Error Handling
[HTTP Status | UI Behavior]
```

## Step 4: Confirm to User

After writing the file, report:

- The output file path
- Count of: pages found, components identified, task flows mapped, APIs extracted
- Any areas where extraction was uncertain or incomplete (e.g., "empty states not implemented in code", "color values mixed across hardcoded and theme files")
- Top 3 UX friction points visible from the code (e.g., "no loading state on submit", "inconsistent error feedback between pages")

Suggest running `/redesign-ui` next if the user wants to redesign the experience based on this extraction.
