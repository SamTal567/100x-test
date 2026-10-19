"""Prepared Module 2 cases. Keys remain private; all material awaits human review.

Stable skills are shared by baseline and fresh situations. A correct constrained
selection is objective exercise evidence, never a conceptual understanding grade.
"""

from uuid import NAMESPACE_URL, uuid5


def authored_id(slug, key):
    return str(uuid5(NAMESPACE_URL, f"concept-check/{slug}/{key}"))


# skill -> (criterion, expected reasoning, acceptable alternatives, misconception, neutral probe)
SKILLS = {
    "endpoint_contract": (
        "Matches the stated endpoint contract",
        "Uses the contract's method, path, required names and value types rather than guessing from conventions.",
        "A correctly annotated request, pseudocode or plain-language mapping is sufficient; field order is irrelevant.",
        "Any request containing the right value reaches the same handler regardless of method, path or field name.",
        "Which parts of the stated contract did you compare with the request?",
    ),
    "request_parts": (
        "Distinguishes request parts",
        "Separates method/path, headers and body, using the placement the particular server contract states.",
        "A table or labelled arrows can replace raw HTTP; HTTP header names are case-insensitive.",
        "A header and a JSON body property with the same name are interchangeable.",
        "Where in the submitted request would the server find each value you mentioned?",
    ),
    "contextual_diagnosis": (
        "Diagnoses using available evidence",
        "Draws only conclusions justified by the documented status/error and stated reachability assumptions.",
        "A conditional diagnosis is accepted when it explicitly identifies a fact the scenario leaves unknown.",
        "A failed request proves the database, network or API key is broken without checking the given evidence.",
        "What does the supplied observation establish, and what remains unknown?",
    ),
    "validation_boundary": (
        "Enforces validation at the server boundary",
        "Explains that callers can bypass browser checks, so every relevant server input needs validation.",
        "Validation in middleware, a typed schema or application service is acceptable if every request passes it.",
        "A disabled button or browser min/max rule prevents all invalid requests.",
        "Which callers and request paths does your explanation cover?",
    ),
    "validation_contract": (
        "Applies stated data constraints",
        "Checks required fields, type and domain constraints from the contract without inventing new restrictions.",
        "Rejecting or documented normalisation is acceptable only when compatible with the stated contract.",
        "Parsing valid JSON establishes that its values meet the business rules.",
        "Which supplied rule supports each accept or reject decision?",
    ),
    "validation_write_boundary": (
        "Rejects before side effects",
        "Explains that invalid input must not produce a write or a success result, and errors should identify the bad input.",
        "A transaction that rolls back all invalid writes is acceptable; no particular HTTP error code is required unless specified.",
        "Writing first and showing a client error later undoes the persisted change automatically.",
        "What state would exist after the rejected request in your proposed sequence?",
    ),
    "secret_isolation": (
        "Keeps provider secrets outside the client",
        "Treats browser bundles, network requests and browser storage as visible to the person running the client.",
        "Any server-controlled secret store is acceptable; an environment variable is safe here only when read solely by backend code.",
        "Minification, a frontend environment variable or an obscured header hides a provider secret from browser users.",
        "Who can inspect each environment or request you identified?",
    ),
    "backend_provider_path": (
        "Separates browser and provider requests",
        "Routes browser data to the backend; the backend loads the provider key and makes the provider request.",
        "A backend function or server-side proxy qualifies; browser-visible short-lived public tokens are outside these provider-key scenarios.",
        "The backend can keep a key secret while returning it to the browser to call the provider.",
        "What data crosses each boundary in your proposed request path?",
    ),
    "secret_lifecycle": (
        "Handles configuration and exposed keys",
        "Separates backend configuration from shipped client code and recognises that removing a leaked key does not revoke copies.",
        "Revocation/replacement through the provider and updating backend configuration are accepted without requiring a particular hosting vendor.",
        "Deleting a key from the next build makes an already downloaded key unusable.",
        "What happens to copies or configuration from the earlier deployment?",
    ),
    "save_boundary": (
        "Distinguishes saved records from screen state",
        "Identifies whether the operation committed durable data rather than inferring it from a toast or DOM update.",
        "An optimistic display is valid if it is identified as pending and later reconciled with success or failure.",
        "A visible item or success toast proves a database write completed.",
        "Which observation tells you about storage, and which tells you about the screen?",
    ),
    "retrieval_path": (
        "Connects retrieval to display",
        "Explains an explicit query/read, returned response and rendering step for existing saved data.",
        "Server-rendered HTML or client fetching is acceptable; no specific frontend state library is required.",
        "Saving to the database automatically updates every screen or reloads every process variable.",
        "How does the displayed value get from its stored location to the screen?",
    ),
    "history_context": (
        "Separates history, references and usable data",
        "Distinguishes saved records/file references from data actually retrieved and passed to a model or renderer.",
        "Selecting a bounded relevant subset is acceptable; a model need not receive the full stored history.",
        "A database row or file path makes all content automatically available to a model or renderer.",
        "What is stored, and what exactly is supplied to the next consumer?",
    ),
    "entity_identity": (
        "Uses stable entity identifiers",
        "Distinguishes instances with stable IDs even when labels are duplicated or changed.",
        "Generated integers, UUIDs or another unique stable key are accepted; no one identifier format is mandatory.",
        "A mutable display name is always a sufficient permanent identifier.",
        "How would your records distinguish two objects with the same label?",
    ),
    "entity_attributes": (
        "Assigns attributes to the right entity",
        "Places facts on the entity they describe and distinguishes a repeated independent object from one attribute.",
        "Reasonable names and equivalent tables are accepted when the stated independent identities are preserved.",
        "Every noun must be a new table, or repeated independent records can always be one text field.",
        "What object does each field describe in your proposed model?",
    ),
    "history_reference": (
        "Preserves historical facts and file references",
        "Separates mutable current attributes from recorded historical facts, and a file reference from the file bytes.",
        "A snapshot field or a versioned referenced record is acceptable if the historical value remains reproducible.",
        "Updating the current catalogue value should rewrite old transaction facts, or a file path contains the file bytes.",
        "Which value should a reader see later, and where would that value come from?",
    ),
    "relationship_cardinality": (
        "Derives the stated relationship",
        "Distinguishes one parent per child and multiple children per parent from many-to-many or one-to-one requirements.",
        "A sentence, diagram or sample rows are accepted; notation is not graded.",
        "One-to-many means each parent must have several children, or a child belongs to several parents.",
        "How many related records are permitted on each side under the stated rules?",
    ),
    "foreign_key_placement": (
        "Places and uses the child foreign key",
        "Uses a parent identifier on each child and retrieves children by that relationship rather than by matching display names.",
        "Equivalent table/column names are accepted; a query description can replace SQL.",
        "A single child ID on the parent can represent arbitrary numbers of children, or matching labels is a stable link.",
        "Show where the relationship for one particular child would be stored.",
    ),
    "relationship_integrity": (
        "Preserves valid relationship records",
        "Uses stable keys and an explicit policy so a child does not silently refer to a missing or wrong parent.",
        "Restrict, soft-delete, or an explicit documented cascade may be valid when the scenario permits it; distinguish each consequence.",
        "A foreign-key-shaped integer automatically guarantees that its parent exists, or deleting a parent has no consequences.",
        "What would your model do in the changed or missing-parent example?",
    ),
}


