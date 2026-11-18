# Bible Brain — UI/UX Redesign Specification

**Document status:** Rewritten and consolidated for final user review — 18 November 2026.
**Application status:** NOT IMPLEMENTED. This document does not authorise code changes, database migrations, installation, deployment or release.
**Purpose:** One authoritative design specification for the existing standalone, local-first Bible Brain application. Preserve its existing Scripture, Strong's/original-language, anchor, graph, research, trace, study, conversation and review data.

## 0. Decisions, authority and reading guide

| Task | Design decision authority | Implementation |
|---|---|---|
| 1. Bible reader | **Explicitly approved by user** | Not started |
| 2. Study Companion | **Explicitly approved by user** | Not started |
| 3. Reading / Exploration / Mapping | **Explicitly approved by user** | Not started |
| 4. Scripture selection and actions | **Explicitly approved by user** | Not started |
| 5. Trace reading and editing | **Explicitly approved by user** | Not started |
| 6. Consolidated research | **Six user-approved choices; remaining details assistant-proposed** | Not started |
| 7. Study workspace | **Assistant-proposed under delegated authority; review pending** | Not started |
| 8. Evidence and review visual language | **Assistant-proposed under delegated authority; review pending** | Not started |
| 9. Visual and mobile design | **Assistant-proposed under delegated authority; review pending** | Not started |
| 10. Regression and release gates | **Assistant-proposed under delegated authority; review pending** | Not started |

**Approval rule:** The user approved Tasks 1–5 and six specific decisions in Task 6. The user then asked the assistant to choose the remaining design details and prepare one completed file for review. Assistant choices are proposals for that final review, not individually user-approved changes to the app.

**Source-of-truth rule:** Each requirement appears once in its task, with cross-cutting state and data contracts in Sections A–C. Those contracts explain how to implement approved behaviour; if a technical detail would materially change an explicitly approved interaction, stop and seek a revised decision. Do not follow outdated draft/legacy headings from the earlier file. The original plan is preserved separately as a single pre-cleanup copy.

### Product goal

> Read Scripture like a book. Explore its connections deliberately. Follow meaning through the Bible without losing context. Keep evidence separate from interpretation and retain nothing as approved knowledge without the user's explicit decision.

- **Scripture is the home**, not an AI chat dashboard or database administration screen.
- **Bible structure is a tree; research is a graph.** The UI shows ordered books/chapters/verses while relationships connect anchored occurrences, subjects, traces, studies and sources.
- **Local-first and standalone.** Reuse Bible Brain's existing data layer. Do not attach this app to the separate Revelation Explorer website or replace its backend with another product.
- **Existing work is safe.** Reading, navigation, search, AI requests and layout restoration do not silently change saved research, anchors or review status.

### Three different navigation levels — do not mix them up

| Level | Controls | Responsibility |
|---|---|---|
| **App destinations** | **Bible · Study · Explore · Traces · Library** | Switch the large workspace. Bible is the launch destination. Existing functions stay reachable. |
| **Reader modes** | **Reading · Exploration · Mapping** | Control how Scripture/relationships are presented. Manual selector; app launches in Reading. |
| **Study Companion tabs** | **Connections · Traces · Studies** | Three permanent context layers within the one Companion panel; one tab's content visible at a time. |

The label **Explore** has two contexts. The top-level Explore destination opens the app's existing broader exploration tools/entry point; **Explore** on a selected word in the floating toolbar **pins that exact anchored investigation in the Companion**. Neither action silently approves evidence. Do not create a fourth Companion tab for AI, Lenses, Research or Conversations.

### User-facing terminology

| Internal/legacy term | Preferred user-facing action |
|---|---|
| Investigate | Ask about this passage |
| Graph | Explore connections |
| Lenses | Interpret through a lens |
| Discovery | Find possible connections |
| Conversation import | Import study conversation |

These are presentation labels, not permission to remove data, APIs or modules.

## A. Non-negotiable invariants

1. **Scripture text is immutable in ordinary reading and research workflows.** Annotations, links and interpretation live in separate records.
2. **One exact Scripture occurrence is not the same as its spelling.** Matching the words “tree of life” elsewhere does not create a saved anchor or Trace member automatically.
3. **Pinned investigation changes only on explicit Explore of an anchored selection or explicit selection from Recent Investigations.** Mere Bible navigation, AI output, tab switches, Trace selection, Mapping or research expansion do not repin it.
4. **Reader location, temporary selection, pinned investigation, active Companion tab, active Trace and edited Study are distinct states.** One must not silently overwrite another.
5. **No unsolicited AI work.** Launching, scrolling, switching modes, opening/restoring sections and browsing saved links do not automatically run discovery, summarisation or external AI.
6. **Evidence kind and review status are independent.** Approved interpretation remains interpretation; an unreviewed suggestion remains provisional.
7. **Local UI memory is not approved knowledge.** Persisting an expanded section or conversation does not create or approve a graph link.
8. **One active Trace reader session** at a time; only user-defined saved Trace members receive its temporary highlights.
9. **No destructive cascading writes** from removing a study attachment, clearing Recent Investigations, collapsing a panel or switching Trace.
10. **No app modification until explicitly authorised after design review.** The present contract is a specification, not an execution order.

## B. Shared UI-state contract — required before new screens

**Implementation direction (assistant proposal, validate against the repository):** Use one coherent state ownership model, not scattered tab-local state copies.

