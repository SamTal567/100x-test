"""Small versioned, allowlisted authored lessons; no learner data or private keys."""

from html import escape

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse


RESOURCE_VERSION = "2026-10-18.1"
router = APIRouter(prefix="/v1/resources", tags=["resources"])

LESSONS = {
    "storage-persistence": {
        "title": "What survives a restart?",
        "paragraphs": [
            "A variable belongs to one running process. When that process ends, a replacement process does not inherit its lists or dictionaries. A successfully committed database row or completed durable file write can survive under an intact-storage assumption.",
            "Draw a timeline: received → memory update → durable commit → acknowledgement. A failure before commit can lose the unsaved update. Starting a write is not the same as completing a durable write. A label such as cache or Redis does not establish a durability policy.",
            "Surviving data is not automatically visible. The restarted application must query the database, read the file, or replay the durable log. It may rebuild a cache at startup or fetch records on demand. Live sockets and other process handles cannot be reconstructed merely by saving a dictionary.",
            "A prototype JSON file can teach persistence, but simultaneous writers, partial writes and growing history need explicit handling. Do not promise zero loss for a reading that has not completed its durable save. Database backups and damaged-disk recovery are beyond this process-restart exercise.",
        ],
        "diagram": "request -> process memory -> durable commit -> acknowledge\n                         |\n                     failure?\n                         v\nnew process -> query/read surviving storage -> display/rebuild cache",
        "practice": "A checklist entry is in memory at 10:01, commits at 10:02, and the process fails at 10:03. Explain what can be recovered and the read step needed. Now move the failure to 10:01:30. Which conclusion changes, and which assumption is essential?",
        "reflection": "An analogy: a desk note and a filed record. It stops working if you assume every file write is instantly complete or that a new worker automatically reads the filing cabinet.",
    },
    "request-anatomy": {
        "title": "Read the request contract before changing the code",
        "paragraphs": [
            "A request has a method and URL, headers that carry request metadata, and sometimes a body. The endpoint's contract tells you which method/path to use, where each input belongs and what field names/types are accepted. A JSON body is not a substitute for a required query parameter or header.",
            "Compare the actual request to that contract one part at a time. GET /items/9 and POST /items are different operations even if they mention the same item. Header names are case-insensitive, but JSON field names follow the endpoint's schema.",
            "Use observations narrowly. A returned validation error proves the request reached a validator; it does not prove a later provider call ran. No response from localhost in a classmate's browser may mean no server exists on that classmate's machine. localhost names the calling machine, not the developer's laptop.",
            "For uploads, a filename string, a file URL and multipart file bytes are different inputs. Use what the given endpoint supports. Do not guess authentication, database failures or status meanings beyond the facts and explicit contract in the scenario.",
        ],
        "diagram": "Browser\n  method + URL + headers + optional body\n          |\n          v\nreachable server -> route -> validate contract -> handler -> response",
        "practice": "A contract accepts POST /drafts with JSON {title: string}. A reachable server receives GET /drafts with a title header. Identify two mismatches, propose the request, and state one thing you still cannot infer about storage.",
        "reflection": "An analogy: an addressed form with labelled sections. It stops working if you assume every office reads every value from any section, or that delivering the envelope proves the work inside succeeded.",
    },
    "backend-validation": {
        "title": "Validate where every caller crosses the boundary",
        "paragraphs": [
            "Browser checks help a person correct input early. A script, another client or edited network request can bypass them. The backend must enforce the actual data contract for every caller before accepted input produces permanent effects.",
            "Valid JSON proves syntax, not meaning. Check required fields, permitted types and stated domain rules such as an allowed status or positive count. Avoid inventing extra constraints. Reject or normalise only as the documented contract permits.",
            "Sequence matters: parse, validate, then write accepted data. If validation is performed in a transaction, invalid input must roll back fully before commit. Returning an error after a committed insert does not erase the row.",
            "A useful error identifies the invalid field/rule without pretending the save succeeded. The same rules apply across browser, mobile and integration callers. File pickers and filename extensions are also client inputs; enforce stated size/format rules on the backend.",
        ],
        "diagram": "browser / mobile / script\n             |\n          backend\n       parse -> validate\n                 | pass       | fail\n                 v            v\n          write + success   errors, no side effect",
        "practice": "A service permits count 1 through 8 and a nonempty label. A direct request sends count 0 and label 'Box'. Explain the decision, which values support it and what should be stored. Would a disabled Submit button change your backend answer?",
        "reflection": "An analogy: checking a form at the reception desk. It stops working if one entrance bypasses the desk or if the filing happens before the check.",
    },
    "secret-placement": {
        "title": "Keep provider secrets on the backend",
        "paragraphs": [
            "A long-lived provider key is a server credential. Browser users can inspect shipped JavaScript, storage and outgoing requests. Minification, a hidden field, HTTPS or a frontend environment-variable name does not hide that value from the person running the browser.",
            "The browser sends the user's input to your backend. Backend code reads its private runtime configuration, calls the provider, and returns only the result the client needs. Never return the provider key in configuration, debug objects, errors or the provider Authorization header.",
            "Build configuration and backend runtime configuration may be different environments. Setting a frontend variable does not configure a deployed FastAPI process. Keep examples and documentation to configuration names, never actual values.",
            "If a secret reached a bundle or browser response, assume copies can remain. Revoke/replace it with the provider and update backend configuration. Removing it in the next build does not revoke earlier copies. Intentionally public client tokens are a separate design with a different contract.",
        ],
        "diagram": "Browser -- user input only --> Own backend\n                                  | reads private configuration\n                                  v\n                              Provider API\nBrowser <-- needed result ----- Backend\n\nProvider credential never crosses into the browser.",
        "practice": "A backend makes the provider call correctly, then returns a debug object containing the full outgoing headers. Explain whether the secret stayed private, repair the response and describe the action needed for an already exposed key.",
        "reflection": "An analogy: a staff-only access badge. It stops working if the receptionist photocopies the badge for every visitor; the original storage location does not undo that disclosure.",
    },
    "save-retrieve-display": {
        "title": "Saving, reading and showing are separate steps",
        "paragraphs": [
            "A visible item, optimistic update or Saved toast is screen state. Durable saving requires a successful storage operation. Keep pending/failed states honest and reconcile them with the server's confirmed result.",
            "Saved rows do not update every open screen automatically. A screen needs a query/read, a returned result and rendering, or an explicitly implemented update subscription. A stale screen and a failed save require different repairs.",
            "A history table is not automatic model memory. Retrieve a relevant bounded history, construct the model request and explicitly include what the model needs. The browser can display yesterday's messages while today's model request contains none of them.",
            "A file path identifies stored bytes. It is not the bytes or extracted text, and a model/renderer without storage access cannot read it by magic. Read supported content explicitly, prepare it for the consumer and preserve the source reference. Large history and unsupported file formats require honest limits.",
        ],
        "diagram": "input -> save/commit -> stored row/file\n                            | explicit read\n                            v\n                       response data -> screen render\n                            | separate selection/preparation\n                            v\n                       model request context",
        "practice": "A transcript is safely stored and its filename appears on screen. The model request includes only that filename. Explain which steps worked, which data the model actually received and how the missing content would reach it.",
        "reflection": "An analogy: filing, fetching and presenting a folder. It stops working if you treat a folder label as the whole document or assume every colleague automatically reads every filed record.",
    },
    "entities-attributes": {
        "title": "Model the thing, its identity and its facts",
        "paragraphs": [
            "An entity is a kind of independently identifiable object in the problem. An attribute describes that object. Start with examples: two people can share a name, and one person's name can change. A stable unique ID keeps identity separate from the display label.",
            "Place a fact with the object it describes. A talk's duration belongs to that talk; a speaker can have several talks with different durations. Avoid a new table for every noun, but do not flatten independently changing records into an ambiguous text field.",
            "Current state and historical facts have different meanings. A product's current price can change while an earlier order line retains its actual charged price. Store a snapshot or reference an immutable version so the past value is reproducible.",
            "A file reference on a row points to bytes in storage; it is not the file itself. Give the relevant business record a stable identity and preserve the reference/bytes needed by the product. Foreign-key cardinality, indexes and access policies are separate questions.",
        ],
        "diagram": "Product P3: name, current_price\n              | identifies purchased item\nOrder line L8: charged_price_at_purchase\n              |\n              +--> receipt reference --> stored file bytes",
        "practice": "Two coaches share a display name and each teaches separately identifiable sessions. Session fees may change for future bookings. Identify stable IDs, where duration belongs and how to preserve the fee actually charged on an old booking.",
        "reflection": "An analogy: a numbered record card with editable labels. It stops working if changing a label changes the object's identity or if today's catalogue rewrites yesterday's receipt.",
    },
    "one-to-many": {
        "title": "Store each child's parent link",
        "paragraphs": [
            "Read cardinality from the product rules: one parent can have zero or many children; each child has exactly one parent in these exercises. One-to-many does not require every parent to have several children, and it does not permit one child to belong to several parents.",
            "Give both tables stable IDs and place parent_id on every child row. Many child rows can hold the same parent ID. A single child_id slot on the parent cannot represent an arbitrary collection; matching mutable display names also creates ambiguous links.",
            "To list a parent's children, query the child table filtered by its parent_id. Enforce required parent existence with a real database foreign key and/or a backend boundary that covers every write path. An integer column named parent_id alone is not enforcement.",
            "Decide what parent deletion means for child records. Restrict deletion, keep/soft-retire the parent or use an explicitly permitted cascade. If historical children must remain, do not silently delete them or leave broken links. Many-to-many needs a separate junction design and is beyond this bank.",
        ],
        "diagram": "Parent\n  parent_id P4\n       ^                ^\n       |                |\nChild C1             Child C2\n  parent_id P4         parent_id P4\n\nList: children WHERE parent_id = P4",
        "practice": "A tournament has many match records, and each match belongs to one tournament. Draw two tables and two sample matches, describe the listing query and explain a deletion policy if completed match history must remain available.",
        "reflection": "An analogy: several labelled folders each carrying the same project number. It stops working if labels are confused with mutable project names or if removing the project number leaves untraceable folders.",
    },
}


