# Bible Brain UI/UX Redesign Plan

## Design approval tracker

This is the **living design specification**, not an implementation instruction. Discuss and approve each item before coding. Codex should **not implement this redesign until explicitly instructed**.

| Task | Design status | Implementation status |
|---|---|---|
| 1. Main Scripture reader | **Approved — 18 November 2026** | Not started |
| 2. Study Companion | To discuss | Not started |
| 3. Reading / Exploration / Mapping modes | To discuss | Not started |
| 4. Word and phrase interaction | To discuss | Not started |
| 5. Trace reading experience | To discuss | Not started |
| 6. Consolidate research tools | To discuss | Not started |
| 7. Study workspace | To discuss | Not started |
| 8. Evidence status visual language | To discuss | Not started |
| 9. Visual and responsive polish | To discuss | Not started |
| 10. Regression and acceptance checks | To discuss | Not started |

## Task 1 — Approved main-screen design

**Status: Design approved; no code changes authorised by this document.**

### Purpose and visual reference

The main screen should feel like opening and reading a Bible, rather than operating a database or research dashboard. Use the user-provided **Living Bible Study** screenshot as the principal visual reference: dark forest green, cream Scripture text, restrained green/gold accents, elegant serif reading typography, generous verse spacing, simple navigation, and a contextual right-hand Study Companion. Borrow the **visual and interaction language**, not the older application's backend.

### Approved behaviour

- **Bible as home:** Launch directly into the Scripture reader. Scripture is the dominant central view; no wall of Research, Discuss, AI, Lenses, Graph or Discovery panels.
- **Study Companion closed by default:** On app launch, the reader has the available reading space. Opening and resizing the companion is defined in later tasks.
- **Navigation:** A slim desktop navigation (Bible, Study, Explore, Traces, Library); compact navigation on phones. Provide book, chapter and translation selection, plus direct passage/verse navigation.
- **Continuous reading:** Scroll naturally from chapter to chapter within a book, with clear chapter headings instead of separate chapter pages.
- **Smart chapter indication:** The displayed chapter follows the passage currently being read as the user scrolls, without unexpectedly moving the reader.
- **Resume reading:** Reopening Bible Brain restores the last passage and scroll position.
- **Reading controls:** Adjustable font size, line spacing and reading-column width, with a comfortable centred reading column on wide screens.
- **Clean selection:** Users can select verses, words and phrases without cluttering or interrupting Scripture. Research actions attached to selection will be defined in Task 4.
- **Responsive experience:** Desktop and mobile layouts should retain clear navigation, comfortable typography, touch-friendly selections and minimal wasted space.
- **No data-layer rebuild:** Preserve existing Scripture/translations, Strong's references, Scripture anchors, studies, traces, conversations, graph, reviews and local-first data.
- **Large-book usability:** Keep scrolling and navigation responsive for long books; implementation details are for Codex to determine when authorised.

### User journey and acceptance criteria

1. Open Bible Brain to a clean reader at the remembered passage and reading position.
2. Change book/chapter/translation or jump directly to a verse without losing navigation clarity.
3. Scroll across successive chapters; the current chapter label tracks the reading position.
4. Change typography settings and continue reading in a comfortable column on desktop or mobile.
5. Select an individual word, phrase or verse without disrupting reading or invoking an unwanted panel.
6. Confirm the Study Companion is initially closed and the existing research/study data remains intact.

### Explicitly deferred — do not assume approval

- Whether scrolling continues automatically from one *book* to the next, rather than between chapters within a book.
- Whether reading settings and position sync across devices or remain local.
- Exact text-selection toolbar and research actions (Task 4).
- Study Companion sizing, animation and open-state handling (Task 2).
- Additional Living Bible Study features and their placement (later tasks).
- Detailed Exploring/Mapping behaviour and AI placement (later tasks).

## Product direction

Bible Brain should feel like this:

> Scripture first, connections hidden until requested, research revealed contextually.

The current data model is strong, but the interface exposes the architecture as separate technical panels. The redesign should make the Scripture reader the permanent home and reveal the knowledge graph only when the user chooses to explore.

The guiding principle is:

> Bible Brain should behave like an ordinary scroll when reading, but like a deeply interconnected research tool when exploring.

## 1. Make the reader the permanent home

The default screen should prioritize:

- Bible, book and chapter navigation.
- Comfortable Scripture typography.
- Verse selection.
- Word and phrase selection.
- Translation selection.
- A small, discoverable Explore control.

The reader should not be surrounded by a wall of competing Research, Explore, Discuss, Lenses, Conversations and Discover controls. Advanced tools should remain hidden or contextual until needed.

## 2. Add three explicit reading modes

### Reading mode

- Clean Scripture only.
- No graph markers or research overlays.
- No AI panel.
- The visual experience should resemble reading a book.

### Exploration mode

- Meaningful words and phrases may receive subtle highlights or underlines.
- Selecting a phrase opens a compact contextual panel.
- Show related passages, repeated expressions, original-language information, traces, studies and evidence status.