| State group | Owned values | Persistence |
|---|---|---|
| **Reader state** | Book, chapter, translation, current top visible Scripture anchor, its viewport-relative offset, typography settings, reader mode | Last location + reading preferences saved locally |
| **Temporary Scripture selection** | Exact selected anchor/range and toolbar visibility | In-memory; never becomes a record merely on selection |
| **Pinned investigation** | Stable investigation ID, originating Scripture anchor, subject/title, active Companion tab | Local; changes only on explicit Explore/history choice |
| **Companion layout** | Open/closed, panel width/sheet size, section open states by investigation ID and tab | UI layout locally; section states survive app restarts |
| **Recent investigations** | Up to **50** IDs, most recently visited first | Local; Clear history requires confirmation and deletes navigation history only |
| **Trace session** | Active Trace ID, active member ID/index, session-origin reader snapshot, temporary highlight set | Session-only; switching traces retains the SAME original return snapshot |
| **Mapping session** | Origin reader snapshot, focus, preview, Follow history stack, pan/zoom | Current mapping session; Back only follows explicit Follow steps |
| **Study workspace** | Open Study ID, editor draft/saved state, return-to-reader snapshot | Saved studies local; unfinished edits protected |
| **AI research context** | Current investigation-specific conversation/thread ID, retrieved evidence IDs, current request/result state | Local conversation history; query/response is not approved knowledge |

**State-transition rules**

| User action | Allowed changes | Must remain unchanged |
|---|---|---|
| Select Scripture words | Temporary selection and toolbar only | Pinned investigation, saved data, mode |
| **Explore** selected words | Pin exact anchored investigation, open/focus Companion, append old pin to Recent history | Reader position, reader mode; keep current Companion tab |
| **Trace** selected words | Open temporary Trace picker in Traces tab; optional explicit choose/create/add | Pinned investigation and recent-history entries |
| Switch Companion tab | Visible tab/content | Scripture location, pinned subject and other tabs' section states |
| Follow cross-reference | Reader destination | Pinned subject and active Companion research context |
| Enter Mapping | Mapping focus from selected anchor, else pin | Origin reader snapshot; pinned subject |
| Preview / Follow map node | Preview only / explicit new map focus and Follow history | Pinned subject and retained origin reader location |
| Start Trace | Trace session, initial member, temporary highlights and navigator | Origin reader snapshot and pin |
| Switch Trace | Active Trace and active member | Original Trace-session return snapshot and saved Trace records |
| Free-scroll in Trace | Reader scroll location | Active Trace member index, saved order, origin snapshot |
| Close entire Trace journey | Clear Trace UI and return to origin reader anchor/offset | Saved Trace data, pin, Companion context |
| Open/close research result | Section open flag; explicit request may produce provisional result | Saved review states, pin, active Trace |
| Save/Approve/Reject | Only the specifically selected destination/record after explicit action | Unrelated research, Scripture, other candidates |

**Persistence design:** Use existing local storage/SQLite facilities if suitable; verify the actual schema and migrations first. Keep UI layout metadata separate from research approvals. Write state changes atomically where possible, debounce frequent scroll/layout updates, flush on normal shutdown, and gracefully recover from interrupted writes. Stable IDs rather than section titles or display text must identify a saved investigation, Trace member, research section and conversation. Treat deleted/missing IDs as unavailable without rewriting surviving user data.

## C. Scripture anchor and exact-position contract

**One canonical anchor model, backed by existing Scripture IDs/tokens where possible:**

- Stable source book ID, chapter, start verse and end verse (where applicable), displayed translation/edition identifier, and **start/end token or word positions**. Retain exact selected text as a verification snapshot, **not** as the unique identifier.
- Each occurrence has an anchor ID stable within its source edition. The same English phrase in another verse or a different place in the same verse is a different anchor. Multi-verse selections use a range, not an invented one-verse citation.
- Specify tokenisation and punctuation/Unicode boundaries in the repository audit; support selections beginning/ending mid-verse and across verse boundaries. Never base identity solely on a displayed DOM node or its pixel coordinates.
- **Translation changes do not silently change anchor identity.** Keep the original selection's edition and exact positions. Cross-translation mapping, if supported by existing data, is an explicit, visibly labelled mapping with an uncertainty/failure state; otherwise open the source edition when following that anchor.
- Original-language/Strong's evidence must be tied to an **actual occurrence and lemma/identifier**, not a naive string match in English. If original-language coverage is absent, say so.
- For saved links and Traces, show a readable passage/reference plus the exact anchor and edition internally; resolve/validate references before jumping or highlighting.

**Return-to-position algorithm:**

1. Snapshot the **top visible verse/token anchor**, its relative offset from the reader viewport, active translation and reading settings when entering Trace, Mapping or full Study.
2. On returning, first restore the source book/translation and render the target passage, then scroll to the anchored location and adjust its relative viewport offset. On an unchanged layout, this should visually match the prior position.
3. If the viewport width, font, layout or translation changed, **prefer an accurate Scripture-anchor return over an impossible promise of identical pixels**; give the reader an intelligible location and preserve its source edition.
4. In a Trace journey, capture the origin **once**. Switching Traces or free-scrolling never overwrites it. Closing the final session restores that original anchor.
5. Test across page resizing, translation changes, chapter boundaries, delayed content rendering, mobile rotation, Study return and Mapping return. Do not claim exact restoration until these tests pass.

## Task 1 — Main Scripture reader [USER APPROVED]

**Purpose:** The Bible opens like a book, not a dashboard.

- On every launch, enter **Bible** in **Reading** mode with the **Study Companion closed**. Restore the last remembered Bible passage/scroll while keeping research overlays out of the way.
- Desktop navigation remains **Bible, Study, Explore, Traces, Library**. Provide clear book/chapter/verse and translation controls and a simple way to enter a passage reference directly.
- Scroll **continuously between chapters within the same book** with clear chapter headings; update the visible chapter indicator while scrolling. At a book boundary offer deliberate **Next book** navigation, not an unexpected jump into another book.
- Scripture remains in a centred, comfortably readable column. Offer adjustable **font size, line spacing and reading width** and save those settings locally.
- Selecting text does not automatically open a research panel, invoke AI or save material; the four-action toolbar in Task 4 appears only on deliberate selection.
- The theme follows the user-approved Living Bible Study visual reference: forest green and warm cream, restrained gold/green accents, elegant readable serif Bible typography and uncluttered navigation. Borrow visual direction only, never its backend.
- The reader must work with mouse, keyboard and touch; remain responsive through long books; and retain original-language/anchor data independently of the visible translation.