def criterion(skill, applicability=None):
    title, description, alternative, misconception, probe = SKILLS[skill]
    crit = {
        "criterion": title, "skill_id": skill, "description": description, "weight": 1.0,
        "acceptable_alternatives": [alternative], "common_misconceptions": [misconception],
        "follow_up_probes": [probe],
    }
    if applicability:
        crit["applicability"] = applicability
        if applicability == "unprompted":
            crit["unprompted"] = True
            crit["unprompted_note"] = "The scenario did not explicitly ask how to handle key revocation, replacement, or downloaded copies."
    return crit


def case(slug, key, kind, order, scenario, assumptions, answer, skill_ids, *, diagram=None, cloze=None, criterion_applicability=None):
    stage = "diagnostic" if kind == "baseline" else "investigate" if kind == "guided_practice" else "apply"
    crit_app = criterion_applicability or {}
    return {
        "authored_id": authored_id(slug, key), "stage": stage, "case_type": kind, "sort_order": order,
        "scenario_text": scenario, "assumptions": assumptions,
        "response_format": "cloze" if cloze else f"diagram_{diagram['interaction_type']}" if diagram else "written",
        "diagram_preset": diagram, "cloze_preset": cloze,
        "source": "ai-authored", "review_status": "unreviewed",
        "rubric": {"reference_answer": answer, "criteria": [criterion(s, applicability=crit_app.get(s)) for s in skill_ids]},
    }


def repair(key, title, left, middle, options, instruction):
    """options: (node id, label); first option is the prepared repair key."""
    return {
        "diagram_id": key, "title": title, "interaction_type": "repair", "task_instruction": instruction,
        "nodes": [
            {"id": "source", "label": left, "x": 60, "y": 70, "type": "actor"},
            {"id": "process", "label": middle, "x": 220, "y": 70, "type": "process"},
            *[{"id": node, "label": label, "x": 400, "y": 35 + i * 95, "type": "process"}
              for i, (node, label) in enumerate(options)],
        ],
        "edges": [
            {"id": "request", "from": "source", "to": "process", "label": "input", "status": "correct"},
            {"id": "repair_path", "from": "process", "to": options[1][0], "label": "current path", "status": "needs_repair"},
        ],
        "repair_edge_id": "repair_path",
        "repair_options": [{"id": f"to_{node}", "label": label, "target_node": node} for node, label in options],
        "correct_repair": f"to_{options[0][0]}",
    }


def trace(key, title, labels, question, options):
    return {
        "diagram_id": key, "title": title, "interaction_type": "trace",
        "task_instruction": "Select the supported step/outcome and explain its effect in this scenario.",
        "nodes": [{"id": f"n{i}", "label": label, "x": 60 + i * 170, "y": 70, "type": "process"} for i, label in enumerate(labels)],
        "edges": [{"id": f"e{i}", "from": f"n{i}", "to": f"n{i+1}", "label": "then", "status": "active"} for i in range(len(labels) - 1)],
        "blanks": [{"id": "outcome", "prompt": question, "options": options, "correct": options[0]}],
    }


def cloze(key, sentence, blanks, explanation):
    return {
        "cloze_id": key, "sentence_template": sentence,
        "blanks": [{"id": name, "options": options, "correct": options[0]} for name, options in blanks],
        "justification_prompt": explanation,
    }


