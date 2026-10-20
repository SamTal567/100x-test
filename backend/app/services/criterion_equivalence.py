"""Prepared, concept-scoped evidence equivalences; never infer from broad skill IDs.

A bundle must be demonstrated in the same later attempt. Empty restarted state
requires both memory loss AND rebuilding state, not recovery reasoning alone.
"""
STORAGE_EQUIVALENCES = {
    'Identifies memory as volatile': [('Cache is volatile',)],
    'Variable data is lost': [('Cache is volatile',)],
    'Recognises empty restart state': [('Cache is volatile', 'Recovery path repopulates cache')],
    'Recovery path': [('Recovery path repopulates cache',)],
    'Identifies startup recovery': [('Recovery path repopulates cache',)],
}


def covers_criterion(name, rows, concept_slug):
    demonstrated = {c['criterion'] for c in rows if c.get('met') is True
                    and c.get('rating') == 'demonstrated' and c.get('issue_type') != 'technical_failure'}
    if name in demonstrated:
        return True
    bundles = STORAGE_EQUIVALENCES.get(name, []) if concept_slug == 'storage-persistence' else []
    return any(set(bundle) <= demonstrated for bundle in bundles)