**Acceptance gates:** Launch into clean Scripture with Companion closed; jump to exact book/verse; scroll through chapters; see current chapter update; change translation without losing the identity of saved anchors; resize typography and reopen to the correct anchored location. No startup AI or automatic research calls.

## Task 2 — Study Companion [USER APPROVED]

**One Companion panel, exactly three permanently visible tabs: Connections | Traces | Studies.** A tab remains visible even when it has no content.

- **Connections:** contextual cross-references, direct repetition, parallel passages, source evidence, original-language/Strong's occurrence detail and comparative research. Each link opens actual Scripture with evidence type/status visible.
- **Traces:** related thematic traces, selection/creation and explicit Trace editing controls; activation enters the in-reader Trace experience from Task 5.
- **Studies:** anchored existing studies, observations, questions, interpretations, conclusions, approved discoveries, saved conversations and relevant research actions.
- On **desktop**, the Companion sits to the right of Scripture with a **draggable width divider**. Both Scripture and the panel remain visible. Closing it restores reading width; it is not a permanent wall of controls.
- On **phones**, use a **drag-resizable bottom sheet** over the reader. The three tabs remain accessible at the sheet's top; closing the sheet reveals the same Bible reading location. Do not create an unrelated full-screen replacement page.
- The Companion remains focused on the **pinned investigation** even as the Bible reader follows other passages, Traces or map links. Only an explicit **Explore** on a new anchored selection, or choosing an item from Recent Investigations, changes the pin.
- Explicit **Explore** switches to the new pin immediately; retain the previous pin in **Recent Investigations**, with a locally persisted list of the **50 most recent subjects** in recency order. A compact History control opens this list.
- **Clear history** requires confirmation and removes only the recent-navigation entries, not investigation records, saved studies, traces, source links, approved discoveries or Scripture.
- **No Reset/Unpin control.** Selecting a new Scripture anchor and pressing Explore starts the next investigation.
- Switching tabs retains the active pinned subject and Bible position. Closing/reopening the Companion restores the current pin, active tab and available research context. If there is no earlier active tab, initially show Connections.
- Provide empty states; make the relevant action accessible from the correct tab rather than hiding tools in a generic top-level technical dashboard.

**Acceptance gates:** Desktop resizable right panel; mobile resizable bottom sheet; three functional visible tabs; pin survives changing Bible passages; 50-entry persistent history and confirmed Clear; tab/pin/context survive panel closing and reopening; no incidental research approval.

## Task 3 — Reading, Exploration and Mapping [USER APPROVED]

**Manual mode selector:** Always accessible but unobtrusive **Reading | Exploration | Mapping**. A mode is a presentation/workspace choice, not a Companion tab. On every app launch use **Reading**, even if another mode was used last time. Manually switching modes does not replace the pinned investigation or lose the saved reader position.

### Reading

- Clean, continuous Scripture without research markers, graph overlays or a permanent AI pane.
- The short floating selection toolbar may still appear when the user deliberately selects text; it does not itself change the mode.
- A deliberately activated Trace may place its temporary, exact-anchor marks/navigation in the normal reader under Task 5; that is a user-requested reading overlay, not automatic Exploration mode.

### Exploration

- Add restrained, inspectable markers only for **existing stored** Connections, Traces and Studies. An unreviewed AI possibility is not presented as an established link.
- A compact **Filters** menu near the mode selector has three **independent** visibility controls: **Connections**, **Traces**, **Studies**. Their names match Companion tabs, but they only control marks on Scripture, not the Companion's contents.
- On first use **all three filters are enabled**. Thereafter store the chosen combination **locally across mode changes and app restarts**. It is valid to hide all markers. Filter changes do not alter saved evidence.
- New semantic/Meaning Engine/AI connections appear only following an explicit **Find possible connections** action, marked as candidates. Exploration entry alone must never run discovery.
- Scripture selection still follows **Task 4**; do not use the obsolete behaviour “selection automatically opens a contextual panel.”

### Mapping

- Open a **large relationship workspace that temporarily replaces the central Scripture area**, rather than forcing the map into the Companion.
- Choose initial focus by priority: the currently **explicitly selected Scripture anchor**; if none, the **pinned investigation**; if neither, a straightforward passage/subject picker. No mandatory map-library landing page.
- Show connected Scripture passages/traces/subjects with visible **evidence kind** and **review status**. Support zoom and pan.
- Clicking/tapping a node opens a **preview** of Scripture and supporting evidence without moving the map centre. **Follow** explicitly recentres on that node and adds it to a map-session history stack; **Back** reverses followed-focus steps, not mere previews.
- Exiting Mapping restores the originating Bible anchor and viewport-relative position; the pinned investigation remains unchanged. Use the shared return contract in Section C.

**Acceptance gates:** Mode switching is manual; Reading is default and uncluttered; filters are independent and persist; fresh suggestions never auto-appear; Mapping focus priority, preview-before-Follow, Back, zoom/pan and precise anchored return all behave correctly.

## Task 4 — Exact Scripture selection and toolbar [USER APPROVED]

Selecting a word, phrase, verse or multi-verse range creates a **temporary exact anchor** and reveals a **small floating toolbar with Explore | Trace | Save | Copy**. Selection alone does not persist a record, start AI, replace a pin or switch reader mode. Controls must work for both mouse text selection and phone touch handles.

### Explore

- **Open/focus the existing Companion** on the exact selected occurrence. Explicitly set that selection as the new **pinned investigation**; keep the current Reading/Exploration/Mapping mode unchanged.
- Retain the previous investigation in Recent Investigations (maximum 50).
- Keep the Companion's current active tab, so a new Explore subject updates the tab's context without jumping back to Connections. If no tab was ever chosen, use Connections.
- Never approve a suggested link or trigger AI merely by pressing Explore.