REQUEST_CASES = [
    case("request-anatomy", "base-contract", "baseline", 1,
         "A campus API documents POST /questions, Content-Type: application/json, body {\"question\": string}. A reachable server receives POST /questions with JSON {\"prompt\": \"Why rain?\"} and returns 422: question is required. Explain what matches, what does not, and the smallest contract-compatible repair. Does this response establish a network outage?",
         ["The route exists and the request reached its validator", "The only required body field is question, a nonempty string", "No provider or database operation ran"],
         "Method and path match, and the request carries JSON, but prompt is not the required question field. Send {\"question\":\"Why rain?\"} with the documented content type. The 422 supplies evidence of a reachable validation failure, not a network outage; it says nothing about later provider health.",
         ["endpoint_contract", "request_parts", "contextual_diagnosis"]),
    case("request-anatomy", "base-route", "baseline", 2,
         "A notes contract defines GET /notes/42 with no body to read note 42, and POST /notes with JSON {\"text\": string} to create one. A client sends POST /notes/42 with a text body and gets 405 Method Not Allowed. Trace the intended read request and explain whether changing only the text value solves this error.",
         ["Note 42 exists", "The server is reachable", "The contract lists all supported methods for these paths"],
         "Read with GET /notes/42 and no body. The submitted POST method is unsupported for that path, so changing the JSON text cannot repair method routing. The 405 is evidence of method mismatch, not proof that the note is absent.",
         ["endpoint_contract", "request_parts", "contextual_diagnosis"],
         diagram=trace("request-read-trace", "Reading a note", ["Browser", "Method + path routing", "Note read handler"], "Which request reaches the read handler?", ["GET /notes/42, no body", "POST /notes/42 with text", "GET /notes with question header"])),
    case("request-anatomy", "practice-header", "guided_practice", 3,
         "A translation endpoint accepts POST /translate. Its contract reads locale from the X-Locale header and text from a JSON body. The client currently puts both locale and text in JSON; the server reports X-Locale missing. Repair the locale path and explain which value remains in the body.",
         ["Only X-Locale supplies locale for this endpoint", "The body schema requires text", "The request reached the server"],
         "Put the locale value in X-Locale and keep text in the JSON body with Content-Type application/json. A JSON locale property does not substitute for the header under this contract. The missing-header observation identifies a contract mismatch, without establishing a provider failure.",
         ["endpoint_contract", "request_parts", "contextual_diagnosis"],
         diagram=repair("request-header-repair", "Separate header from body", "Browser", "Locale value", [("header", "X-Locale request header"), ("body", "JSON locale property")], "Repair the locale placement; explain the text placement too.")),
    case("request-anatomy", "practice-cloze", "guided_practice", 4,
         "A reachable backend accepts PATCH /tickets/7 with JSON {\"status\": \"closed\"}. Complete the request anatomy and justify why putting status in a custom header would not satisfy this body contract.",
         ["Ticket 7 exists", "The contract reads status only from JSON", "The caller is permitted to update it"],
         "PATCH is the method, /tickets/7 is the path, and status belongs in the JSON body. Under the explicit contract, a status header alone leaves the required body field missing. This is a request-shape question rather than an inference about deployment or storage.",
         ["endpoint_contract", "request_parts"],
         cloze=cloze("request-parts-cloze", "The method is {method}; the path is {path}; status is supplied in {location}.", [("method", ["PATCH", "GET", "HEADER"]), ("path", ["/tickets/7", "closed", "application/json"]), ("location", ["the JSON body", "a status header only", "the hostname"])], "Explain how each choice follows from this contract.")),
    case("request-anatomy", "transfer-query", "transfer", 5,
         "A library API documents GET /books?author=Ada with no body. A client sends GET /books with JSON {\"author\":\"Ada\"}; the server returns 400: author query parameter missing. Explain the repair and what this response does and does not establish.",
         ["This handler reads author only from the URL query", "The request reached the correct reachable server", "No matching query means validation stops before lookup"],
         "Use GET /books?author=Ada with the author encoded as a query value and no body as documented. The body property is not read as a query parameter. The 400 establishes the supplied request missed the expected query input, not that Ada has no books or the database is down.",
         ["endpoint_contract", "request_parts", "contextual_diagnosis"]),
    case("request-anatomy", "transfer-upload", "transfer", 6,
         "An image API accepts POST /images using multipart/form-data with a file field named image. The client instead sends JSON {\"image\":\"cat.png\"}; the reachable server reports a missing uploaded file. Explain a contract-compatible request and why changing the filename string cannot create the upload.",
         ["The API does not accept file URLs or JSON uploads", "cat.png exists on the client device", "No file bytes arrived in a multipart field"],
         "Submit the actual file bytes as multipart field image to POST /images, with a correctly generated multipart content type/boundary. A JSON filename is text, not an uploaded file. The supplied error supports an upload-shape mismatch and does not diagnose image processing health.",
         ["endpoint_contract", "request_parts", "contextual_diagnosis"]),
    case("request-anatomy", "transfer-localhost", "transfer", 7,
         "A React app deployed on a public website still calls http://localhost:8000/summarise. It works on the developer's laptop, where FastAPI runs on port 8000. A classmate opens the site on another laptop, which runs no backend. No HTTP response is received. Explain where localhost points and the configuration change needed before checking the API body contract.",
         ["Each browser executes on its own laptop", "No backend runs on the classmate's machine", "A reachable deployed HTTPS API URL can be configured"],
         "localhost refers to the machine making the browser request, so the classmate's browser calls the classmate's laptop. Configure the frontend to call the reachable deployed API origin, then use its documented method/path/body and CORS policy. No response from this local address cannot establish a JSON validation or database error.",
         ["request_parts", "contextual_diagnosis"]),
    case("request-anatomy", "confirmation-delete", "confirmation", 8,
         "A bookmark API documents DELETE /bookmarks/18 with an X-Workspace header and no body. A client calls DELETE /bookmarks with JSON {\"id\":18,\"workspace\":\"study\"}; the server returns 404 route not found. Describe a matching request and the narrow conclusion supported by that error.",
         ["Bookmark 18 exists in workspace study", "Only the documented DELETE route is registered", "The header is a workspace selector, not a provider secret"],
         "Call DELETE /bookmarks/18 with X-Workspace: study and no body. An id in JSON does not complete the missing path segment, nor does a body workspace substitute for the header. The error establishes route mismatch for this request; it does not prove the bookmark is absent.",
         ["endpoint_contract", "request_parts", "contextual_diagnosis"]),
]