def render_resource(slug: str) -> str:
    lesson = LESSONS[slug]  # Exact allowlist lookup, never a filesystem path.
    paragraphs = "".join(f"<p>{escape(text)}</p>" for text in lesson["paragraphs"])
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{escape(lesson["title"])} — Concept Check</title>'
        '<style>body{font:18px/1.6 system-ui,sans-serif;max-width:52rem;margin:2rem auto;padding:0 1rem;color:#17213b;background:#fffdf6}'
        'h1{line-height:1.2}pre{white-space:pre-wrap;overflow-wrap:anywhere;padding:1rem;border:2px solid #17213b;background:#eef1ff;font-size:.9rem}'
        '.provenance{font-size:.9rem;color:#46516a}section{margin-top:2rem}a:focus-visible{outline:3px solid #204edd}</style></head><body><main>'
        f'<h1>{escape(lesson["title"])}</h1>'
        f'<p class="provenance">Local AI-authored explanation · unreviewed · version {RESOURCE_VERSION}. '
        'Guided study material; reading or selecting an answer does not establish understanding.</p>'
        f'{paragraphs}<pre>{escape(lesson["diagram"])}</pre>'
        f'<section><h2>Practice</h2><p>{escape(lesson["practice"])}</p>'
        '<p>Write your reasoning before discussing it with the tutor. Explain your assumptions and the consequence of each step.</p></section>'
        f'<section><h2>Where the analogy stops</h2><p>{escape(lesson["reflection"])}</p></section>'
        '</main></body></html>'
    )


@router.get("/{slug}", response_class=HTMLResponse)
def get_resource(slug: str):
    try:
        html = render_resource(slug)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown authored resource") from None
    return HTMLResponse(html, headers={
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'self'",
        "X-Content-Type-Options": "nosniff",
        "X-Resource-Version": RESOURCE_VERSION,
    })