### Trace

- Open a **temporary selection-specific Trace picker** in the Companion's Traces tab. This temporary Trace context is distinct from the pinned investigation.
- Present matching saved traces and explicit **Choose / Create new / Add selected anchor to existing trace** actions. Do not automatically activate the first match or attach the same phrase from a different occurrence.
- When dismissed without choosing, return to the prior pinned subject and previous Companion tab/content without changing Scripture scroll. Choosing/creating/adding remains explicit and must not silently replace the pin or add to Recent Investigations.
- The actual in-reader Trace reading session begins only after an explicit Trace choice as specified in Task 5.

### Save

Open a compact menu with **exactly three primary destinations**: **Bookmark**, **Add to existing study**, **Create research subject**. Opening the menu writes nothing.

- **Bookmark** stores the exact anchored selection for revisit, without an invented interpretation.
- **Add to existing study** requires choosing the destination study and preserves its existing content.
- **Create research subject** uses the anchored selection and a deliberate name; it does not automatically create a Trace or include suggested other occurrences.
- If a subject with the same/closely matching name already exists, explicitly choose **Reuse/link existing** or **Create separate**. No silent merge or duplicate.

### Copy

Copy the **exact selected text** and its correct **book/chapter/verse or verse range and displayed translation**. For example: **“tree of life” — Revelation 2:7 (KJV)**. Do not expand a phrase into an entire verse or alter its wording; Copy is read-only.

### Connection suggestions

- A search may propose exact-word matches, other occurrences, lexical relationships or semantic parallels. Label each one by the **type of evidence**, source passage and limitations.
- A candidate is **not** a saved member or approved relationship until its own **Approve** action is taken. **Reject** is likewise individual. Keep pending, approved and rejected distinct; never bulk-approve on open.
- Approval of a proposed interpretation must **not** reclassify it as a textual or original-language fact.
- Preserve all exact selection/translation rules in Section C.

**Acceptance gates:** Four-action toolbar; each action's explicit side effects and non-side effects; stable multi-verse anchor and Copy reference; no unwanted mode/pin changes; duplicate subject choice; individual evidence-linked approval/rejection; mobile usability.

## Task 5 — Trace reading and management [USER APPROVED]

**Design priority:** A Trace should feel like following a biblical thought through the normal reader, not completing a database form.

### Starting and navigation

- After deliberate Trace selection in Task 4, activate **one Trace reading session inside the normal Scripture reader**. Do not launch a list of disconnected excerpts or a second reader.
- If the currently selected anchored occurrence is a member of the chosen Trace, start at **that member's place in the saved sequence**; otherwise start at its **first saved member**. Match by exact anchor/member identity, not text spelling.
- **Previous / Next follows the user's saved Trace-member order**, not canonical Genesis-to-Revelation order. Show the passage reference and progress such as **2 of 4**.
- At the **first** member, Previous is disabled; at the **last**, Next is disabled. **Never loop.** If a Trace has one member, both are disabled; list and Close remain available.
- The compact floating navigator lives **in the Bible reader independently of the Companion**, showing Trace name/switcher, passage/progress, Previous/Next, ordered passage-list control and Close.
- The **compact passage list** shows every member in saved order. Tapping one jumps the normal reader to that exact passage, updates the active member and closes/returns from the list without modifying the Trace's order.
- **Free Scripture scrolling remains available**, including outside current Trace passages. The active member and progress indicator **do not change** merely because the user scrolls over another Trace member; only explicit Previous/Next, passage-list selection or Trace switching changes the active step.

### Highlights and origin restoration

- Temporarily mark **only the exact saved anchors** of the currently active Trace, in its user-chosen colour. Do not highlight every repeated spelling in the Bible. Apply highlights to rendered visible verses, not a wasteful full-Bible DOM layer.
- Only **one Trace may be active** at a time. Switching to another saved Trace replaces temporary highlights/navigation without changing or erasing either saved Trace.
- Capture the **original Bible reading anchor, translation and viewport-relative position once** before the first Trace of that continuous session. Keep the same original return snapshot across every deliberate Trace switch and free scroll.
- Closing the entire Trace-reading journey removes its temporary marks and bar and restores that original location using Section C's anchored return algorithm. Closing does **not** change the pinned Companion subject, approve links or edit stored Trace membership.

### Separate Trace management

- Provide an explicit **Create / Rename / Change colour / Reorder members / Remove member** editing interface. The existing saved order is authoritative until deliberately edited.
- Merely opening a Trace, following it, inspecting its member list or switching traces never edits a record. Removing a member removes **only that membership**, not Scripture, unrelated source evidence or saved Studies.
- Make Trace controls reachable and touch-friendly on phones without covering the selected verse or conflicting with a raised Companion sheet.

**Acceptance gates:** One active reader Trace, exact occurrence highlights, custom order and selected-member start, non-looping endpoints, passage list, free scrolling without progress change, multi-Trace origin restoration, and editing strictly separated from reading.

## Task 6 — Consolidated research and Meaning Engine [SIX USER CHOICES APPROVED; REST DELEGATED]

**Companion architecture stays exactly three tabs.** Old technical functions (Research, Conversation, Lenses, Discovery, Sources, Original Language, Meaning Engine) must stay reachable **inside the relevant tabs**, not vanish during consolidation.

### The six explicitly approved interaction choices

1. **Contextual actions** appear in the relevant Companion tab, rather than exclusively behind one global Research menu.
2. Results open as **expandable sections in that same tab**, not in a separate research screen.
3. **Multiple research sections** may remain expanded independently at the same time. This does not require side-by-side columns on a narrow phone.
4. Switching Companion tabs remembers **each tab's own open/collapsed sections**.
5. Switching pinned investigations remembers **separate section layouts per investigation**; reopening one from Recent Investigations restores its original layout rather than another subject's.
6. Each investigation's section layout is **stored locally across application restarts** and restored when that investigation is reopened.