VALIDATION_CASES = [
    case("backend-validation", "base-direct", "baseline", 1,
         "An event form allows ticket quantity 1 through 5 and disables Submit otherwise. The POST /reservations handler directly inserts the supplied quantity. Someone calls it with HTTP tooling and sends quantity -2. Explain which layer must enforce the stated rule and what should happen before any reservation is saved.",
         ["The server is reachable directly", "Quantity must be an integer from 1 through 5", "No reservation has yet been written"],
         "Browser controls improve feedback but do not constrain direct callers. The backend must verify the type and range for every request, reject -2 with a useful error, and avoid inserting a reservation. Parsing JSON alone is insufficient.",
         ["validation_boundary", "validation_contract", "validation_write_boundary"]),
    case("backend-validation", "base-json", "baseline", 2,
         "An API accepts JSON with email as a nonempty string and seats as an integer 1 through 4. A browser-validated caller sends {\"email\":\"\",\"seats\":\"two\"}. The handler parses the JSON, inserts a row and returns success. Trace where checking belongs and explain the two contract violations.",
         ["The API contract forbids an empty email and does not coerce seats strings", "The JSON is syntactically valid", "Failed input must create no row"],
         "JSON parsing establishes syntax only. Server validation must reject the empty email and noninteger seats before insertion, regardless of prior client validation. Return a field-specific failure and leave storage unchanged.",
         ["validation_boundary", "validation_contract", "validation_write_boundary"],
         diagram=trace("validation-order-trace", "Validate before writing", ["Parse input", "Validate constraints", "Write accepted record"], "For these invalid values, which step follows validation?", ["Return errors; skip write", "Insert then show toast", "Trust browser approval"])),
    case("backend-validation", "practice-write", "guided_practice", 3,
         "A donation API requires amount to be a positive integer in paise. Its current path sends parsed input straight to the database; the browser rejects negatives but a script sends -500. Repair the path and describe the resulting storage state.",
         ["Server code can inspect the input before inserting", "The invalid request has not been committed", "No automatic coercion is part of the contract"],
         "Route parsed input through backend contract validation, then write only on success. Reject -500 and store nothing from the request. Keeping a browser check is useful but does not replace this boundary.",
         ["validation_boundary", "validation_contract", "validation_write_boundary"],
         diagram=repair("validation-boundary-repair", "Protect the write", "Any HTTP caller", "Parsed donation input", [("validate", "Backend validation before insert"), ("insert", "Insert without checking")], "Choose the next step for parsed input and explain the rejection behavior.")),
    case("backend-validation", "practice-cloze", "guided_practice", 4,
         "A profile API requires age to be an integer 18 through 120. A mobile app and a website call the same endpoint. Complete the scaffold for a direct request with age 12; justify the write decision.",
         ["Age 12 is outside the stated product contract", "All callers use the same server handler", "No record has yet changed"],
         "Validation belongs on the backend for all callers. Age 12 fails the stated range, so return an input error and do not update the record. This follows the product contract rather than a claim about all real-world age rules.",
         ["validation_boundary", "validation_contract", "validation_write_boundary"],
         cloze=cloze("validation-cloze", "The authoritative check runs on {layer}; age 12 is {decision}; the database should {write}.", [("layer", ["the backend", "the website only", "the user's keyboard"]), ("decision", ["outside the allowed range", "valid because JSON parsed", "valid because a mobile app sent it"]), ("write", ["remain unchanged for this request", "store 12 before checking", "change after an error toast"])], "Explain why another caller cannot bypass the chosen boundary.")),
    case("backend-validation", "transfer-file", "transfer", 5,
         "An upload UI accepts PDF files up to 2 MB. A direct multipart request reaches the backend carrying a 6 MB text file. The backend stores any uploaded bytes immediately. Explain the backend checks required by this contract and the response/storage behavior for this request.",
         ["The contract permits only PDF up to 2 MB", "The actual bytes and size are available to the backend", "No file has yet been retained"],
         "Enforce the size and supported PDF format on the backend using the supplied bytes/size rather than trusting the file picker or filename. Reject this request and retain no permanent upload/row. A clear error can identify both violated constraints; this does not require full malware scanning or ownership modeling.",
         ["validation_boundary", "validation_contract", "validation_write_boundary"]),
    case("backend-validation", "transfer-enum", "transfer", 6,
         "A task API accepts status only as todo, doing or done, and title as a nonempty string. A new integration sends {\"status\":\"finished\",\"title\":\"Draft\"}. The dashboard dropdown never emits finished. Explain whether the API may save it and where the contract must be enforced.",
         ["There is no documented mapping from finished to done", "Integrations call the API directly", "Validation failures must not create tasks"],
         "The valid title does not make the unsupported status valid. The backend must reject finished before writing and state the permitted statuses. The UI dropdown cannot constrain an integration, and silently normalising finished is outside the stated contract.",
         ["validation_boundary", "validation_contract", "validation_write_boundary"]),
    case("backend-validation", "transfer-atomic", "transfer", 7,
         "A booking endpoint accepts a nonempty attendee and count 1 through 3. A handler inserts a booking first, then notices count is 0 and returns 400. The frontend displays an error, yet the booking remains in the database. Explain what failed in the sequence and a valid repair.",
         ["The insert committed before the check", "An error response does not roll back a committed row", "Invalid input must leave no booking"],
         "The handler checked too late: a client-visible failure does not undo committed data. Validate the attendee/count on the server before the insert, or validate within a transaction that rolls back completely before commit. For count 0, return an error and create no booking regardless of the caller.",
         ["validation_boundary", "validation_contract", "validation_write_boundary"]),
    case("backend-validation", "confirmation-length", "confirmation", 8,
         "A feedback API requires message length 1 through 500 characters. Browser JavaScript truncates long input. A script sends 700 characters directly. Explain what the backend should do, what happens to storage, and why the browser feature is insufficient.",
         ["The server contract rejects excess length rather than truncating", "Length is measured after decoding using the same stated character rule", "Nothing has yet been written"],
         "The backend must enforce 1 through 500 for every request, reject 700 with a useful validation error and leave storage unchanged. Browser truncation is feedback for one client and can be bypassed; silently truncating at the server would violate this explicit reject contract.",
         ["validation_boundary", "validation_contract", "validation_write_boundary"]),
]


