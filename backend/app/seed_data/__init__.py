"""Seed data for concepts, case prompts, and rubrics.

Module B (Storage & persistence) has 12 prepared
scenario/reference-answer pairs (3 baseline, 4 guided practice, 4 transfer,
1 confirmation), including 7 preset diagrams and 2 cloze exercises.
All mapped to stable skill identifiers: memory_lifetime, persistence_timing, recovery_path.

Source: AI-authored. Review status: unreviewed (awaiting human verification).
"""

CONCEPTS = [
    {
        "module": "B",
        "slug": "storage-persistence",
        "title": "Storage & persistence",
        "description": "Temporary versus persistent storage. Understanding what survives a process restart and why.",
        "enabled": True,
        "sort_order": 1,
    },
    {
        "module": "A",
        "slug": "request-anatomy",
        "title": "Request anatomy",
        "description": "How requests travel: methods, endpoints, headers, body, and contextual failure diagnosis.",
        "enabled": False,
        "sort_order": 2,
    },
    {
        "module": "A",
        "slug": "backend-validation",
        "title": "Backend validation",
        "description": "Why the server must validate data independently of the client.",
        "enabled": False,
        "sort_order": 3,
    },
    {
        "module": "A",
        "slug": "secret-placement",
        "title": "Secret placement",
        "description": "Where secrets live and why they must never reach the client.",
        "enabled": False,
        "sort_order": 4,
    },
    {
        "module": "B",
        "slug": "save-retrieve-display",
        "title": "Save, retrieve, display",
        "description": "The pipeline from user action to persistent storage and back to the screen.",
        "enabled": False,
        "sort_order": 5,
    },
    {
        "module": "C",
        "slug": "entities-attributes",
        "title": "Entities & attributes",
        "description": "Identifying entities, their attributes, and stable identifiers in a data model.",
        "enabled": False,
        "sort_order": 6,
    },
    {
        "module": "C",
        "slug": "one-to-many",
        "title": "One-to-many relationships",
        "description": "Foreign keys and how one entity owns many related records.",
        "enabled": False,
        "sort_order": 7,
    },
]

from app.seed_data.module_banks import qpart