**Layout state is not the research itself.** Expanding, collapsing or restoring a section does not rerun AI, change a saved source, approve a discovery or replace the pinned subject.

### Concrete tool placement — assistant proposal

| Companion tab | Visible, relevant entry points | Deeper functionality |
|---|---|---|
| **Connections** | **Compare passages; Search occurrences; Original language / Strong's** | Source inspection, lexical comparisons, exact/repeated expressions, candidate relationship discovery and its evidence. |
| **Traces** | **Find trace; Follow trace; Create / Manage trace** | Matching Trace picker, explicit ordering/colour editing; approved reader Trace in Task 5. |
| **Studies** | **Ask about this passage; Open study; Interpret through a lens** | Ongoing research conversations, Challenge interpretation, Review discoveries, imported conversations, draft notes, source history and individual approval workflow. |

Show only the few actions relevant to the current content. A **local More control** may expose other functions without creating an additional permanent Companion tab or global wall of buttons. No action is implicitly a save or approval.

### Research-result display and persistence — assistant proposal

Keep **three different kinds of information separate**:

| Kind | Meaning | Storage / restoration behaviour |
|---|---|---|
| **UI layout** | Which research sections are expanded for investigation X / tab Y | Local, persistent across tab/subject switches and restarts. Never a knowledge-approval record. |
| **Research execution / conversation history** | Explicitly requested search/result/AI answer, query, source anchors, evidence citations, engine/time and provisional state | Stored/revisited according to existing local research/conversation capabilities; not auto-approved. A displayed result is not a graph fact. |
| **Reviewed knowledge** | User-authored study content or explicitly accepted candidate relationships | Separate durable records with evidence type and review decision; requires the corresponding explicit action. |

- Every section gets a stable identifier within its pinned investigation and tab. An expanded state points to that section ID, **not** its display title or a text string.
- Opening a result runs a query **only after the user invokes its action**. Reopening/restoring the layout **never automatically re-runs it**.
- If a previous result snapshot is available, display it as **“Previous result”** with source, query context, creation time and an explicit **Run again / Refresh** action. A refreshed result is a **new research execution**, not a silent rewrite of earlier evidence or approved findings.
- If the section was expanded but its prior content was not stored, removed or unavailable, retain a usable expanded placeholder: **“Previous result unavailable — run again”**. Do not invent result text or fetch from the network without consent.
- Local result caching, if supported, must be **bounded** (configurable maximum items/space) and distinct from persistent conversation history and approved knowledge. Cache eviction may remove temporary output but **must not** delete saved studies, conversations, Trace data, provenance or review records.
- A result tied to an older Scripture translation/edition or a different pinned subject remains labelled with its original context; do not silently repurpose it as an answer to a new question.
- A pending research job can be cancelled; display progress/errors plainly. If the model is offline, the user can still consult locally stored Scripture, connections, Traces and Studies.

### AI research conversation and memory — assistant proposal

**Choose ongoing, investigation-specific conversations rather than stateless one-answer cards.**

- The **Studies** tab contains an expandable ongoing discussion for the pinned investigation. Follow-ups continue the selected thread and may use earlier turns; a different pinned investigation has separate discussion context.
- **New discussion** deliberately starts a fresh thread attached to the same investigation while preserving older threads for reading. An imported existing conversation remains a source-linked object, not an automatically approved interpretation.
- An AI-generated answer shows its text, question/context, **model/engine when available**, selected lens, relevant evidence citations and a visible **Provisional / Not approved** label. No automatic save to a Study conclusion or graph relationship.
- Collapse/reopen, tab switching, restoration after restart and normal navigation do **not** send new model requests or silently re-summarise anything.

**Default bounded Retrieval-Augmented Generation (RAG) pipeline; validate token numbers with the actual local models:**

1. Receive the **explicit user question** with the current pinned investigation ID, precise Scripture anchor and translation; include a lens only when explicitly selected.
2. Query existing local Scripture/text/FTS, exact Strong's-lemma occurrences, relevant cross-references, reviewed studies and graph relationships. Preserve source IDs and distinguish **exact retrieval** from **semantic candidate retrieval**.
3. Rank evidence by relevance and source quality. A practical *initial* ceiling is **up to eight passage/evidence snippets** with source anchors; allow user-selected passages to receive priority. Every snippet must carry a traceable source/reference and applicable review state.
4. Include a bounded slice of recent **same-thread messages** (initially up to six recent exchanges) and a compact **same-thread rolling summary** when necessary; keep original conversation turns retrievable locally. Treat the rolling summary as an AI-produced convenience, **not** authoritative Scripture evidence.
5. Fit the assembled prompt to the actual model context window with a safety margin; **token budget wins over numeric examples**. Drop lower-ranked context before dropping the user's question or requested Scripture. Do not pass the entire Bible, all stored studies or unrelated conversations into one prompt.
6. Generate the response with source attribution, important counterevidence/limitations and accurate model/lens label. A cited retrieved snippet can be used as evidence; a previous AI statement is identified as conversation history, not independently verified evidence.
7. Store the new conversation turn and its provenance **locally** as provisional discussion history. Update a thread summary only when a configurable context threshold is crossed or the user explicitly requests it. Never silently promote the answer into a discovery, accepted connection or study conclusion.

**Retrieval failure behaviour:** If exact anchors cannot be resolved, a lemma is absent, citation retrieval fails or the local model is unavailable, display that fact. Do not fabricate verses, concordance IDs, sources or confidence scores. User approval is required before sending private local data to any external model/provider; nothing in this design enables an automatic sync or API connection.

### Lens and review workflow — assistant proposal