SECRET_CASES = [
    case("secret-placement", "base-bundle", "baseline", 1,
         "A React summariser reads a long-lived provider key from a frontend build environment variable and sends it in a browser Authorization header directly to the provider. The build is minified. Explain who can recover the key and draw or describe a request path that keeps this provider secret backend-only.",
         ["The variable value is compiled into shipped browser JavaScript", "The provider key is a secret, not a designated public client token", "A FastAPI backend can make outbound provider calls"],
         "Anyone running the client can inspect its bundle and outgoing request, so minification and the environment-variable name do not protect the key. The browser sends the user's text to FastAPI without that key; FastAPI reads a backend-only configured key and calls the provider, then returns the needed result. An exposed key must be revoked/replaced, not merely removed from a new build.",
         ["secret_isolation", "backend_provider_path", "secret_lifecycle"],
         criterion_applicability={"secret_lifecycle": "unprompted"}),
    case("secret-placement", "base-proxy", "baseline", 2,
         "A backend reads a provider key from its environment but implements GET /config returning that key to the browser. The browser then calls the provider. Trace whether the key stayed secret, explain a replacement flow, and what to do about copies already downloaded.",
         ["/config is callable by ordinary users", "The provider key permits billable calls", "This is a long-lived server credential"],
         "The environment is server-side, but returning the value crosses into a user-inspectable environment. Remove the key-returning path and let the backend call the provider on the browser's behalf. Revoke/rotate the exposed credential and update backend configuration because downloaded copies survive code changes.",
         ["secret_isolation", "backend_provider_path", "secret_lifecycle"],
         diagram=trace("secret-proxy-trace", "Where the value travels", ["Backend environment", "GET /config response", "Browser user"], "Which fact determines exposure here?", ["The response contains the secret value", "The variable name says server", "The response used HTTPS"])),
    case("secret-placement", "practice-provider", "guided_practice", 3,
         "A browser image generator currently calls a paid provider directly with a secret copied into its bundle. A backend endpoint /generate already accepts the prompt. Repair where the browser sends the prompt; describe where the provider key is loaded and how to respond to its earlier exposure.",
         ["The backend can reach the provider", "The browser must receive only the generated result", "The old bundle has already been downloaded"],
         "Send the prompt to /generate; the backend loads its secret configuration and calls the provider. Return the result without echoing the credential. Revoke/replace the old exposed key; moving the next copy alone does not invalidate downloaded copies. Backend caller checks/limits are a separate operational consideration, not a new authentication criterion here.",
         ["secret_isolation", "backend_provider_path", "secret_lifecycle"],
         diagram=repair("secret-request-repair", "Browser request destination", "Browser prompt", "Outgoing request", [("backend", "Own backend /generate (no provider key)"), ("provider", "Paid provider with embedded secret")], "Choose the browser destination and explain both requests.")),
    case("secret-placement", "practice-cloze", "guided_practice", 4,
         "A speech feature uses a paid provider secret. Complete the browser/backend boundary and justify whether storing the secret in browser localStorage would solve exposure.",
         ["The backend can send the audio to the provider", "This is a server secret, not an intentionally public identifier", "The browser user can inspect localStorage and network requests"],
         "The browser sends audio to the backend without the provider secret. The backend reads its private configuration and sends the provider request. localStorage remains client-controlled and inspectable, so it is not a secret store for this key.",
         ["secret_isolation", "backend_provider_path"],
         cloze=cloze("secret-boundary-cloze", "The browser calls {destination}; the provider credential is read by {reader}; browser localStorage is {visibility}.", [("destination", ["our backend with audio only", "the provider with the secret", "a public config download"]), ("reader", ["backend code", "the shipped React bundle", "a hidden HTML input"]), ("visibility", ["inspectable by the browser user", "a backend-only vault", "protected by minification"])], "Explain the two outgoing requests and who can inspect each.")),
    case("secret-placement", "transfer-build", "transfer", 5,
         "A deployed quiz site builds a JSON settings file containing a long-lived translation-provider secret. Frontend code fetches the file over HTTPS and calls the provider. The file is not linked in the UI. Explain the exposure, repair the flow and handle the shipped credential.",
         ["Any site user can fetch the settings URL", "The value is a secret provider credential", "An existing backend can make translation requests"],
         "The browser fetch exposes the secret to its user despite HTTPS and the hidden link. Keep the value in backend-only configuration and send translation input to a backend endpoint that calls the provider. Revoke/replace the shipped key and update the backend; removing the JSON file does not revoke existing copies.",
         ["secret_isolation", "backend_provider_path", "secret_lifecycle"]),
    case("secret-placement", "transfer-debug", "transfer", 6,
         "An API correctly calls a paid model from the backend but includes the full outbound Authorization header in a debug object returned with every result. A student says it is safe because the key was never written in React source. Evaluate the claim and describe a safe result payload and incident response.",
         ["The debug object reaches ordinary browser users", "Authorization contains the actual long-lived provider secret", "No key value is needed to display the model answer"],
         "The returned header leaks the credential independently of where it originated. Remove the secret and provider headers from learner responses, return only the needed answer and safe diagnostics, and keep provider calls server-side. Revoke/replace the leaked key and update backend configuration because prior recipients may have retained it.",
         ["secret_isolation", "backend_provider_path", "secret_lifecycle"]),
    case("secret-placement", "transfer-deploy", "transfer", 7,
         "A local FastAPI app reads its provider key from a backend environment variable. On deployment, the operator sets only a similarly named frontend build variable, so backend provider calls report missing configuration. Explain where to configure the key, what the browser should send, and what to check if a build has shipped that value.",
         ["Backend and frontend build environments are separate", "The backend error explicitly reports missing key configuration", "Frontend variables used in its bundle become public"],
         "Configure the credential in the deployed backend runtime, where the provider adapter reads it. The browser sends user input to that backend without a provider key. A frontend build variable does not configure the separate server and can expose the value if bundled; if shipped, revoke/replace it and rebuild without it.",
         ["secret_isolation", "backend_provider_path", "secret_lifecycle"]),
    case("secret-placement", "confirmation-rotation", "confirmation", 8,
         "A PDF summariser once shipped a provider secret in browser JavaScript. The next version sends document text to FastAPI, which calls the provider with a backend environment variable. The team has not revoked the original key. Explain what improved, what remains exposed and the remaining action.",
         ["Earlier users can retain the downloaded old bundle", "Both versions used the same long-lived provider credential", "The new backend response contains only the summary"],
         "The new request path keeps future configured provider access on the backend and does not return its key. Old downloaded copies still contain a usable credential until it is revoked/replaced. Rotate through the provider, update backend configuration and keep the replacement outside all browser artifacts.",
         ["secret_isolation", "backend_provider_path", "secret_lifecycle"]),
]