### Mapping mode

- The selected word, phrase, symbol or verse becomes the centre of a relationship view.
- Show connected passages and traces.
- Allow navigation through the network.
- Keep speculative links visually distinct from direct textual relationships.

The existing Explore and graph backend should be reused behind these modes rather than presented as unrelated database screens.

## 3. Build a Study Companion panel

Use one contextual side panel instead of many independent panels. Suggested tabs:

- Conversation
- Discoveries
- Research
- Sources
- Original language
- Trace

The companion opens beside the selected passage and closes without changing the reader.

Example:

```text
Revelation 2:7
────────────────────────────
He that hath an ear...
...to eat of the tree of life...
────────────────────────────
Study Companion
[Connections] [Trace] [Research]

Tree of Life
Revelation 22:2
Revelation 22:14
Genesis 3:22

Relationship:
Promise → restored access

Status:
Textual connection / user reviewed
```

## 4. Make words and phrases first-class research objects

The interaction should make expressions such as `tree of life`, `overcometh`, `stars`, `candlesticks`, `throne`, `witnesses` and `Babylon` feel like meaningful research entities.

Required experience:

- Select a word or phrase.
- Give the selection a stable Scripture anchor.
- View related occurrences.
- Open Strong's/original-language information where available.
- See trace membership.
- See attached studies and connections.
- Open a compact phrase detail panel.

Reuse the existing Scripture anchor, token and graph tables. This is primarily an interaction and presentation improvement.

## 5. Make Trace the central interaction

Trace should not feel like a management form.

Reader workflow:

1. Select `tree of life`.
2. Choose `Trace`.
3. Temporarily highlight all Tree of Life members.
4. Navigate between members.
5. View the trace sequence or member list.
6. Close Trace.
7. Return to a completely clean reader.

Trace needs two experiences:

- Management: create, edit, colour and order traces.
- Reading: follow an active trace through Scripture.

The reading experience is the priority.

## 6. Make evidence distinctions visible

Use a consistent visual language:

- Scripture: neutral, authoritative text.
- Direct textual repetition: strong but restrained marker.
- Original-language evidence: separate lexical badge.
- User observation: note colour.
- Interpretation: provisional/amber colour.
- Possible relationship: dotted or muted treatment.
- Rejected or parked material: hidden by default.

The database already stores review status. The interface must make those distinctions immediately understandable.

## 7. Replace technical names with user intentions

Prefer user actions over implementation labels.

| Technical label | User-oriented label |
|---|---|
| Investigate | Ask about this passage |
| Graph | Explore connections |
| Lenses | Interpret through a lens |
| Conversation | Import study conversation |
| Discovery | Find possible connections |

Suggested primary navigation:

- Bible
- Study
- Explore
- Traces
- Library

Advanced controls can live inside these areas.

## 8. Create a real Study workspace

A study should feel like a living research document with:

- Title.
- Summary.
- Connected passages.
- Observations.
- Questions.
- Interpretations.
- Conclusions.
- Attached traces.
- Source history.
- Related conversations.
- Related discoveries.

The structured study database is already suitable. The editor and dossier view need to become more readable and research-oriented.

## 9. Move AI into the context panel

AI should not dominate the top-level navigation. From a selected passage, offer:

- Ask about this passage.
- Interpret through lens.
- Challenge this interpretation.
- Compare with connected passages.

Display the answer with retrieved evidence, citations, model information, provisional status and Keep / Investigate / Park / Reject controls.

## 10. Adopt the stronger visual language from LivingBibleStudy

Use the older app as a UX reference for:

- Calm green/cream palette.
- Clear top-level navigation.
- Strong reader typography.
- Contextual companion panel.
- Study-centric language.
- Friendly empty states.
- Fewer simultaneous controls.
- Modal editors instead of database-looking forms.
- Clear local/private research messaging.

Do not replace Bible Brain's database or local-first architecture with the older app's backend.

## Implementation sequence

- [ ] 1. Rebuild the main shell around Bible as the default view.
- [ ] 2. Add a contextual right-side Study Companion.
- [ ] 3. Implement Reading, Exploration and Mapping modes.
- [ ] 4. Make phrase selection open the companion.
- [ ] 5. Turn Trace into a reader interaction.
- [ ] 6. Move Research, Conversations, Lenses and Discoveries into companion tabs.
- [ ] 7. Improve study editing and the study dossier presentation.
- [ ] 8. Add visual evidence-status treatment.
- [ ] 9. Polish typography, spacing, empty states and responsive behaviour.
- [ ] 10. Re-run regression and acceptance tests after each milestone.

## Definition of success

The user can read Scripture without distraction, select a meaningful word or phrase, open its hidden connections, follow a trace, inspect evidence and research, and close the exploratory layer to return to a clean reading experience.

Nothing speculative should look established, and no AI result should become retained knowledge without an explicit user decision.