- Theological lenses are **editable user-defined research frameworks**. Selecting one is explicit and visibly labelled; its assumptions and conclusions remain separate from Scripture and original-language evidence. A lens switch does not rewrite prior saved answers or records.
- **Find possible connections** returns individual candidates with source passages, lexical/semantic rationale, known counterevidence and limitations. A quotation, an English verbal match and a theological interpretation are not interchangeable.
- Candidate-level actions: **Investigate** (inspect further), **Keep as draft** (explicit provisional note), **Park** (defer), **Reject** (record rejection), and **Approve connection** (explicitly accept that candidate). Do not use a single ambiguous **Keep** button to mean both “save this text” and “approve this relationship”.
- Each action applies only to its selected item, with its original evidence kind and provenance preserved; no automatic batch approval or interpretation-to-fact promotion.

**Acceptance gates:** Three permanently visible Companion tabs with preserved existing research tools; contextual actions; independent expandable sections and per-investigation/per-tab local layout memory; no automatic research on restore; ongoing per-investigation conversations with bounded evidence-first context; accurate lexical citations; review of individual candidates; offline/errors without invented output; mobile readability and stable pin.

## Task 7 — Study workspace [DELEGATED; FINAL REVIEW PENDING]

**Principle:** The Companion's **Studies** tab is a compact contextual doorway; the main **Study** destination is a calm, readable, long-form research document. Do not force full writing inside a narrow side panel.

### Study document structure

- **Title** and short **Summary** at the top.
- Separate, collapsible but accessible sections for **Connected Scripture passages**, **Observations**, **Questions**, **Interpretations**, **Conclusions**, **Attached Traces**, **Related research conversations**, **Related discoveries**, and **Source history**.
- Each Scripture attachment retains its **exact canonical anchor and originating translation**; show the readable reference and a way to **Open in Bible**.
- Clearly separate user-authored statements, quoted Scripture/source passages and provisional AI material. An attached AI conversation is a source/reference, not an approved conclusion.
- A study may link multiple anchored expressions, traces, discussions, sources and subjects without cloning or changing their underlying identities.

### Editing workflow

- From the Task 4 Save menu, **Add to existing study** asks which study; the anchored verse/phrase is attached only after the user confirms.
- Within a Study, provide explicit **Add observation**, **Add question**, **Add interpretation**, **Add conclusion**, **Link Scripture**, **Attach Trace**, **Attach conversation** and **Attach source** actions. Keep fields visually simple, with comfortable text editing rather than database-style forms.
- Support writing, editing and reordering study sections as existing data capabilities permit; identify unsupported rich-text features during the repository audit rather than promising an editor the stored schema cannot support.
- Persist authored changes locally with clear **Saved / Unsaved / Saving / Failed** feedback. Preserve a draft through accidental navigation or an interrupted write. Do not mistake automatic draft recovery for user-approved AI knowledge.
- Open long edits in the full Study workspace; brief contextual notes and research actions can remain in the Companion.
- A clear **Back to Bible** restores the reader anchor, translation and viewport-relative position captured when entering Study, along with the earlier pinned Companion investigation. Following a study's passage intentionally navigates to Scripture without replacing the pinned subject unless Explore is explicitly invoked.
- Removing a passage/Trace/Conversation attachment removes the **link only**, not the source object. Confirm destructive Study deletion and provide a verified recovery path where the existing storage supports it.
- The main Study destination supports title/subject search, recent-edit sorting and friendly empty states. Opening a search result reuses the existing Study record, not a duplicate.

**Acceptance gates:** One readable dossier with all required sections; correct anchored links; clean distinction between question/observation/interpretation/conclusion; usable desktop and mobile writing; saved drafts and safe unlinking; sources/provenance preserved; returning to the Bible retains its position and pinned investigation; no silent AI approval.

## Task 8 — Evidence and review language [DELEGATED; FINAL REVIEW PENDING]

**Critical correction to the earlier plan:** **Evidence type** and **review status** are **independent fields/labels**. “Parked” and “Rejected” are review statuses, **not evidence types**. An item can be an **approved interpretation**, a **pending lexical candidate**, or a **rejected semantic suggestion**, but approval never changes what the evidence actually is.

### Evidence type — what supports the claim?

| Evidence kind | Honest label and visual convention | Caution |
|---|---|---|
| **Direct Scripture / quotation** | Passage and translation; restrained solid textual/quotation marker if a research overlay is requested | The biblical text itself is not an AI claim. |
| **Exact textual repetition / verbal parallel** | Clearly labelled Text match / Verbal parallel with both source anchors | Repetition alone does not prove shared theological meaning. |
| **Original-language / lexical** | Distinct Hebrew/Greek/Strong's/lemma label with real occurrence-specific identification | Shared English spelling does not establish shared lemma; shared lemma does not establish interpretation. |
| **User observation** | “Observation” with a quiet note/pencil symbol, user attribution | Personal observation is not automatically direct biblical wording. |
| **Interpretation / lens-based reading** | “Interpretation” plus optional lens, with supporting evidence visible | A theological lens is an analytical choice, not a neutral lexical fact. |
| **Proposed semantic or thematic connection** | “Possible connection” with dotted/muted connector and evidence/limitations | This is a hypothesis until separately reviewed. |

**Scripture itself remains clean in Reading mode**. These labels appear on relevant Companion cards, research results, review history and graph relationships; the text-match or Trace overlay appears in the reader only under the relevant approved mode or deliberate Trace session.

### Review status — what decision has been made?

| Status | Meaning | Visibility |
|---|---|---|
| **Pending** | Candidate not yet reviewed | Visible as a proposal; never presented as established. |
| **Approved** | User explicitly accepted **that specific candidate** | Kept with evidence type unchanged; show review/provenance where available. |
| **Parked** | User deferred a candidate | Hidden from ordinary approved-connection overlays, available in review history. |
| **Rejected** | User declined a candidate | Kept in review history and out of ordinary overlays; not silently reintroduced as approved. |
| **Saved draft** | User deliberately saved provisional text/note | A draft is not an approved connection or conclusion. |