PIPELINE_CASES = [
    case("save-retrieve-display", "base-optimistic", "baseline", 1,
         "A journal page immediately adds a new entry to its visible list and shows Saved. POST /entries then fails before any database commit. After reload, GET /entries returns no such entry. Explain the difference between the first screen and stored state, and a reliable save/read/display sequence.",
         ["The optimistic item exists only in browser state", "The failed request wrote nothing", "GET reads committed entries from the database"],
         "The first visible item proves only a browser update, not persistence. Mark it pending, submit the POST, and show saved only after confirmed commit; on failure remove/retry or clearly mark it unsaved. Reload must GET stored entries and render that response, which correctly lacks the failed entry.",
         ["save_boundary", "retrieval_path"]),
    case("save-retrieve-display", "base-model", "baseline", 2,
         "A chatbot commits every message to a history table. On the next turn, its model request contains only the latest user message; no query loads earlier messages. The user expects the model to recall yesterday's address. Trace the missing step and distinguish saved history from actual model input.",
         ["The model request starts without hidden persistent memory", "Earlier history rows remain readable", "No retrieval or history messages are sent in this request"],
         "The messages are saved but absent from this model request. Query relevant history, construct the permitted bounded model input, call the model and render its response; storing rows does not automatically include them. It need not send all history, and it should not claim the model saw an address it never received.",
         ["save_boundary", "retrieval_path", "history_context"],
         diagram=trace("history-model-trace", "Saved history and model input", ["History database", "Explicit query + input assembly", "Model request"], "What makes previous messages available to this call?", ["Retrieving and including relevant messages", "Naming the table history", "Displaying yesterday's conversation only"])),
    case("save-retrieve-display", "practice-read", "guided_practice", 3,
         "A feedback form successfully commits feedback rows. The dashboard always renders a hardcoded empty array and never calls GET /feedback. Repair the read path and explain why an empty screen does not prove the write failed.",
         ["The write transaction succeeded", "GET /feedback reads the saved rows", "No automatic live-update connection exists"],
         "Replace the empty-array input with a request that reads saved rows and passes the returned data to rendering. The committed write and missing display are different steps: a screen that never retrieves rows can remain empty even when storage is correct.",
         ["save_boundary", "retrieval_path"],
         diagram=repair("pipeline-read-repair", "Supply the renderer", "Dashboard", "Data source", [("query", "GET /feedback then render returned rows"), ("empty", "Hardcoded empty array")], "Choose the dashboard's data path and explain the saved-state evidence.")),
    case("save-retrieve-display", "practice-cloze", "guided_practice", 4,
         "A document app stores a row containing file_id and a private storage path. Its model request currently sends only that path string, while the model has no storage access. Complete the scaffold and explain the separate retrieval and input steps.",
         ["The file bytes are safely stored", "The path is an identifier, not the content", "Backend code can read and extract supported file content"],
         "A file reference identifies stored bytes but is not itself the document text. The backend must read the file, extract supported content and explicitly include appropriate content in the model request. Rendering a filename or saving the row does not perform these operations.",
         ["retrieval_path", "history_context"],
         cloze=cloze("file-context-cloze", "The path is {reference}; the backend must {retrieve}; the model sees {context}.", [("reference", ["a reference to stored bytes", "all the document text", "an automatic model memory"]), ("retrieve", ["read and prepare the file content", "rename the row model_context", "show a Saved toast"]), ("context", ["only content explicitly provided to this call", "every file in the database", "all earlier browser screens"])], "Explain why a stored reference alone is insufficient.")),
    case("save-retrieve-display", "transfer-search", "transfer", 5,
         "A reading tracker commits book 27 and returns its ID. Its list screen performs GET /books once before the save and never refreshes. A second device queries the same API and sees book 27. Explain what each observation establishes and how to update the first screen without re-saving the book.",
         ["Both devices use the same database", "The commit succeeded", "The first screen has no push subscription"],
         "The commit/second-device read support that book 27 is saved. The first screen is a stale rendered result, not proof of loss. Refetch the list or merge the confirmed server record into display state; do not create another row merely to refresh the screen.",
         ["save_boundary", "retrieval_path"]),
    case("save-retrieve-display", "transfer-summary", "transfer", 6,
         "A study app stores five lesson transcripts. A summary job selects only transcript 5 and sends its extracted text to a model. The UI labels the result Summary of all five lessons. Explain the mismatch, what a correct pipeline must do, and what can truthfully be displayed for the current result.",
         ["All five database rows and files exist", "The actual request includes only transcript 5", "The model has no independent access to stored files"],
         "Persistence of five transcripts does not make all five model inputs. Query/read/prepare the intended lessons and explicitly supply an appropriate bounded representation before producing an all-lessons summary. The current result can be labelled a summary of lesson 5; neither a stored filename nor the UI label changes what the model saw.",
         ["save_boundary", "retrieval_path", "history_context"]),
    case("save-retrieve-display", "transfer-file", "transfer", 7,
         "An invoice list loads a database row with invoice_id and file_path. It displays the filename, but clicking preview sends the path text to a renderer that expects PDF bytes. The file exists in storage. Explain which parts worked and the missing retrieval step.",
         ["The row and file were saved successfully", "The renderer cannot fetch paths by itself", "The backend has a route that reads the referenced file"],
         "Saving the row/file and displaying metadata worked. A path reference is not the PDF bytes: the preview flow must request the file through the serving route and pass the returned supported bytes/URL to the renderer. This is a missing read/display integration, not evidence that the file was never saved.",
         ["save_boundary", "retrieval_path", "history_context"]),
    case("save-retrieve-display", "confirmation-history", "confirmation", 8,
         "After reload, a coaching app queries saved conversation rows and correctly displays yesterday's messages. Its next model call includes only today's question. Explain why visible history does not guarantee model recall and describe the separate data paths.",
         ["The historical rows are committed and retrievable", "The model sees only the constructed request", "The browser display is not automatically sent to the model"],
         "The screen proves that retrieval/rendering of saved history works. Model context is a separate request path: retrieve/select relevant messages and explicitly include them before calling the model. The current call can answer today's question but cannot rely on yesterday's unseen content merely because it was displayed.",
         ["save_boundary", "retrieval_path", "history_context"]),
]


