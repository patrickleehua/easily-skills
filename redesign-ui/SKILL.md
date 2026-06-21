---
name: redesign-ui
description: This skill should be used when the user wants to redesign the UI/UX of an existing product based on extracted UI/UX specs. It performs diagnosis, sets design strategy, redesigns information architecture, and produces detailed interaction specs plus a visual design system. Triggers on /redesign-ui or when the user says things like "帮我重新设计UI/UX", "基于现有体验重做前端", "生成体验设计规范". Reads output/uiux-extraction-*.md produced by the extract-ui skill as input. Outputs a UI/UX spec document and a tool-agnostic prototype generation prompt.
---

# redesign-ui

Redesign the UI/UX of an existing product based on extracted UI/UX specs. Produce a comprehensive experience specification and a tool-agnostic prototype generation prompt.

## Trigger

Activated by `/redesign-ui [module-name]` or natural language requests to redesign or reimagine a product's UI/UX.

## Step 0: Load Input

Look for extraction files in `output/uiux-extraction-*.md`:

- **If one file exists** → load it automatically.
- **If multiple files exist** → list them and ask the user which module to redesign.
- **If no file exists** → ask the user to paste the feature list, page descriptions, or business workflow description directly.

## Step 1: Current State Diagnosis

Before designing anything, analyze the input extraction file and list the top 5–7 experience problems:

- **Information architecture issues**: too many nav levels, unclear page grouping, hidden features
- **Interaction friction**: too many clicks for common tasks, inconsistent patterns, missing shortcuts
- **State gaps**: missing empty states, error recovery, loading feedback
- **Visual inconsistency**: mixed color values, typography chaos, no spacing system
- **Accessibility concerns**: color-only indicators, missing focus states, poor contrast

Present these as a numbered list with a one-line explanation each. Ask the user if they agree or want to add/remove items before proceeding.

## Step 2: Design Goals & Strategy

Define the redesign's purpose:

1. **Primary design goals** (1–2): what must improve?
   - Example: "Reduce task completion time from 5 clicks to 3 clicks"
   - Example: "Establish a unified design system to eliminate visual inconsistency"
2. **Target users**: who is this for? Any persona or role changes?
3. **Scope decision**: redesign in place, or restructure IA (merge/split pages)?
4. **Constraint notes**: any tech stack limitations, must-keep features, or brand requirements?

Summarize in 3–4 sentences. Ask the user to confirm or edit before proceeding.

## Step 3: Detect Tech Stack

Read `package.json` (or `pubspec.yaml` for Flutter, `build.gradle` for Android native) to detect the frontend tech stack.

Common detections:
- React + Ant Design / MUI / shadcn/ui / Tailwind
- Vue + Element Plus / Naive UI / Vuetify
- Next.js / Nuxt.js
- Flutter
- SwiftUI / Jetpack Compose

If detection fails or is ambiguous, ask the user: "请问前端使用什么技术栈？（如 React + Tailwind、Vue + Element Plus、Flutter 等）"

## Step 4: Select Target Platform

Ask the user to select one or more target platforms:

```
请选择目标平台（可多选）：
1. Web 桌面端（1280px+）
2. Web 移动端（375px 基准，响应式）
3. iOS App（Human Interface Guidelines）
4. Android App（Material Design 3）
5. 微信小程序（750rpx 基准）
6. 支付宝小程序
7. Electron 桌面客户端
8. 平板端（iPad / Android Tablet，768px+）
9. 大屏数据看板（1920px+）
```

Apply platform-specific constraints in all subsequent output:
- Web desktop: sidebar navigation, dense information layout, keyboard shortcuts
- Mobile web / mini-program: bottom tab bar, thumb-friendly touch targets (min 44px), pull-to-refresh
- iOS: SF Symbols conventions, safe area insets, native sheet patterns, swipe-back
- Android: Material You color roles, FAB placement, predictive back gesture
- Large screen dashboard: grid-based widget layout, real-time data zones, multi-column views

## Step 5: Recommend Theme and Style

Based on the product type inferred from the feature list, recommend 2–3 style directions. For each direction provide:

- Direction name (e.g., "简洁商务型")
- Primary color + accent color (hex)
- Typography pairing suggestion
- Visual density (compact / comfortable / spacious)
- One-line mood description
- Why it fits this product type

Ask the user to choose one direction or describe their own preference before proceeding.

Product type → style heuristics:
- Admin / back-office → neutral grays, blue accent, compact density
- Consumer app → warm palette, rounded corners, comfortable density
- Data dashboard → dark background, cyan/amber data colors, compact density
- E-commerce → high contrast, bold CTA colors, product-photo-first layout
- Developer tool → monospace elements, dark mode default, minimal chrome
- Healthcare / finance → conservative blues/greens, high legibility, spacious layout

## Step 6: Information Architecture Redesign

Propose a new IA based on the diagnosed problems and design goals:

- **New page hierarchy tree**: what pages exist, how they nest, what was merged or split
- **Navigation redesign**: nav items, groups, ordering, icons
- **Route changes**: old route → new route mapping if URLs change
- **Entry point optimization**: how users get to each page (fewer clicks? new shortcuts?)
- **Access control updates**: any auth/role changes

Include a brief rationale for each structural change ("Merged 'Settings' and 'Profile' because users toggled between them 80% of the time").

## Step 7: Page Specifications

For every page/screen in the redesigned IA, write a detailed spec:

```markdown
### [Page Name]

**User goal**: What does the user want to accomplish here?
**Entry paths**: Where do users come from to reach this page?
**Exit paths**: Where can they go next?
**Core actions**: Primary CTA + secondary actions

**Layout**:
- Navigation pattern: [top nav / sidebar / bottom tab / drawer]
- Grid: [columns and gutter, responsive breakpoints]
- Key zones: [header / content / aside / footer] with relative priority
- Z-index layering: modals, drawers, toasts, sticky headers

**Content hierarchy**:
1. Primary information (must see immediately)
2. Secondary information (supports primary)
3. Auxiliary information (available on demand)

**Components**:
| Component | Type | State Variants | Notes |
|-----------|------|----------------|-------|

**States**:
- Empty state: [description + CTA]
- Error state: [description + recovery action]
- Loading state: [skeleton / spinner / progressive loading strategy]
- Success state: [description + feedback]
- Partial/Degraded state: [if applicable, e.g., offline mode]
```

## Step 8: Interaction Specifications

Define cross-page and in-page interaction behavior:

- **State transitions**: For every major action, document the full chain:
  ```
  User clicks [X] → UI shows [loading indicator] → API responds → 
  If success: [feedback] + [navigation/animation] → [next state]
  If error: [error display] + [retry option]
  ```
- **Animation / motion spec**:
  - Page transitions: type (slide, fade, scale), duration, easing
  - Micro-interactions: button press, checkbox toggle, dropdown open
  - Loading animations: skeleton wave, spinner, progress fill
- **Keyboard shortcuts**: if desktop, list key bindings for power users
- **Gesture support**: if mobile/touch, list swipe, pinch, long-press actions
- **Focus management**: tab order, focus traps in modals, skip links
- **Undo / confirmation patterns**: destructive actions, bulk operations

## Step 9: Visual Design System

Document the complete design system for implementation:

### Design Tokens
| Token | Value | Usage |
|-------|-------|-------|
| Primary | #XXXXXX | CTAs, active states, links |
| Primary Hover | #XXXXXX | Hover states |
| Surface | #XXXXXX | Page background |
| Surface Elevated | #XXXXXX | Cards, modals |
| Text Primary | #XXXXXX | Headlines, body |
| Text Secondary | #XXXXXX | Captions, meta |
| Text Inverted | #XXXXXX | On primary color |
| Border | #XXXXXX | Dividers, input borders |
| Success / Warning / Error / Info | #XXXXXX each | Semantic feedback |

### Typography Scale
| Level | Size | Weight | Line Height | Usage |
|-------|------|--------|-------------|-------|

### Spacing Scale
| Token | Value | Usage |
|-------|-------|-------|

### Shape
| Token | Radius | Usage |
|-------|--------|-------|

### Elevation
| Level | Shadow | Usage |
|-------|--------|-------|

### Component States
For each major component type, define:
- Default / Hover / Active / Disabled / Focus / Error visual treatment
- Color, border, shadow, and opacity changes

### Icon Rules
- Library: [name]
- Size scale: [sm / md / lg values]
- Color inheritance rules
- When to use filled vs outlined variants

### Responsive Breakpoints
| Name | Width | Layout Change |
|------|-------|---------------|

## Step 10: Generate Output

Produce two artifacts saved under `output/`:

### Artifact 1: UI/UX Specification — `output/uiux-spec-[module].md`

Combine all sections from Steps 6–9 into a single comprehensive document. Include a summary at the top:

```markdown
# UI/UX Design Spec: [Module Name]

**Platform**: [selected platforms]
**Tech stack**: [detected or user-provided]
**Style direction**: [chosen direction + primary color]
**Generated at**: [date]

## Summary
- Design goals: [list]
- Pages redesigned: [count]
- Key interaction changes: [2–3 bullets]
- Accessibility improvements: [list]

---

## 1. Information Architecture
[From Step 6]

## 2. Page Specifications
[From Step 7 — one section per page]

## 3. Interaction Specifications
[From Step 8]

## 4. Visual Design System
[From Step 9]

## 5. Migration Notes
[What breaks, what stays, rollout order]
```

### Artifact 2: Prototype Prompt — `output/uiux-prototype-[module].md`

Write a tool-agnostic structured prompt that any generative UI tool (v0, Figma AI, Galileo AI, etc.) can consume. Include:

1. Product type and purpose (one sentence)
2. Target platform and screen dimensions
3. Style direction: color palette, typography, visual density
4. Redesigned page/screen list with layout description per screen
5. Key components and their states
6. Interaction behaviors and transitions to represent
7. What NOT to include (avoid generic AI-looking templates, purple gradients, emoji icons, placeholder text)

End the prompt file with a section titled `## Tool-Specific Hints` with brief notes for:
- v0 (Vercel): how to phrase for React code generation
- Figma AI: how to phrase for design file generation
- Galileo AI: how to phrase for wireframe generation
- MasterGo / 即时设计: Chinese UI tool phrasing tips

## Step 11: Confirm to User

After writing both files, report:
- Paths of both output files
- Summary of: pages designed, platforms covered, style chosen, top 3 UX improvements
- Highlight any breaking changes from the old UI (route changes, removed pages, renamed nav items)
- Next steps:
  - Hand off prompt to a generative tool
  - Implement with `/super-dev` using the spec as the design contract
  - Iterate on specific pages if user has feedback

If the user requests changes (e.g., "换一个风格", "这个页面布局不对"), stay in redesign mode and update the affected sections before re-confirming.