**State-machine direction:** Candidate review moves from Pending to Approved / Parked / Rejected only on an explicit per-item action. A revision/reopening of a decision must be explicit and auditable. A **Saved draft** belongs to note/document lifecycle rather than silently converting the relationship's review state. Map these concepts to the **actual existing database statuses** during the baseline audit; do not assume matching columns or force a schema migration unnecessarily.

### Visual accessibility and trace-colour coexistence

- Use **text + symbol/line style + restrained colour**, not colour alone. A non-colour viewer must still distinguish a direct quote, lexical evidence, observation, interpretation and proposed link.
- The approved dark-green/cream palette uses readable contrast and accessible focus states. Amber may signal interpretation; dotted muted edges may signal proposed relationships; a legend explains the treatment in Mapping and research.
- **Trace colour is a user-selected membership colour**, never a truth/confidence indicator. On screen, show evidence and review labels separately where needed; do not conflate a Trace's bright colour with an approved interpretation.
- Rejected and parked material is hidden by default in simple reading and ordinary approved-link views, yet retrievable in dedicated review history.
- Every result shows actual source verse/edition and, where relevant, source document, lexical entry, competing evidence and review status. Unsupported evidence is explicitly labelled **Not verified** or **Source unavailable**, never invented.
- Avoid arbitrary numeric confidence percentages unless a reliable, calibrated method and its limits have been validated. Prefer plain **Direct text / Lexical support / Interpretive possibility** descriptions.

**Acceptance gates:** All evidence kinds remain distinct from review statuses, including after approval; per-item review persists; graph edges and Companion results agree; Trace colours do not override meaning/status; no invented citations; colour-independent mobile and desktop accessibility.

## Task 9 — Visual layout and mobile interaction [DELEGATED; FINAL REVIEW PENDING]

**Design language:** Preserve the approved Living Bible Study inspiration — **forest-green reading surface, warm cream Scripture, restrained muted gold/green accents**, elegant serif text for the Bible, legible neutral type for controls, gentle separators and clear whitespace. Borrow styling and ergonomic intent, not the old application's architecture or storage.

### Layout rules

- Keep a **centred adjustable Scripture column** as the visual anchor on large screens; use chapter separators and strong book/chapter/verse navigation without a permanent AI/tool dashboard.
- **App destinations**, **mode selector** and **Companion tabs** are three different navigation concepts (Section 0). Visually differentiate them by placement and hierarchy. Do not render all three as equally prominent stacked navigation bars.
- Desktop: the Companion is a **resizable right panel** with a useful minimum width for both panes, without blocking Bible text. Section results scroll inside it.
- Phone portrait: a **single comfortable Scripture column** and the approved **draggable bottom-sheet Companion**, with all three tabs visible at the top of that sheet. The initial sheet height should leave some Bible visible; taller positions are available through a clear handle.
- Phone landscape: support the limited height with scrollable sheet contents and accessible closing/drag controls. Do not force landscape or full-screen takeover.
- The **Explore | Trace | Save | Copy** toolbar appears close to selected text only on explicit selection. It must not interfere with the native text-selection handles or scroll gestures.
- The **Trace navigator** stays reachable in the reader. If the mobile Companion opens over its usual location, dock the Trace navigator in a non-overlapping location, or temporarily minimize it with a visible way to reveal it when the sheet is dismissed; do not cover critical Scripture or system navigation.
- Expanded research sections stack vertically in narrow panels; allowing multiple sections to remain open does **not** mean forcing multiple desktop-like columns on phones.
- Full Study writing and large Mapping are **focused workspaces**, not more floating sidebars. Returning to Bible restores the origin anchor.
- Keep touch targets comfortable, show keyboard focus, provide screen-reader labels and status announcements, and respect reduced motion and larger font settings. Do not make critical functionality hover-only.
- Long-book rendering and graph layout must remain responsive. If the implementation uses windowing/virtualisation, it must preserve anchor-based selections, verse IDs and return-to-position restoration.

### Practical viewport/gesture test set — proposed minimum

- **Narrow phone portrait** around 360 CSS px: select a multi-word phrase, open the four-action toolbar, raise/lower sheet and switch tabs without losing Scripture.
- **Common phone portrait** around 390–430 CSS px: follow a Trace while Companion is open/closed; confirm neither overlay hides the active verse.
- **Phone landscape:** adequate text, scrolling and sheet handle despite limited height; no forced rotation.
- **Tablet/intermediate widths** around 768 CSS px: no unusable two-column squeeze; if necessary adapt Companion to an overlay while preserving Task 2's panel/sheet intention.
- **Desktop** around 1280 CSS px and wider: draggable divider, comfortable minimum Bible reading width, accessible keyboard/touch controls, readable Study dossier and large Mapping canvas.
- **Large text / zoom / reduced motion:** no clipped control, invalid highlight anchor or lost return position.

**Acceptance gates:** Bible is visually dominant; no competing fixed toolbars; approved three-layer navigation remains comprehensible; desktop right panel and phone bottom sheet work; Trace bar and selection toolbar do not collide; consistent readable typography and evidence labels; good keyboard/touch behaviour; reliable scrolling and recovery after resizing.

## Task 10 — Feasibility, implementation gates and release [DELEGATED; FINAL REVIEW PENDING]

**These are future gates, not executed tests.** The document describes expected behaviour; it does not prove the repository currently has every required API, index, persistence field or device integration.

### Stage 0 — Read-only repository and data audit (before authorising build)

1. Identify the exact local repo, current branch/version, working app structure, build commands and existing tests.
2. Inspect the **actual** Bible/translation, Scripture token/anchor, Strong's/lemma, graph, Trace, Study, conversation, investigation, evidence and review schemas. Document what already exists and what is missing.
3. Identify current screen/components and every legacy research capability that must remain reachable. Map them to the three Companion tabs and top-level destinations; verify no capability disappears.
4. Record baseline counts/IDs and a small controlled sample of actual saved user records for before/after comparisons. Take a **verified, restorable backup** of the local database/configuration before any future migration.
5. Check the app's actual local-model interfaces/context limits and whether offline AI, original-language lookup, full-text search and translation mapping exist. Mark absent features as **work required**, not “already supported”.
6. Confirm target devices, browser/runtime and responsive constraints. A screenshot alone is not an interaction test.