ENTITY_CASES = [
    case("entities-attributes", "base-duplicates", "baseline", 1,
         "A library has two different books titled Introduction to Python, each with its own copy of publication year and author. A learner records one row per title and uses title as the permanent key. One book is later retitled. Propose entities, attributes and stable identifiers that preserve both books.",
         ["These are distinct book editions, not multiple physical copies", "Titles can duplicate and change", "No borrowing relationship is required in this question"],
         "Use a book/edition entity with a unique stable book_id and attributes title, author and publication_year. Keep separate rows/IDs for the two editions, and update only the title attribute on retitling. A duplicate or mutable display label is not a reliable identity; no extra table is required for every descriptive word.",
         ["entity_identity", "entity_attributes"]),
    case("entities-attributes", "base-history", "baseline", 2,
         "A shop stores a product's current price and an order line for a sale made at ₹300. The product price changes to ₹350. A receipt file also has a stored path. Describe which attributes belong to product, order line and file reference, and how the original receipt amount remains reproducible.",
         ["An order line records the price actually charged", "Current product price can change", "The path points to separately stored file bytes"],
         "Product has a stable product_id and mutable current_price. The order line has its own identity and recorded unit_price ₹300 (or an immutable price-version reference), so later catalogue edits do not rewrite the sale. A receipt path identifies a separate stored file; it does not contain the file bytes.",
         ["entity_identity", "entity_attributes", "history_reference"],
         diagram=trace("entity-price-trace", "Current and historical facts", ["Product current price ₹350", "Past order line", "Receipt rendering"], "Which amount belongs on the past line?", ["₹300 charged at purchase", "Always current ₹350", "The receipt filename"])),
    case("entities-attributes", "practice-stable", "guided_practice", 3,
         "Two college clubs share the display name Coding Club. One changes its name next term. A club profile is currently looked up solely by display name. Repair the lookup identity and explain which facts are editable attributes.",
         ["The clubs are independent entities", "Names can duplicate and change", "Each club can have a generated unique identifier"],
         "Give each club a stable club_id and use it for lookup; display_name and description are editable attributes. Duplicate names and renaming then do not merge or lose records. Integer or UUID keys are both suitable.",
         ["entity_identity", "entity_attributes"],
         diagram=repair("entity-key-repair", "Identify a club", "Profile link", "Lookup value", [("stable", "Stable unique club_id"), ("name", "Mutable display name only")], "Choose the identity used by the profile link and explain renaming.")),
    case("entities-attributes", "practice-cloze", "guided_practice", 4,
         "A repair shop stores the current service price, a completed job's charged amount and a photo path for that job. Complete the scaffold and explain why changing the current service price should not change the old bill.",
         ["Completed bills record actual charged amounts", "Current prices may change", "Photos live in separate file storage"],
         "A stable job_id identifies the completed job; charged_amount records the historical fact, while the service's current_price remains mutable. photo_path is a reference to bytes stored elsewhere. A versioned price reference is also valid if it preserves the exact billed value.",
         ["entity_identity", "entity_attributes", "history_reference"],
         cloze=cloze("entity-history-cloze", "A completed job is identified by {identity}; its bill uses {price}; photo_path stores {file}.", [("identity", ["a stable job_id", "the changing service name", "the price alone"]), ("price", ["the amount recorded at service time", "whatever the current price is", "the photo filename"]), ("file", ["a reference to stored photo bytes", "all the photo pixels", "the current service price"])], "Explain each field's role and one acceptable historical-price design.")),
    case("entities-attributes", "transfer-people", "transfer", 5,
         "A conference has two speakers named Meera Shah. One changes her display name after marriage. A draft model uses name as speaker identity and places talk duration on the speaker row even though a speaker may give distinct talks. Propose entities, keys and attribute placement.",
         ["Speakers and talks are separately identifiable", "A speaker's different talks can have different durations", "No co-presenter or many-to-many modeling is required"],
         "Use separate stable speaker_id and talk_id, keep each person's display_name on Speaker and duration/title on Talk. Duplicate or changed names do not change identity. The model can refer to the speaker by stable ID; detailed relationship assessment belongs to its own concept.",
         ["entity_identity", "entity_attributes"]),
    case("entities-attributes", "transfer-rental", "transfer", 6,
         "A cycle shop changes its current daily rate from ₹100 to ₹120. Last week's rental was charged ₹100 per day; its signed agreement is in file storage. Identify the cycle/rental facts and stable IDs needed so a later bill remains accurate and the agreement can be located.",
         ["Each cycle and each rental is a distinct record", "The past charge must remain reproducible", "Files are kept outside the relational rows"],
         "Use stable cycle_id and rental_id. Keep the cycle's current rate on the current catalogue entity and the actual ₹100 rate on the rental or an immutable price version. Store an agreement file reference on the rental; retrieve the referenced bytes separately. Updating today's rate must not recalculate the old charge.",
         ["entity_identity", "entity_attributes", "history_reference"]),
    case("entities-attributes", "transfer-snapshot", "transfer", 7,
         "A training company corrects a course title after certificates were issued. The product rule says an issued certificate must reproduce the title printed at issue time. The draft stores only the course's current title and a certificate filename. Explain a sufficient model and what the filename represents.",
         ["Current course titles can change", "Issued certificate content is a historical fact", "Certificate files exist in separate storage"],
         "Give courses and certificates stable identifiers. Preserve title_at_issue on the certificate or an immutable referenced course version while allowing the course's current title to change. A filename/path locates the stored certificate bytes; it does not itself preserve all printed facts unless the referenced immutable file is retained and available.",
         ["entity_identity", "entity_attributes", "history_reference"]),
    case("entities-attributes", "confirmation-menu", "confirmation", 8,
         "Two menu dishes have the same display name. A restaurant changes one price after an order was placed and stores a receipt file in external storage. Describe stable identities, current versus historical attributes and the meaning of receipt_path.",
         ["Dishes and order lines have separate identities", "The past order must keep its charged price", "A receipt path points to actual stored bytes"],
         "Use stable dish_id/order_line_id rather than names, keep mutable name/current_price on dishes and the charged price on each historical order line or immutable price version. receipt_path is a reference used to locate the separate receipt file. Name/price edits must not merge dishes or rewrite past charges.",
         ["entity_identity", "entity_attributes", "history_reference"]),
]