STORAGE_PERSISTENCE_CASES = [
    # ── 1. Diagnostic Baseline Case #1 (Diagram Repair) ─────────────────────────
    {
        "stage": "diagnostic",
        "case_type": "baseline",
        "sort_order": 1,
        "response_format": "diagram_repair",
        "scenario_text": (
            "A quick-notes backend receives a new note via POST. The handler appends the note "
            "object to a Python global list in the running process. No database or disk file write "
            "is invoked. An operator restarts the server process to apply an OS update.\n\n"
            "Explicit assumptions:\n"
            "- The OS update succeeded and the server restarted cleanly.\n"
            "- No disk or database write ever occurred.\n"
            "- The process starts with empty memory.\n\n"
            "Task: Can the previously added note be retrieved after the restart? Explain your reasoning "
            "and repair the diagram so that the save path writes to persistent storage."
        ),
        "assumptions": [
            "Server restarted cleanly after OS update",
            "No disk or database write was performed",
            "Server starts with an empty in-memory list",
        ],
        "diagram_preset": {
            "diagram_id": "memory-vs-disk-repair",
            "title": "Process Memory vs Persistent Disk",
            "task_instruction": "The current diagram routes the note only to volatile process memory. Select the correct destination to persist notes across restarts.",
            "nodes": [
                {"id": "client", "label": "Web Client", "x": 60, "y": 70, "type": "actor"},
                {"id": "server", "label": "FastAPI Server", "x": 220, "y": 70, "type": "process"},
                {"id": "ram", "label": "Process Memory (RAM)", "x": 390, "y": 30, "type": "volatile"},
                {"id": "disk", "label": "Database on Disk", "x": 390, "y": 110, "type": "persistent"},
            ],
            "edges": [
                {"id": "e1", "from": "client", "to": "server", "label": "POST /notes", "status": "correct"},
                {"id": "e2", "from": "server", "to": "ram", "label": "append to notes[]", "status": "needs_repair"},
            ],
            "repair_options": [
                {"id": "opt_ram", "label": "Process Memory (RAM) only", "target_node": "ram"},
                {"id": "opt_disk", "label": "Database on Disk (Persistent)", "target_node": "disk"},
            ],
            "correct_repair": "opt_disk",
            "interaction_type": "repair",
        },
        "question_parts": [
            qpart("retrieval_reasoning", "Explain whether the note can be retrieved after restart and why process memory is cleared", ["memory_lifetime", "recovery_path"],
                  assessment_guidance="Recognises that data in process memory/RAM is volatile and wiped when the process terminates; restarted process starts with empty memory.",
                  acceptable_alternatives=["Note cannot be retrieved; RAM is cleared on process restart."]),
            qpart("diagram_repair_persistent_path", "Repair the diagram to route the save path to persistent storage", ["memory_lifetime"],
                  assessment_guidance="Select Database on Disk (Persistent) as the save target.",
                  acceptable_alternatives=["opt_disk"]),
        ],
        "source": "ai-authored",
        "review_status": "unreviewed",
        "rubric": {
            "reference_answer": (
                "No, the note cannot be retrieved after restart. Data stored only in a process "
                "variable exists in volatile RAM, which is completely released when the operating system "
                "terminates the process. To survive a restart, the server must write the note to "
                "persistent storage (such as a database or file on disk) before returning."
            ),
            "criteria": [
                {
                    "criterion": "Identifies memory as volatile",
                    "skill_id": "memory_lifetime",
                    "description": "Recognises that process memory / RAM is cleared when the process stops",
                    "weight": 1.0,
                },
                {
                    "criterion": "Explains need for persistent storage",
                    "skill_id": "memory_lifetime",
                    "description": "Explains that data must be written to disk/database to survive restarts",
                    "weight": 1.0,
                },
                {
                    "criterion": "Recognises empty restart state",
                    "skill_id": "recovery_path",
                    "description": "Notes that the restarted process initializes with an empty list",
                    "weight": 0.5,
                },
            ],
        },
    },

    # ── 2. Diagnostic Baseline Case #2 (Diagram Trace) ──────────────────────────
    {
        "stage": "diagnostic",
        "case_type": "baseline",
        "sort_order": 2,
        "response_format": "diagram_trace",
        "scenario_text": (
            "A to-do app writes each item to a JSON file on disk immediately inside the POST handler "
            "before returning a 201 response. Ten minutes later, the server process crashes due to "
            "an unexpected exception. When the server process restarts, are the to-do items still there?\n\n"
            "Explicit assumptions:\n"
            "- The disk write was fully flushed to disk before the crash.\n"
            "- The disk hardware is intact and uncorrupted.\n"
            "- On startup, the application runs a routine that reads the JSON file.\n\n"
            "Task: Explain what happened to the data and trace the path taken during startup recovery."
        ),
        "assumptions": [
            "Write was flushed to disk before crash",
            "Disk hardware is undamaged",
            "Application reloads JSON file on startup",
        ],
        "diagram_preset": {
            "diagram_id": "file-save-trace",
            "title": "Immediate Disk Write & Startup Reload",
            "task_instruction": "Trace the lifecycle: verify that saving happened before crash, and select which step reloads data on restart.",
            "nodes": [
                {"id": "client", "label": "Client Request", "x": 60, "y": 70, "type": "actor"},
                {"id": "handler", "label": "POST Handler", "x": 200, "y": 70, "type": "process"},
                {"id": "disk_file", "label": "todos.json on Disk", "x": 370, "y": 70, "type": "persistent"},
                {"id": "startup", "label": "Startup Loader", "x": 200, "y": 140, "type": "process"},
            ],
            "edges": [
                {"id": "t1", "from": "client", "to": "handler", "label": "1. Add item", "status": "correct"},
                {"id": "t2", "from": "handler", "to": "disk_file", "label": "2. Flush to disk", "status": "correct"},
                {"id": "t3", "from": "disk_file", "to": "startup", "label": "3. Read file on startup", "status": "active"},
            ],
            "blanks": [
                {
                    "id": "b1",
                    "prompt": "Why are items preserved through the crash?",
                    "options": [
                        "Saved to persistent disk before crash",
                        "Cached in CPU L2 cache",
                        "Recovered from Python garbage collector",
                    ],
                    "correct": "Saved to persistent disk before crash",
                }
            ],
            "interaction_type": "trace",
        },
        "question_parts": [
            qpart("explain_data_preservation", "Explain why the items survive the crash and are preserved on disk", ["memory_lifetime", "persistence_timing"],
                  assessment_guidance="Items were flushed to a file on disk before the crash occurred, existing in non-volatile storage that survives crash.",
                  acceptable_alternatives=["Flushed to disk before crash; disk survives process crash."]),
            qpart("trace_startup_recovery", "Trace the path taken during startup recovery in the diagram", ["recovery_path"],
                  assessment_guidance="Application startup loader reads the JSON file on disk to recover items into memory.",
                  acceptable_alternatives=["Startup loader reads JSON file from disk."]),
        ],
        "source": "ai-authored",
        "review_status": "unreviewed",
        "rubric": {
            "reference_answer": (
                "Yes, the to-do items are still there. Because the items were flushed to a file on disk "
                "before the crash occurred, they exist in non-volatile persistent storage that survives "
                "process death. On startup, the server can read todos.json and recover all items."
            ),
            "criteria": [
                {
                    "criterion": "Identifies file as persistent",
                    "skill_id": "memory_lifetime",
                    "description": "Recognises that files on disk survive process crash and restart",
                    "weight": 1.0,
                },
                {
                    "criterion": "Explains save timing",
                    "skill_id": "persistence_timing",
                    "description": "Notes that saving completed before the crash occurred",
                    "weight": 1.0,
                },
                {
                    "criterion": "Identifies startup recovery",
                    "skill_id": "recovery_path",
                    "description": "Explains that the app reloads persisted items from disk into memory on startup",
                    "weight": 0.5,
                },
            ],
        },
    },

    # ── 3. Diagnostic Baseline Case #3 (Written) ────────────────────────────────
    {
        "stage": "diagnostic",
        "case_type": "baseline",
        "sort_order": 3,
        "response_format": "written",
        "scenario_text": (
            "A support chat server keeps the last 50 chat messages in a global variable for instant "
            "rendering, and also commits every message to a PostgreSQL database on disk. The server "
            "crashes unexpectedly.\n\n"
            "Explicit assumptions:\n"
            "- All 50 messages successfully committed to PostgreSQL before the crash.\n"
            "- The PostgreSQL database runs on durable disk and did not crash.\n"
            "- Upon startup, the chat server boots with an empty global variable.\n\n"
            "Task: Which messages can be recovered, from where, and what must the server do on startup?"
        ),
        "assumptions": [
            "All 50 messages committed to PostgreSQL before crash",
            "PostgreSQL database survived intact",
            "Server boots with empty global variable",
        ],
        "question_parts": [
            qpart("recovered_messages_source", "Explain which messages can be recovered and from where", ["memory_lifetime"],
                  assessment_guidance="Global variable in RAM is wiped on crash; all 50 messages committed to PostgreSQL database are preserved on durable disk.",
                  acceptable_alternatives=["Messages in PostgreSQL survive on disk; RAM variable is wiped."]),
            qpart("startup_recovery_action", "Explain what the server must do on startup to repopulate state", ["recovery_path"],
                  assessment_guidance="Startup routine must query PostgreSQL (SELECT messages) to rebuild the fast-access in-memory cache/variable.",
                  acceptable_alternatives=["Query database on startup to repopulate global variable."]),
        ],
        "source": "ai-authored",
        "review_status": "unreviewed",
        "rubric": {
            "reference_answer": (
                "The messages in the global variable in process memory are wiped when the process crashes. "
                "However, all 50 messages committed to the PostgreSQL database are preserved on disk. "
                "To restore the fast-access in-memory list, the server startup routine must execute a "
                "database query (e.g. SELECT * FROM messages ORDER BY created_at DESC LIMIT 50) and "
                "repopulate the global variable."
            ),
            "criteria": [
                {
                    "criterion": "Variable data is lost",
                    "skill_id": "memory_lifetime",
                    "description": "Recognises the in-memory variable is cleared on crash",
                    "weight": 1.0,
                },
                {
                    "criterion": "Database data survives",
                    "skill_id": "memory_lifetime",
                    "description": "Explains that database-written messages persist on disk",
                    "weight": 1.0,
                },
                {
                    "criterion": "Recovery path",
                    "skill_id": "recovery_path",
                    "description": "Describes querying the database on startup to rebuild the in-memory cache",
                    "weight": 1.0,
                },
            ],
        },
    },

    # ── 4. Guided Practice Case #1 (Cloze with Justification) ───────────────────
    {
        "stage": "investigate",
        "case_type": "guided_practice",
        "sort_order": 4,
        "response_format": "cloze",
        "scenario_text": (
            "An e-commerce prototype stores shopping cart contents in an in-memory dictionary "
            "`active_carts = {}` inside the backend application. Whenever the staging server "
            "automatically redeploys new code, customers report their shopping carts are emptied.\n\n"
            "Task: Complete the cloze sentence below and provide your written justification explaining "
            "why shopping carts vanish during deployment and what storage would fix it."
        ),
        "assumptions": [
            "Redeployment restarts the application process",
            "Carts exist only in active_carts dictionary",
            "No session database or Redis store is currently used",
        ],
        "cloze_preset": {
            "cloze_id": "cart-session-cloze",
            "sentence_template": "When carts live only in {blank1}, redeploying the server {blank2} because process memory is {blank3}.",
            "blanks": [
                {"id": "blank1", "options": ["process memory", "the SQL database", "an append-only disk log"], "correct": "process memory"},
                {"id": "blank2", "options": ["wipes all active carts", "backs up all active carts", "pauses checkout"], "correct": "wipes all active carts"},
                {"id": "blank3", "options": ["volatile", "persistent", "replicated"], "correct": "volatile"},
            ],
            "justification_prompt": "Explain in your own words why the cart behaves this way and where carts should be stored instead.",
        },
        "question_parts": [
            qpart("cloze_cart_lifecycle", "Complete the cloze sentence on cart memory lifetime and process redeployment", ["memory_lifetime"],
                  assessment_guidance="When carts live only in process memory, redeploying wipes active carts because process memory is volatile.",
                  acceptable_alternatives=["process memory, wipes all active carts, volatile."]),
            qpart("cart_vanish_justification", "Explain why shopping carts vanish during deployment and what durable storage would fix it", ["memory_lifetime", "persistence_timing"],
                  assessment_guidance="Terminating process frees volatile RAM; new process boots empty; carts must be written to durable storage (database or Redis with configured persistence) before responding.",
                  acceptable_alternatives=["RAM is wiped on process restart; commit to persistent database or configured durable cache."]),
        ],
        "source": "ai-authored",
        "review_status": "unreviewed",
        "rubric": {
            "reference_answer": (
                "Shopping carts vanish because active_carts is an in-memory dictionary. When the server "
                "redeploys, the old process terminates, clearing RAM. Because no state was saved to "
                "persistent storage (like Redis or a SQL database), the new process starts with an "
                "empty dictionary. Carts should be written to durable storage keyed by user/session ID."
            ),
            "criteria": [
                {
                    "criterion": "Process termination clears memory",
                    "skill_id": "memory_lifetime",
                    "description": "Explains that redeployment ends the process and frees volatile RAM",
                    "weight": 1.0,
                },
                {
                    "criterion": "Recommends persistent session storage",
                    "skill_id": "persistence_timing",
                    "description": "Suggests storing cart data in a database or Redis before responding",
                    "weight": 1.0,
                },
            ],
        },
    },

    # ── 5. Guided Practice Case #2 (Diagram Completion) ─────────────────────────
    {
        "stage": "investigate",
        "case_type": "guided_practice",
        "sort_order": 5,
        "response_format": "diagram_completion",
        "scenario_text": (
            "A transactional email service places outgoing emails into an in-memory queue array. "
            "If the worker process crashes while 20 emails are waiting in the queue, all 20 emails "
            "are lost forever.\n\n"
            "Task: Complete the architecture diagram by selecting the appropriate durable queue storage "
            "and explain why an in-memory array fails when workers crash."
        ),
        "assumptions": [
            "Worker crashes while emails are queued",
            "In-memory queue is volatile",
            "Durable queue commits jobs to disk/DB",
        ],
        "diagram_preset": {
            "diagram_id": "queue-persistence-complete",
            "title": "Email Worker Queue Architecture",
            "task_instruction": "Select the storage type for the job queue so pending emails survive worker crashes.",
            "nodes": [
                {"id": "api", "label": "API Webhook", "x": 60, "y": 70, "type": "actor"},
                {"id": "queue_slot", "label": "[ Queue Storage ? ]", "x": 220, "y": 70, "type": "blank"},
                {"id": "worker", "label": "Email Worker", "x": 390, "y": 70, "type": "process"},
            ],
            "edges": [
                {"id": "qe1", "from": "api", "to": "queue_slot", "label": "enqueue email", "status": "active"},
                {"id": "qe2", "from": "queue_slot", "to": "worker", "label": "pop email", "status": "active"},
            ],
            "blanks": [
                {
                    "id": "queue_choice",
                    "prompt": "What storage mechanism must replace the in-memory array?",
                    "options": [
                        "Durable Queue / Database on Disk",
                        "Global Python List in Worker RAM",
                        "Worker Thread Local Storage",
                    ],
                    "correct": "Durable Queue / Database on Disk",
                }
            ],
            "interaction_type": "completion",
        },
        "question_parts": [
            qpart("complete_queue_storage", "Complete the diagram by selecting the durable queue storage mechanism", ["recovery_path"],
                  assessment_guidance="Select 'Durable Queue / Database on Disk' to replace the in-memory array.",
                  acceptable_alternatives=["Durable Queue / Database on Disk"]),
            qpart("memory_queue_failure", "Explain why an in-memory array fails when workers crash and how durable queue enables recovery", ["memory_lifetime", "recovery_path"],
                  assessment_guidance="Array lives in worker process RAM and is destroyed on crash; durable queue persists jobs to disk so a restarted worker can reload and resume processing.",
                  acceptable_alternatives=["Worker RAM is lost on crash; durable queue allows restarted worker to reload pending jobs."]),
        ],
        "source": "ai-authored",
        "review_status": "unreviewed",
        "rubric": {
            "reference_answer": (
                "An in-memory array lives inside the worker process RAM. When the worker crashes, "
                "the OS reclaims the memory space, destroying all queued jobs. Replacing the array with "
                "a durable queue (e.g. database table or disk-backed message broker) ensures that jobs "
                "are persisted before being acknowledged, allowing a restarted worker to resume processing."
            ),
            "criteria": [
                {
                    "criterion": "Identifies memory queue loss",
                    "skill_id": "memory_lifetime",
                    "description": "Explains why jobs in RAM are lost when the worker process dies",
                    "weight": 1.0,
                },
                {
                    "criterion": "Explains durable queue recovery",
                    "skill_id": "recovery_path",
                    "description": "Describes how a durable queue allows a restarted worker to reload pending jobs",
                    "weight": 1.0,
                },
            ],
        },
    },

    # ── 6. Guided Practice Case #3 (Diagram Repair) ─────────────────────────────
    {
        "stage": "investigate",
        "case_type": "guided_practice",
        "sort_order": 6,
        "response_format": "diagram_repair",
        "scenario_text": (
            "A user profile service writes phone number updates to an in-memory cache immediately, "
            "but delays writing to PostgreSQL to an hourly batch job. 15 minutes after a user changes "
            "their phone number, a power failure reboots the host.\n\n"
            "Task: Explain why the new phone number was lost and repair the diagram to enforce safe "
            "persistence timing."
        ),
        "assumptions": [
            "Cache is in-memory only without snapshotting",
            "PostgreSQL write was scheduled for 45 minutes later",
            "Power outage occurred at minute 15",
        ],
        "diagram_preset": {
            "diagram_id": "cache-write-repair",
            "title": "Profile Update Write Path",
            "task_instruction": "Repair the write path so updates are committed durably before considering the update complete.",
            "nodes": [
                {"id": "user", "label": "User Browser", "x": 60, "y": 70, "type": "actor"},
                {"id": "api", "label": "Profile API", "x": 200, "y": 70, "type": "process"},
                {"id": "cache", "label": "Volatile Cache", "x": 370, "y": 30, "type": "volatile"},
                {"id": "postgres", "label": "PostgreSQL on Disk", "x": 370, "y": 110, "type": "persistent"},
            ],
            "edges": [
                {"id": "pe1", "from": "user", "to": "api", "label": "PUT /profile", "status": "correct"},
                {"id": "pe2", "from": "api", "to": "cache", "label": "write to cache only", "status": "needs_repair"},
            ],
            "repair_options": [
                {"id": "opt_delayed", "label": "Write to Cache now, PostgreSQL later in batch", "target_node": "cache"},
                {"id": "opt_immediate", "label": "Commit to PostgreSQL before responding", "target_node": "postgres"},
            ],
            "correct_repair": "opt_immediate",
            "interaction_type": "repair",
        },
        "question_parts": [
            qpart("explain_phone_loss", "Explain why the new phone number was lost during the power failure", ["persistence_timing", "recovery_path"],
                  assessment_guidance="Update was acknowledged while only in volatile cache; power failure occurred in the window before the batch write to PostgreSQL, so data never reached disk.",
                  acceptable_alternatives=["Data was only in volatile cache and delayed batch had not run before power cut."]),
            qpart("repair_persistence_timing", "Repair the diagram to enforce safe persistence timing before responding", ["persistence_timing"],
                  assessment_guidance="Select 'Commit to PostgreSQL before responding'.",
                  acceptable_alternatives=["opt_immediate"]),
        ],
        "source": "ai-authored",
        "review_status": "unreviewed",
        "rubric": {
            "reference_answer": (
                "The update was lost because of flawed persistence timing: the server acknowledged the "
                "update when it was only in volatile memory. Because the crash happened during the "
                "45-minute window before the batch save, the data never touched durable disk. The write "
                "path must commit to PostgreSQL before returning success."
            ),
            "criteria": [
                {
                    "criterion": "Identifies persistence timing vulnerability",
                    "skill_id": "persistence_timing",
                    "description": "Explains that delayed saving leaves a vulnerability window where crashes cause loss",
                    "weight": 1.0,
                },
                {
                    "criterion": "Explains recovery dependency",
                    "skill_id": "recovery_path",
                    "description": "Notes that after restart, the system can only recover data that reached disk",
                    "weight": 1.0,
                },
            ],
        },
    },

    # ── 7. Guided Practice Case #4 (Cloze with Justification) ───────────────────
    {
        "stage": "investigate",
        "case_type": "guided_practice",
        "sort_order": 7,
        "response_format": "cloze",
        "scenario_text": (
            "An analytics ingestion server buffers incoming clickstream events in a memory array "
            "`event_buffer` and flushes them to disk once every 60 seconds. A process crash occurs "
            "at second 45.\n\n"
            "Task: Complete the cloze sentence below and provide your written justification explaining "
            "which events survive, which are lost, and why."
        ),
        "assumptions": [
            "Events 0 to 45 were in event_buffer memory array only",
            "Crash occurred at second 45 before the 60-second flush",
            "Previous 60-second batches were successfully saved to disk",
        ],
        "cloze_preset": {
            "cloze_id": "buffer-flush-cloze",
            "sentence_template": "Events arriving between seconds 0 and 45 were stored in {blank1}; because the crash occurred before the 60s flush, these events were {blank2} due to {blank3}.",
            "blanks": [
                {"id": "blank1", "options": ["volatile memory buffer", "committed disk storage", "browser cookies"], "correct": "volatile memory buffer"},
                {"id": "blank2", "options": ["permanently lost", "automatically recovered", "re-sent by the OS"], "correct": "permanently lost"},
                {"id": "blank3", "options": ["delayed persistence timing", "corrupted disk sectors", "network disconnection"], "correct": "delayed persistence timing"},
            ],
            "justification_prompt": "Explain why timing of the disk flush determines whether incoming events survive.",
        },
        "question_parts": [
            qpart("cloze_buffer_flush", "Complete the cloze sentence for buffer flush timing", ["memory_lifetime", "persistence_timing"],
                  assessment_guidance="Events in volatile memory buffer were permanently lost due to delayed persistence timing.",
                  acceptable_alternatives=["volatile memory buffer, permanently lost, delayed persistence timing."]),
            qpart("event_survival_justification", "Explain which events survive, which are lost, and why flush timing determines survival", ["memory_lifetime", "persistence_timing"],
                  assessment_guidance="Events 0-45 in unwritten RAM buffer are lost on crash; earlier batches already flushed to disk survive because they crossed the persistence boundary.",
                  acceptable_alternatives=["Unflushed events in RAM buffer are lost; previously flushed batches on disk survive."]),
        ],
        "source": "ai-authored",
        "review_status": "unreviewed",
        "rubric": {
            "reference_answer": (
                "Events from seconds 0 to 45 are lost because they resided solely in the server's "
                "in-memory buffer. The flush interval had not arrived, so no disk write occurred. "
                "When the process crashed, volatile RAM was freed. Events from earlier batches that were "
                "already flushed to disk survive unharmed because they crossed the persistence boundary."
            ),
            "criteria": [
                {
                    "criterion": "Buffer volatility causes loss",
                    "skill_id": "memory_lifetime",
                    "description": "Recognises that unwritten buffered data in RAM is destroyed on crash",
                    "weight": 1.0,
                },
                {
                    "criterion": "Persistence timing boundary",
                    "skill_id": "persistence_timing",
                    "description": "Explains that only events flushed before the crash timestamp survive",
                    "weight": 1.0,
                },
            ],
        },
    },

    # ── 8. Held-Back Transfer Case #1 (Written) ─────────────────────────────────
    {
        "stage": "apply",
        "case_type": "transfer",
        "sort_order": 8,
        "response_format": "written",
        "scenario_text": (
            "A multiplayer game server keeps each player's real-time score in a dictionary during the "
            "match. Scores are written to a database only when the match ends. During minute 12 of a "
            "20-minute match, the server crashes.\n\n"
            "Explicit assumptions:\n"
            "- The match was not marked finished.\n"
            "- No intermediate database save occurred.\n"
            "- The database itself is operational.\n\n"
            "Task: What happens to the scores from minutes 0 to 12? Explain why, referencing memory "
            "lifetime and persistence timing."
        ),
        "assumptions": [
            "Match was in progress at minute 12",
            "Scores were kept only in server dictionary",
            "No database write was performed mid-match",
        ],
        "question_parts": [
            qpart("score_fate_and_memory_lifetime", "Explain what happens to the scores from minutes 0 to 12 and why process memory causes loss", ["memory_lifetime"],
                  assessment_guidance="Scores from minutes 0 to 12 are permanently lost because they existed only in the game server's volatile RAM dictionary, which is wiped on crash.",
                  acceptable_alternatives=["Scores are lost because they only existed in volatile RAM."]),
            qpart("persistence_timing_analysis", "Explain why the persistence timing policy left scores unsaved when the crash occurred", ["persistence_timing"],
                  assessment_guidance="Scores were configured to be saved only when the match ends; because crash happened mid-match at minute 12, the database save was never executed.",
                  acceptable_alternatives=["Database write only happens at match end, so mid-match crash occurred before any commit."]),
        ],
        "source": "ai-authored",
        "review_status": "unreviewed",
        "rubric": {
            "reference_answer": (
                "The scores from minutes 0 to 12 are permanently lost. They existed only in the "
                "game server's process memory (the dictionary), which is volatile. Because the crash "
                "happened before the match finished, the database write was never executed. Data must "
                "be committed to persistent storage before a crash occurs to survive."
            ),
            "criteria": [
                {
                    "criterion": "Identifies when persistence happens",
                    "skill_id": "persistence_timing",
                    "description": "Notes that scores are only saved at match end, not during the match",
                    "weight": 1.0,
                },
                {
                    "criterion": "Applies volatility principle",
                    "skill_id": "memory_lifetime",
                    "description": "Explains that in-memory dictionary data is wiped on process crash",
                    "weight": 1.0,
                },
                {
                    "criterion": "Timing matters",
                    "skill_id": "persistence_timing",
                    "description": "Recognises that crash occurring before the commit point causes data loss",
                    "weight": 0.5,
                },
            ],
        },
    },

    # ── 9. Held-Back Transfer Case #2 (Diagram Trace) ───────────────────────────
    {
        "stage": "apply",
        "case_type": "transfer",
        "sort_order": 9,
        "response_format": "diagram_trace",
        "scenario_text": (
            "An e-commerce site caches product prices in memory for speed. An admin updates the "
            "database price of an item from $1000 to $900, but the cache invalidation code fails. "
            "Customers continue seeing the stale $1000 price. That night, the server restarts.\n\n"
            "Explicit assumptions:\n"
            "- The database holds the updated $900 price on disk.\n"
            "- The server restarted cleanly and memory was wiped.\n"
            "- On restart, the application rebuilds cache on-demand from the database.\n\n"
            "Task: After restart, does the customer see $1000 or $900? Explain why and trace the recovery path."
        ),
        "assumptions": [
            "Database holds $900 on disk",
            "Server restart wiped in-memory cache",
            "Application queries database on-demand after restart",
        ],
        "diagram_preset": {
            "diagram_id": "pricing-cache-trace",
            "title": "Price Cache Lifecycle Across Restart",
            "task_instruction": "Trace the read flow after restart: does the server read the stale destroyed cache or query the authoritative database?",
            "nodes": [
                {"id": "customer", "label": "Customer", "x": 60, "y": 70, "type": "actor"},
                {"id": "server", "label": "E-Commerce Server", "x": 220, "y": 70, "type": "process"},
                {"id": "old_cache", "label": "Stale Cache ($1000) [Wiped on Restart]", "x": 390, "y": 30, "type": "volatile"},
                {"id": "db", "label": "Database on Disk ($900)", "x": 390, "y": 110, "type": "persistent"},
            ],
            "edges": [
                {"id": "t_req", "from": "customer", "to": "server", "label": "GET /product", "status": "correct"},
                {"id": "t_db", "from": "server", "to": "db", "label": "Query authoritative price", "status": "active"},
            ],
            "blanks": [
                {
                    "id": "price_outcome",
                    "prompt": "What price is displayed after restart?",
                    "options": ["$900 from Database", "$1000 from Stale Cache", "Error 500"],
                    "correct": "$900 from Database",
                }
            ],
            "interaction_type": "trace",
        },
        "question_parts": [
            qpart("price_seen_and_authoritative_source", "Explain whether the customer sees $1000 or $900 after restart and why", ["memory_lifetime"],
                  assessment_guidance="Customer sees $900; stale $1000 cache was destroyed when process stopped, and restarted server queries authoritative PostgreSQL database on disk containing $900.",
                  acceptable_alternatives=["Customer sees $900 because restart wiped the stale cache and server reads $900 from DB."]),
            qpart("trace_recovery_path", "Trace the read flow and cache recovery path in the diagram", ["recovery_path"],
                  assessment_guidance="Server queries authoritative database on disk ($900 from Database) and rebuilds cache.",
                  acceptable_alternatives=["$900 from Database"]),
        ],
        "source": "ai-authored",
        "review_status": "unreviewed",
        "rubric": {
            "reference_answer": (
                "After the restart, customers see the new $900 price. The in-memory cache containing "
                "the stale $1000 price was destroyed when the process stopped. Upon restarting, the "
                "server queries the authoritative PostgreSQL database, which has the updated $900 price, "
                "and populates the fresh cache."
            ),
            "criteria": [
                {
                    "criterion": "Cache is volatile",
                    "skill_id": "memory_lifetime",
                    "description": "Explains that the in-memory cache is destroyed when the process terminates",
                    "weight": 1.0,
                },
                {
                    "criterion": "Database is authoritative",
                    "skill_id": "memory_lifetime",
                    "description": "Notes that the persistent database holds the durable source of truth",
                    "weight": 1.0,
                },
                {
                    "criterion": "Recovery path repopulates cache",
                    "skill_id": "recovery_path",
                    "description": "Explains that startup/query sequence rebuilds cache from persistent storage",
                    "weight": 0.5,
                },
            ],
        },
    },

    # ── 10. Held-Back Transfer Case #3 (Diagram Repair) ─────────────────────────
    {
        "stage": "apply",
        "case_type": "transfer",
        "sort_order": 10,
        "response_format": "diagram_repair",
        "scenario_text": (
            "A collaborative canvas server stores active WebSocket client connections in a local "
            "Python dictionary `connected_users = {}`. An engineer attempts to implement automatic "
            "reconnection by having the server read `connected_users` on restart to reconnect users.\n\n"
            "Task: Explain why this design cannot work upon server restart, and repair the diagram "
            "to show how a restarted process can retrieve saved canvas state. "
            "Explain why restoring saved data is different from restoring a live socket."
        ),
        "assumptions": [
            "Server restarts and process memory is cleared",
            "TCP/WebSocket sockets terminate when server stops",
            "Canvas edits were committed to the database before restart",
            "Clients can initiate a new connection; authentication is outside this case",
        ],
        "diagram_preset": {
            "diagram_id": "websocket-session-repair",
            "title": "Canvas State Recovery Across Restart",
            "task_instruction": "Repair the saved-state recovery path; explain separately what happens to live connections.",
            "nodes": [
                {"id": "client", "label": "Client Browser", "x": 60, "y": 70, "type": "actor"},
                {"id": "server", "label": "WebSocket Server", "x": 220, "y": 70, "type": "process"},
                {"id": "mem_sock", "label": "In-Memory Sockets [Destroyed]", "x": 390, "y": 30, "type": "volatile"},
                {"id": "session_db", "label": "Committed Canvas Edits / DB", "x": 390, "y": 110, "type": "persistent"},
            ],
            "edges": [
                {"id": "we1", "from": "server", "to": "mem_sock", "label": "attempt reload sockets", "status": "needs_repair"},
                {"id": "we2", "from": "client", "to": "server", "label": "new connection", "status": "active"},
            ],
            "repair_options": [
                {"id": "opt_socket_reload", "label": "Read sockets from dead process memory", "target_node": "mem_sock"},
                {"id": "opt_client_reconnect", "label": "Read committed canvas edits from DB", "target_node": "session_db"},
            ],
            "correct_repair": "opt_client_reconnect",
            "interaction_type": "repair",
        },
        "question_parts": [
            qpart("explain_socket_vs_saved_state", "Explain why reading connected_users cannot work and why restoring saved data is different from live sockets", ["memory_lifetime"],
                  assessment_guidance="Dictionary in RAM is gone on restart and open network socket handles are closed by OS; restarted server cannot revive live sockets, clients must reconnect.",
                  acceptable_alternatives=["Sockets and RAM die on restart; restoring saved DB data does not restore live network connections."]),
            qpart("repair_canvas_recovery", "Repair the diagram to retrieve saved canvas state from persistent storage", ["recovery_path"],
                  assessment_guidance="Select 'Read committed canvas edits from DB'.",
                  acceptable_alternatives=["opt_client_reconnect"]),
        ],
        "source": "ai-authored",
        "review_status": "unreviewed",
        "rubric": {
            "reference_answer": (
                "The server cannot read `connected_users` on restart because the dictionary existed in "
                "the old process memory, which is gone. Additionally, open network sockets are closed "
                "when a process stops. The restarted process can query the committed canvas edits "
                "from the database to restore the drawing; this does not restore the old live sockets. "
                "Clients must establish new connections. Authentication is not assessed here."
            ),
            "criteria": [
                {
                    "criterion": "Sockets and memory die with process",
                    "skill_id": "memory_lifetime",
                    "description": "Explains that process memory and open socket handles do not survive restarts",
                    "weight": 1.0,
                },
                {
                    "criterion": "Recovery path retrieves saved canvas data",
                    "skill_id": "recovery_path",
                    "description": "Explains querying committed canvas edits after restart; distinguishes restored data from a live socket",
                    "weight": 1.0,
                },
            ],
        },
    },

    # ── 11. Held-Back Transfer Case #4 (Diagram Completion) ─────────────────────
    {
        "stage": "apply",
        "case_type": "transfer",
        "sort_order": 11,
        "response_format": "diagram_completion",
        "scenario_text": (
            "An IoT sensor gateway buffers temperature readings in a memory buffer and writes a "
            "compressed batch to an on-disk SQLite database once every 5 minutes. At minute 3, "
            "the gateway suffers a power cut.\n\n"
            "Explicit assumptions:\n"
            "- Minutes 1, 2, and 3 were in the memory buffer only.\n"
            "- The minute 0 database commit completed successfully.\n"
            "- Power was cut abruptly without graceful shutdown.\n\n"
            "Task: Which sensor readings survive, which are lost, and complete the diagram by identifying "
            "what write strategy reduces the unsaved window. State the boundary of any guarantee."
        ),
        "assumptions": [
            "Readings from minutes 1, 2, 3 were in RAM only",
            "Minute 0 write completed to disk",
            "Abrupt power loss terminated process",
            "Previously completed durable commits survive and the disk remains intact",
            "A reading counts as durably accepted only after its durable commit completes",
        ],
        "diagram_preset": {
            "diagram_id": "sensor-buffer-complete",
            "title": "Sensor Ingestion Write Boundary",
            "task_instruction": "Choose a strategy that reduces the unsaved window; explain what can still be lost before commit completes.",
            "nodes": [
                {"id": "sensor", "label": "Sensor Unit", "x": 60, "y": 70, "type": "actor"},
                {"id": "gateway", "label": "IoT Gateway", "x": 220, "y": 70, "type": "process"},
                {"id": "strategy_slot", "label": "[ Persistence Strategy ? ]", "x": 390, "y": 70, "type": "blank"},
            ],
            "edges": [
                {"id": "se1", "from": "sensor", "to": "gateway", "label": "readings every 10s", "status": "active"},
                {"id": "se2", "from": "gateway", "to": "strategy_slot", "label": "storage path", "status": "active"},
            ],
            "blanks": [
                {
                    "id": "write_strategy",
                    "prompt": "Which approach reduces the window before a reading is durably accepted?",
                    "options": [
                        "Commit each reading durably before acknowledging it",
                        "Hold 10 minutes in memory before write",
                        "Store in CPU register cache",
                    ],
                    "correct": "Commit each reading durably before acknowledging it",
                }
            ],
            "interaction_type": "completion",
        },
        "question_parts": [
            qpart("readings_survival_analysis", "Explain which sensor readings survive and which are lost during the power cut", ["memory_lifetime"],
                  assessment_guidance="Minute 0 readings in SQLite survive because they were committed to disk; minutes 1, 2, and 3 in volatile RAM buffer are lost when power was cut.",
                  acceptable_alternatives=["Minute 0 committed readings survive on disk; minutes 1-3 in RAM buffer are lost."]),
            qpart("complete_write_strategy", "Complete the diagram by identifying the write strategy that reduces the unsaved window", ["persistence_timing"],
                  assessment_guidance="Select 'Commit each reading durably before acknowledging it'.",
                  acceptable_alternatives=["Commit each reading durably before acknowledging it"]),
            qpart("durability_guarantee_boundary", "State the boundary of any durability guarantee and the throughput trade-off", ["persistence_timing"],
                  assessment_guidance="Acknowledged durable commits survive under intact storage assumption; readings arriving before commit completes may still be lost; policy trades throughput for durability.",
                  acceptable_alternatives=["Durable commit before acknowledgement minimizes unsaved window, but in-flight readings can still be lost; trades throughput for durability."]),
        ],
        "source": "ai-authored",
        "review_status": "unreviewed",
        "rubric": {
            "reference_answer": (
                "The minute 0 readings in SQLite survive because they were committed to disk. Readings "
                "from minutes 1, 2, and 3 were in the volatile RAM buffer and are completely lost when "
                "power was cut. Committing each reading durably before it is acknowledged reduces the "
                "unsaved window. Under the stated intact-storage assumption, acknowledged durable commits "
                "survive. A reading arriving before its commit completes may still be lost; immediate "
                "append alone is not an absolute zero-loss guarantee, and this policy trades throughput for durability."
            ),
            "criteria": [
                {
                    "criterion": "Identifies unwritten buffered data loss",
                    "skill_id": "memory_lifetime",
                    "description": "Explains that readings held in memory during power cut are unrecoverable",
                    "weight": 1.0,
                },
                {
                    "criterion": "Explains persistence timing trade-off",
                    "skill_id": "persistence_timing",
                    "description": "Distinguishes completed durable commits from in-flight readings and explains the write-frequency trade-off without an absolute guarantee",
                    "weight": 1.0,
                },
            ],
        },
    },

    # ── 12. Confirmation Case #1 (Written) ──────────────────────────────────────
    {
        "stage": "apply",
        "case_type": "confirmation",
        "sort_order": 12,
        "response_format": "written",
        "scenario_text": (
            "A high-throughput audit logging gateway writes each event simultaneously to both an "
            "in-memory circular buffer (holding the last 500 lines for immediate dashboard streaming) "
            "and synchronously appends each event to an on-disk audit log file. The server is restarted "
            "by an administrator for maintenance.\n\n"
            "Explicit assumptions:\n"
            "- All disk writes finished before the restart command executed.\n"
            "- The on-disk audit log file is undamaged.\n"
            "- The in-memory circular buffer starts empty on process launch.\n\n"
            "Task: Describe what the dashboard displays immediately upon restart before new events arrive, "
            "what happened to the historical logs, and how the dashboard can display the previous 500 lines."
        ),
        "assumptions": [
            "All events were committed to disk log file before restart",
            "Disk log is uncorrupted",
            "In-memory circular buffer boots empty",
        ],
        "question_parts": [
            qpart("dashboard_display_on_restart", "Describe what the dashboard displays immediately upon restart before new events arrive and why", ["memory_lifetime"],
                  assessment_guidance="Dashboard displays an empty buffer because the circular buffer lived in process RAM, which was cleared on restart.",
                  acceptable_alternatives=["Dashboard shows empty buffer because RAM was wiped on restart."]),
            qpart("historical_logs_status", "Explain what happened to the historical logs", ["memory_lifetime"],
                  assessment_guidance="Historical logs are safely preserved in the on-disk audit log file because disk writes completed before restart.",
                  acceptable_alternatives=["Historical logs survived intact on disk."]),
            qpart("restore_dashboard_history", "Explain how the dashboard can display the previous 500 lines", ["recovery_path"],
                  assessment_guidance="Application startup routine must read the last 500 lines from the disk log file to repopulate the in-memory circular buffer.",
                  acceptable_alternatives=["Read last 500 lines from disk file on startup to reload circular buffer."]),
        ],
        "source": "ai-authored",
        "review_status": "unreviewed",
        "rubric": {
            "reference_answer": (
                "Immediately upon restart, the dashboard displays an empty buffer because the circular "
                "buffer lived in process RAM, which was cleared on restart. However, the complete history "
                "of audit logs is safely preserved in the on-disk file. To display the previous 500 "
                "lines, the application startup routine must read the last 500 lines from the disk log "
                "file to repopulate the in-memory circular buffer."
            ),
            "criteria": [
                {
                    "criterion": "Buffer is volatile",
                    "skill_id": "memory_lifetime",
                    "description": "Explains the in-memory circular buffer is cleared on restart",
                    "weight": 1.0,
                },
                {
                    "criterion": "File persists",
                    "skill_id": "memory_lifetime",
                    "description": "Notes that the log file on disk survives the restart intact",
                    "weight": 1.0,
                },
                {
                    "criterion": "Recovery behaviour",
                    "skill_id": "recovery_path",
                    "description": "Describes reading the file on disk to repopulate the in-memory buffer on startup",
                    "weight": 1.0,
                },
            ],
        },
    },
]