### Internal build stages — individually tested, one final user-facing release

| Internal stage | Scope | Must pass before next stage |
|---|---|---|
| **G1 — State and anchors** | Stable Scripture selections, edition-safe range IDs, reader snapshot/restore, navigation-state ownership | Exact-occurrence and multi-verse selection tests, translation fallback, resize/restart return tests. |
| **G2 — Bible shell and Companion** | Reading home, mode selector, continuous chapters, desktop panel/mobile sheet, tabs, history, selection toolbar | No automatic pin/mode change; closed-by-default Companion; 50-item history; layout/mobile accessibility. |
| **G3 — Trace** | Custom sequence navigator, selected-member start, passage list, exact temporary highlights, edit vs read, return snapshot | Boundaries, no looping, free scroll unchanged step, Trace switching and original return point. |
| **G4 — Research and memory** | Contextual tools, independent expandable sections, local layout restoration, retrieval, conversations, lenses, candidates and review | No automatic re-run/approval; per-investigation persistence; accurate source attribution, bounded prompts, offline/error handling. |
| **G5 — Studies and Mapping** | Full Study dossier/editor and graph focus/preview/Follow/Back | Safe Study saves/links, distinct interpretation statuses; anchored return from both workspaces. |
| **G6 — Visual and accessibility** | Responsive styling, fonts, mobile gestures, overlay collision rules, evidence legend | Narrow-phone/landscape/tablet/desktop and keyboard/zoom/accessibility checks pass. |
| **G7 — Final stabilization** | Full regression, data integrity, backup restore, performance, packaged release candidate | All acceptance criteria and rollback gates pass; no unexplained data loss; user explicitly authorises release. |

**One release, not one giant untested build.** These are private internal stages with automated and interactive gates, not ten installers, disconnected branches or repeated public versions. Stage boundaries are suggestions for Codex once implementation is authorised.

### Required automated and manual regression coverage

| Area | Positive case | Important failure case |
|---|---|---|
| Reader | Restore passage and viewport offset; scroll across chapters | Font/viewport/translation change cannot use stale pixel offsets. |
| Selection | Exact phrase and cross-verse range, correct Copy reference | Same wording elsewhere must not be mistaken for the saved anchor. |
| Companion | Pinned Tree of Life stays while reader visits Genesis; 50 recent entries | Tab switch, Trace picker or clear-history must not delete/replace the pin or saved research. |
| Modes / Mapping | Reading default, independent filters, preview → Follow → Back, zoom/pan | Preview does not recenter map; leaving Mapping restores reader location. |
| Trace | User order, selected-member start, free scrolling, switch and Close | No loop at boundaries, no accidental member change on manual scroll, no lost original return point. |
| Research | Two expanded sections persist for the right subject/tab across restart | Old result does not auto-rerun or become approved on restore; absent cache shows honest placeholder. |
| AI / RAG | Subject-specific follow-up uses cited passages and bounded context | Missing original-language/verse reference, model outage, stale cache or unsupported citation produces visible uncertainty, not fabricated success. |
| Review | Approve one candidate and Reject another individually | No bulk approval, no candidate converted into a false textual fact. |
| Studies | Save an observation, attach an exact anchor, reopen later | Removing a link cannot delete shared Scripture, Trace, source or conversation data. |
| Evidence | Evidence kind and review status both visible | Rejected/Parked never mistakenly treated as evidence kinds or approved links. |
| Mobile | Toolbar, bottom sheet and Trace navigator work in portrait/landscape | Controls do not overlap, obstruct Scripture or hijack text selection. |
| Upgrade | Existing corpus and user records remain readable post-update | Schema changes cannot orphan IDs, overwrite interpretations or prevent rollback. |

### End-to-end demonstration required for final acceptance

1. Open Revelation 2 in Reading mode with the Companion closed at the remembered position.
2. Select **tree of life** (Revelation 2:7); press **Explore** and pin that exact anchor without changing Reading mode.
3. Expand **Passage Comparison** and **Original Language** in Connections; inspect correct Scripture and lemma evidence.
4. Ask a follow-up in Studies; verify the ongoing conversation belongs to Tree of Life and remains **provisional**.
5. Explore **Seven Stars**, then reopen Tree of Life from Recent Investigations; verify its tab layouts still match after an app restart.
6. Start a saved Tree of Life Trace; follow deliberately ordered members, free-scroll away, switch to another Trace if desired and Close. Verify the precise original Scripture anchor/viewport restoration.
7. Attach the selected anchor to a Study, write an observation, save and reopen; confirm Study/approval boundaries.
8. Enter Mapping, preview a node, Follow and Back, then return to exactly the originating Scripture context.
9. Inspect two potential connections, approve one and reject another; verify evidence type is preserved and both decisions survive restart.
10. Repeat the core journey on desktop and real phone; compare persistent records against the baseline and verify a tested rollback path.

### Final release conditions

- All appropriate existing tests **and** newly required unit, integration, browser and real-device acceptance tests have actually run and passed; record actual results and exceptions.
- The original local Scripture, Strong's, studies, anchors, graph, conversations, Trace members and review decisions remain intact; any migration is reversible and verified on a test copy first.
- A restore test proves backup recovery; offline AI/model failures do not corrupt saved research or block ordinary Scripture reading.
- Major new UI components are accessible by keyboard and touch, responsive on phone and desktop, and preserve pinned and reader state under transitions.
- If any gate fails, **do not release**. Fix and retest internally before building one user-facing installer/release.
- **Separate authorisation required** to start implementation, to migrate real data and to publish/install a release. User review of this document alone is not such authorisation.