RELATIONSHIP_CASES = [
    case("one-to-many", "base-posts", "baseline", 1,
         "A blog allows one author to write zero or more posts; every post must have exactly one author. Authors can change display names. Show small Author and Post tables, identify the foreign key and explain how to list one author's posts without relying on names.",
         ["There are no co-authored posts", "author_id is unique and stable", "Every new post must refer to an existing author"],
         "Author has author_id and display_name; Post has post_id, title and author_id referencing Author.author_id. A query filters Post.author_id by the chosen stable author ID, so zero or many rows are possible. Validate/enforce that each required parent exists; an author rename does not alter the link.",
         ["relationship_cardinality", "foreign_key_placement", "relationship_integrity"]),
    case("one-to-many", "base-rooms", "baseline", 2,
         "Each hostel room belongs to exactly one hostel, and a hostel may have many rooms or none yet. The draft stores a single room_id on Hostel and only hostel_name on Room. Two hostels may share a name. Repair the model and explain how a room for a nonexistent hostel should be handled.",
         ["Hostel IDs are stable and unique", "The product rejects rooms whose hostel does not exist", "Names may duplicate"],
         "Put hostel_id on each Room, referencing Hostel.hostel_id; a single room_id on Hostel cannot represent an arbitrary collection. Query rooms by hostel_id rather than name. Reject a missing-parent room (with a foreign-key constraint and/or universal server check); a number-shaped ID alone is not integrity enforcement.",
         ["relationship_cardinality", "foreign_key_placement", "relationship_integrity"],
         diagram=trace("relationship-rows-trace", "One hostel, multiple room rows", ["Hostel H7", "Room R1: hostel_id H7", "Room R2: hostel_id H7"], "Where is each room's parent link?", ["On each Room as hostel_id", "One room_id field on Hostel", "Only in the hostel display name"])),
    case("one-to-many", "practice-child", "guided_practice", 3,
         "A reading app has one shelf per book record and many book records per shelf. It stores one book_id on Shelf and loses the previous link whenever another book is added. Repair the relationship path and show how two books can refer to the same shelf.",
         ["Each book record belongs to exactly one shelf", "Shelves may be empty", "Shelf and book IDs are stable"],
         "Store shelf_id on each Book row, referencing the existing Shelf. B1.shelf_id and B2.shelf_id can both equal S1 while Shelf has no single authoritative book_id slot. Listing uses a filter on Book.shelf_id; enforce the required parent's existence.",
         ["relationship_cardinality", "foreign_key_placement", "relationship_integrity"],
         diagram=repair("relationship-fk-repair", "Store a book's parent", "Book B1", "Parent link", [("child_fk", "Book.shelf_id → Shelf.shelf_id"), ("parent_fk", "Shelf.book_id → one Book only")], "Choose where the parent relationship is recorded; explain a second book.")),
    case("one-to-many", "practice-cloze", "guided_practice", 4,
         "A course has many lessons; each lesson belongs to exactly one course. A lesson referring to a missing course must be rejected. Complete the scaffold and explain how renaming a course affects existing lessons.",
         ["No shared lessons across courses", "course_id is stable", "Course names may change"],
         "Lesson is the many side and stores course_id referencing an existing Course. The foreign key uses stable identity so a course rename changes its name attribute without relinking lessons. Reject missing parent IDs; a Course can have no lessons.",
         ["relationship_cardinality", "foreign_key_placement", "relationship_integrity"],
         cloze=cloze("relationship-cloze", "The many side is {child}; its parent link is {foreign_key}; a missing required parent is {missing}.", [("child", ["Lesson", "Course", "the course name"]), ("foreign_key", ["Lesson.course_id", "Course.one_lesson_id", "Lesson.course_name only"]), ("missing", ["rejected before storing an orphan", "made valid by any integer", "ignored because the UI filtered courses"])], "Explain the link using two example lesson rows and a renamed course.")),
    case("one-to-many", "transfer-order", "transfer", 5,
         "An order contains zero or more tracking events, and every event belongs to exactly one order. Order numbers shown to customers may change format. Design the parent/child link and describe how to retrieve all events for order O19. The product forbids events for missing orders.",
         ["order_id is the stable internal identifier", "Tracking events are independent rows", "No event belongs to two orders"],
         "Put order_id on each TrackingEvent, referencing Order.order_id, with a separate event_id. Filter events by O19, returning zero or many rows. Use stable IDs rather than display order numbers and reject nonexistent parent IDs with effective integrity enforcement.",
         ["relationship_cardinality", "foreign_key_placement", "relationship_integrity"]),
    case("one-to-many", "transfer-deletion", "transfer", 6,
         "One project has many task records; each task must keep a valid project link. A product rule says completed task history must remain accessible after a project is retired. An engineer proposes deleting the Project row but leaving Task.project_id unchanged. Evaluate the design and propose a policy satisfying the rule.",
         ["Task.project_id references a stable Project.project_id", "Each task has exactly one project", "Historical tasks must remain, not be cascade-deleted"],
         "Task is the many side and its project_id stores the link. Deleting the parent while retaining the required IDs creates invalid references unless prevented. Keep/soft-retire the project, or restrict deletion while tasks exist, so historical links remain valid. Cascade deletion conflicts with this scenario's retain-history rule; no ownership model is required.",
         ["relationship_cardinality", "foreign_key_placement", "relationship_integrity"]),
    case("one-to-many", "transfer-members", "transfer", 7,
         "A workshop has multiple registered seats, each assigned to exactly one workshop. Two workshops can share a display title. The report joins Seat.workshop_title to Workshop.title and duplicates some seats. Explain a stable model, the listing query and a missing-workshop rule.",
         ["A seat cannot be shared across workshops", "Workshop IDs are unique and stable", "New seats must reference an existing workshop"],
         "Store workshop_id on each Seat and join/filter that to Workshop.workshop_id rather than duplicated titles. This represents many seats for one workshop and one workshop for each seat. Enforce parent existence on new seats; changing a workshop title does not alter those relationships.",
         ["relationship_cardinality", "foreign_key_placement", "relationship_integrity"]),
    case("one-to-many", "confirmation-comments", "confirmation", 8,
         "Each article can have zero or more comments, and each comment belongs to exactly one article. Titles can change. Show a minimal schema, explain how article A8's comments are found and how to prevent a comment pointing at a nonexistent article.",
         ["There are no comments shared by articles", "article_id and comment_id are stable", "Comments require an existing article"],
         "Article has article_id/title; Comment has comment_id/text/article_id referencing Article.article_id. Filter Comment.article_id by A8 to find zero or many comments; do not store a single comment ID on Article or join by mutable title. Enforce required parent existence through the write path and/or a database foreign key.",
         ["relationship_cardinality", "foreign_key_placement", "relationship_integrity"]),
]


ADDITIONAL_CASE_BANKS = {
    "request-anatomy": REQUEST_CASES,
    "backend-validation": VALIDATION_CASES,
    "secret-placement": SECRET_CASES,
    "save-retrieve-display": PIPELINE_CASES,
    "entities-attributes": ENTITY_CASES,
    "one-to-many": RELATIONSHIP_CASES,
}