# Prepared bank authoring metadata remains private inside the rubric.
from app.seed_data.module_banks import ADDITIONAL_CASE_BANKS, authored_id

STORAGE_SKILL_NOTES = {
    'memory_lifetime': (
        'Describing loss of the old process variable is enough; no OS implementation detail is required. Files, a database or a durable queue are valid only with stated durability assumptions.',
        'A server variable, ordinary cache or default Redis configuration is automatically permanent.',
        'Which locations contained this data immediately before the stated failure?',
    ),
    'persistence_timing': (
        'A file, log, database or queue is acceptable if the write has durably completed before the relevant failure; acknowledge any still-in-flight window.',
        'Starting an append, returning a response or naming a store persistent proves the last write completed.',
        'Which writes had completed at the failure time, and which had not?',
    ),
    'recovery_path': (
        'Startup loading, on-demand reads, direct database-backed responses or replay of an intact durable log can all be valid recovery paths when explained.',
        'A surviving database automatically repopulates application variables or restores live sockets.',
        'What does the new process read, and what must it do before it can use that state?',
    ),
}

for _case in STORAGE_PERSISTENCE_CASES:
    _case['authored_id'] = authored_id('storage-persistence', f"case-{_case['sort_order']:02d}")
    _diagram = _case.get('diagram_preset')
    if _diagram and _diagram.get('repair_options'):
        _diagram['repair_edge_id'] = next(e['id'] for e in _diagram['edges'] if e.get('status') == 'needs_repair')
    for _criterion in _case['rubric']['criteria']:
        _alternative, _misconception, _probe = STORAGE_SKILL_NOTES[_criterion['skill_id']]
        _criterion['acceptable_alternatives'] = [_alternative]
        _criterion['common_misconceptions'] = [_misconception]
        _criterion['follow_up_probes'] = [_probe]

# Redis requires an explicit durability policy; a default cache is not enough.
STORAGE_PERSISTENCE_CASES[3]['rubric']['reference_answer'] = (
    'Shopping carts disappear because active_carts belongs to the terminated process. '
    'The new process starts empty. Commit cart changes to a database, a disk-backed store, '
    'or a queue/cache explicitly configured for the needed durability before acknowledging them, '
    'and retrieve the saved cart for later requests. Redis without a stated persistence configuration '
    'is not automatically durable. No storage choice recovers changes that were never saved.'
)
STORAGE_PERSISTENCE_CASES[3]['rubric']['criteria'][1]['description'] = (
    'Suggests a completed durable cart write before acknowledgement; a Redis proposal must specify durability rather than assume it'
)

CASE_BANKS = {'storage-persistence': STORAGE_PERSISTENCE_CASES, **ADDITIONAL_CASE_BANKS}
for _concept in CONCEPTS:
    # Enabled means a complete prepared development bank exists, not human review.
    _concept['enabled'] = _concept['slug'] in CASE_BANKS
